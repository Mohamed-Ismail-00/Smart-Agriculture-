"""
Step 4 - quality report and exports of the finished dataset.

Outputs (research/data/dataset/):
  csv/samples.csv                       one row per sample (label, split, coordinates, quality)
  csv/{REGION}_{SEASON}_timeseries.csv  one row per sample and dekad: the five vegetation indices
  csv/sample_for_viewing.xlsx           100 samples per crop, small enough to open in Excel
  qa/curves_{REGION}_{SEASON}.png       mean NDVI and NDWI curve of every class
  qa/summary.json                       the numbers behind the data card

In the CSV files gaps are filled (linear in time) and `n_clear` says how many clear
satellite passes stand behind each value: 0 means the value was interpolated.

    python research/step4_export.py
"""

import argparse
import json
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import dataset
from config import DATASET_DIR, DOUBTFUL_LABELS, REGIONS, SEED

EXCEL_SAMPLES_PER_CROP = 100
MIN_CLASS_FOR_CURVES = 300


def long_table(d: dict, V: np.ndarray, rows: np.ndarray) -> pd.DataFrame:
    """Tidy table (one row per sample and dekad) for the chosen sample rows."""
    s = d["samples"].iloc[rows]
    steps = V.shape[1]
    table = pd.DataFrame({
        "sample_id": np.repeat(s["sample_id"].to_numpy(), steps),
        "pixel_id": np.repeat(s["pixel_id"].to_numpy(), steps),
        "region": np.repeat(s["region"].to_numpy(), steps),
        "season": np.repeat(s["season_key"].to_numpy(), steps),
        "dekad": np.tile(np.arange(1, steps + 1), len(s)),
        "date": np.tile(np.array(d["dates"]), len(s)),
        "n_clear": d["n_clear"][rows].reshape(-1),
    })
    for i, name in enumerate(dataset.INDICES):
        table[name] = V[rows, :, i].reshape(-1)
    table["crop"] = np.repeat(s["crop"].to_numpy(), steps)
    return table


def plot_curves(key: str, d: dict, V_raw: np.ndarray, out_dir):
    """Mean NDVI and NDWI per class from clear observations only (no interpolation)."""
    crops = d["samples"]["crop"].to_numpy()
    names = [c for c, n in zip(*np.unique(crops, return_counts=True)) if n >= MIN_CLASS_FOR_CURVES]
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5), sharex=True)
    x = np.arange(len(d["dates"]))
    curves = {}
    region, season_key = key.split("_")
    for name in names:
        sel = crops == name
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)     # a dekad nobody saw clearly
            mean = np.nanmean(V_raw[sel], axis=0)        # [time, indices]
        curves[name] = {"n": int(sel.sum()), "ndvi": np.round(mean[:, 0], 3).tolist(), "ndwi": np.round(mean[:, 2], 3).tolist()}
        doubt = (region, season_key, name) in DOUBTFUL_LABELS
        for ax, col in zip(axes, (0, 2)):
            ax.plot(x, mean[:, col], marker="o", ms=3, lw=1.8, ls="--" if doubt else "-",
                    label=f"{name}{' (name doubtful)' if doubt else ''} ({sel.sum():,})")
    for ax, title in zip(axes, ("NDVI (greenness)", "NDWI (canopy / surface water)")):
        ax.set_title(f"{key}: mean {title} per class")
        ax.set_xticks(x[::3])
        ax.set_xticklabels([d["dates"][i][5:] for i in x[::3]], rotation=45)
        ax.set_xlabel("dekad start (month-day)")
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(out_dir / f"curves_{key}.png", dpi=110)
    plt.close(fig)
    return curves


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-timeseries", action="store_true",
                        help="do not rewrite the large time-series CSV files (everything else is redone)")
    args = parser.parse_args()

    csv_dir, qa_dir = DATASET_DIR / "csv", DATASET_DIR / "qa"
    csv_dir.mkdir(parents=True, exist_ok=True)
    qa_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    samples = pd.read_parquet(DATASET_DIR / "samples.parquet")
    samples.to_csv(csv_dir / "samples.csv", index=False, float_format="%.6f")
    summary = {"samples": len(samples), "pixels": int(samples["pixel_id"].nunique()),
               "blocks": int(samples["block_id"].nunique()), "sets": {}}
    excel_parts, total_rows = [], 0

    for region, cfg in REGIONS.items():
        for season_key in cfg["maps"]:
            key = f"{region}_{season_key}"
            d = dataset.load(region, season_key)
            V_raw = dataset.vegetation_indices(d["X"])
            V = dataset.vegetation_indices(dataset.fill_gaps(d["X"]))
            usable = np.isfinite(V[:, 0, 0])            # False only if a sample never had a clear view

            path = csv_dir / f"{key}_timeseries.csv"
            rows_all = np.nonzero(usable)[0]
            for n, start in enumerate(range(0, 0 if args.skip_timeseries else len(rows_all), 20_000)):
                long_table(d, V, rows_all[start:start + 20_000]).to_csv(
                    path, mode="w" if n == 0 else "a", header=n == 0, index=False, float_format="%.4f")
            n_rows = len(rows_all) * V.shape[1]
            total_rows += n_rows

            crops = d["samples"]["crop"]
            pick = np.concatenate([
                rng.choice(idx := np.nonzero((crops == c).to_numpy() & usable)[0], size=min(EXCEL_SAMPLES_PER_CROP, len(idx)), replace=False)
                for c in sorted(crops.unique())
            ])
            excel_parts.append(long_table(d, V, np.sort(pick)))

            curves = plot_curves(key, d, V_raw, qa_dir)
            s = d["samples"]
            summary["sets"][key] = {
                "samples": len(s), "time_steps": V.shape[1], "csv_rows": n_rows,
                "samples_never_clear": int((~usable).sum()),
                "dekads_interpolated_pct": round(float((d["n_clear"] == 0).mean() * 100), 1),
                "classes": s.groupby("crop").size().sort_values(ascending=False).to_dict(),
                "doubtful_names": {c: why for (r, k, c), why in DOUBTFUL_LABELS.items() if (r, k) == (region, season_key)},
                "split": s.groupby("split").size().to_dict(),
                "mean_curves": curves,
            }
            print(f"{key}: {len(s):,} samples x {V.shape[1]} dekads -> {n_rows:,} rows  "
                  f"({summary['sets'][key]['dekads_interpolated_pct']}% of values interpolated)", flush=True)

    summary["csv_rows_total"] = total_rows
    (qa_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    excel = pd.concat(excel_parts, ignore_index=True)
    columns = pd.DataFrame({
        "column": ["sample_id", "pixel_id", "region", "season", "dekad", "date", "n_clear",
                   "ndvi, evi, ndwi, savi, gndvi", "crop"],
        "meaning": [
            "one sample = one pixel in one season",
            "the 10 m pixel (same id if it appears in another season)",
            "ZAN = Zankalon (Sharqia), SGZ = Sidi Ghazi (Kafr El-Sheikh)",
            "W2324 = winter 2023-24, S2023 / S2024 = summer",
            "10-day period number within the season (1 = first)",
            "first day of that dekad",
            "clear satellite passes behind the value; 0 = interpolated from neighbouring dekads",
            "vegetation indices computed from Sentinel-2 surface reflectance",
            "label from the FAO WaPOR crop type map",
        ],
    })
    with pd.ExcelWriter(csv_dir / "sample_for_viewing.xlsx", engine="xlsxwriter") as writer:
        columns.to_excel(writer, sheet_name="columns", index=False)
        excel.to_excel(writer, sheet_name="timeseries", index=False)
        samples[samples["sample_id"].isin(excel["sample_id"].unique())].to_excel(writer, sheet_name="samples", index=False)
    print(f"total: {len(samples):,} samples, {total_rows:,} time-series rows; Excel sample: {len(excel):,} rows", flush=True)


if __name__ == "__main__":
    main()

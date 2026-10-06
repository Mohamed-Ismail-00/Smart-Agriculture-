"""
QA: can the labels be learned from the series at all?

Not a model for the project - a sanity floor. Each class gets the average curve of its
training pixels; a validation pixel is given the class whose curve it is closest to. If the
labels and the satellite series were misaligned or scrambled, this would score at chance.

    python research/check_learnable.py
"""

import json

import numpy as np

import dataset
from config import DATASET_DIR, DOUBTFUL_LABELS, MIN_CLASS_FOR_FOLDS, REGIONS


def macro_f1(truth: np.ndarray, predicted: np.ndarray, n_classes: int) -> tuple:
    scores = []
    for c in range(n_classes):
        tp = np.sum((predicted == c) & (truth == c))
        precision = tp / max(np.sum(predicted == c), 1)
        recall = tp / max(np.sum(truth == c), 1)
        scores.append(0.0 if tp == 0 else 2 * precision * recall / (precision + recall))
    return float(np.mean(scores)), scores


def main():
    results = {}
    for region, cfg in REGIONS.items():
        for season_key in cfg["maps"]:
            d = dataset.load(region, season_key)
            s = d["samples"]
            counts = s[s["is_crop"]].groupby("crop").size()
            classes = sorted(counts[counts >= MIN_CLASS_FOR_FOLDS].index)
            keep = s["crop"].isin(classes).to_numpy()
            features = dataset.vegetation_indices(dataset.fill_gaps(d["X"][keep]))
            features = features.reshape(len(features), -1)
            y = s.loc[keep, "crop"].map({c: i for i, c in enumerate(classes)}).to_numpy()
            split = s.loc[keep, "split"].to_numpy()
            usable = np.isfinite(features).all(axis=1)
            train, val = (split == "train") & usable, (split == "val") & usable

            mean, std = features[train].mean(axis=0), features[train].std(axis=0) + 1e-6
            z = (features - mean) / std
            centroids = np.stack([z[train & (y == c)].mean(axis=0) for c in range(len(classes))])
            zv = z[val]
            # squared distance to every centroid, without building a [samples, classes, features] array
            dist = (zv ** 2).sum(axis=1)[:, None] - 2 * zv @ centroids.T + (centroids ** 2).sum(axis=1)[None, :]
            predicted = dist.argmin(axis=1)
            f1, per_class = macro_f1(y[val], predicted, len(classes))
            accuracy = float((predicted == y[val]).mean())
            majority = float(np.bincount(y[val]).max() / val.sum())
            key = f"{region}_{season_key}"
            trusted = [v for c, v in zip(classes, per_class) if (region, season_key, c) not in DOUBTFUL_LABELS]
            results[key] = {
                "classes": classes, "train": int(train.sum()), "val": int(val.sum()),
                "accuracy": round(accuracy, 3), "macro_f1": round(f1, 3),
                "macro_f1_without_doubtful_names": round(float(np.mean(trusted)), 3),
                "chance_macro_f1": round(1 / len(classes), 3), "always_biggest_class_accuracy": round(majority, 3),
                "f1_per_class": {c: round(v, 3) for c, v in zip(classes, per_class)},
            }
            print(f"{key}: {len(classes)} classes, train {train.sum():,}, val {val.sum():,}  "
                  f"accuracy {accuracy:.3f} (always-biggest-class {majority:.3f})  macro-F1 {f1:.3f} (chance {1 / len(classes):.3f}; "
                  f"{np.mean(trusted):.3f} over the {len(trusted)} classes with trusted names)")
            print("    F1 per class: " + ", ".join(f"{c} {v:.2f}" for c, v in zip(classes, per_class)), flush=True)
    (DATASET_DIR / "qa").mkdir(parents=True, exist_ok=True)
    (DATASET_DIR / "qa" / "learnable.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

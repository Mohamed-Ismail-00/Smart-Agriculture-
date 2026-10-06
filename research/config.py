"""Shared configuration for the crop-type dataset pipeline."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
DATA = ROOT / "data"            # git-ignored
FAO_DIR = DATA / "fao"          # FAO WaPOR crop type maps (downloaded as published)
LABELS_DIR = DATA / "labels"    # label grids on the Sentinel-2 grid + sampled pixels
RAW_DIR = DATA / "raw"          # Sentinel-2 values extracted per acquisition date
DATASET_DIR = DATA / "dataset"  # final tables

# ---------------------------------------------------------------------------
# Grid: Sentinel-2's own grid (UTM zone 36N, 10 m), so reflectance is never resampled.
# The label maps are warped onto it instead.
# ---------------------------------------------------------------------------
CRS_UTM = "EPSG:32636"
PIXEL_M = 10

# The ten Sentinel-2 bands kept (visible, red-edge, NIR, SWIR). Bands not in BANDS_10M are 20 m.
BANDS = ["B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12"]
BANDS_10M = {"B02", "B03", "B04", "B08"}

# Scene Classification values treated as unusable. Identical to the platform's rule in
# app/connectors/sentinel.py so training data and live inference see the same mask.
SCL_INVALID = (0, 1, 3, 8, 9, 10)
# Classes that count as cloud or cloud shadow when measuring distance to the nearest cloud.
SCL_CLOUD = (3, 8, 9, 10)

# ---------------------------------------------------------------------------
# Regions and seasons. Imagery is fetched as one continuous period per region, covering
# every labelled season.
#
# Only relative orbit 21 is used. It covers both regions completely on every pass (one
# acquisition every 5 days). Orbit 64 clips the north-east corner of Zankalon only, so
# using it would give some pixels twice as many observations, from a different viewing
# angle, than the rest of the dataset.
# ---------------------------------------------------------------------------
ORBIT = 21
REGIONS = {
    "ZAN": {
        "name": "Zankalon",
        "governorate": "Sharqia",
        "imagery": ("2023-10-01", "2024-10-31"),
        "maps": {"W2324": "EGY-ZAN.2024.GS1", "S2024": "EGY-ZAN.2024.GS2"},
    },
    "SGZ": {
        "name": "Sidi Ghazi",
        "governorate": "Kafr El-Sheikh",
        "imagery": ("2023-05-01", "2024-10-31"),
        "maps": {"S2023": "EGY-SGZ.2023.GS2", "W2324": "EGY-SGZ.2024.GS1", "S2024": "EGY-SGZ.2024.GS2"},
    },
}

SEASONS = {
    "S2023": {"season": "summer", "start": "2023-05-01", "end": "2023-10-31"},
    "W2324": {"season": "winter", "start": "2023-10-01", "end": "2024-05-31"},
    "S2024": {"season": "summer", "start": "2024-05-01", "end": "2024-10-31"},
}

# FAO class codes -> names, from the official WaPOR style files (EGY-*-CROP-GS1 / GS2).
# The codes are shared by Zankalon and Sidi Ghazi. Mallawi is excluded: its published
# legend does not match the codes found in its files.
LEGEND = {
    "winter": {
        1: "wheat", 2: "sugarbeet", 3: "flax", 4: "clover", 6: "beans", 7: "vegetables",
        8: "orchards", 9: "medicinal_plants", 12: "bare_soil", 13: "water", 14: "built_up",
    },
    "summer": {
        1: "rice", 2: "maize", 3: "cotton", 7: "vegetables", 8: "orchards", 11: "others",
        12: "bare_soil", 13: "water", 14: "built_up", 15: "roads",
    },
}
NON_CROP = {"others", "bare_soil", "water", "built_up", "roads"}
FAO_NODATA = 255

# Classes whose published name does not fit how their pixels behave. The names are kept
# (they are FAO's), but the samples carry label_doubt = True so experiments can leave them
# out. Evidence: the mean curves in data/dataset/qa and the same pixels in the other maps.
DOUBTFUL_LABELS = {
    ("SGZ", "W2324", "orchards"): "bare in Dec-Jan, peaks in March, and 80% is rice in the summer map: an annual crop, not trees",
    ("SGZ", "W2324", "medicinal_plants"): "flat sparse vegetation all winter (NDVI ~0.35); 55% is bare soil in the summer 2023 map",
    ("SGZ", "S2024", "built_up"): "grows and is harvested like an early-summer crop; 67% was rice in the 2023 map",
    ("SGZ", "S2024", "bare_soil"): "carries a crop until July; 59% was rice in the 2023 map",
}

# ---------------------------------------------------------------------------
# Sampling design
# ---------------------------------------------------------------------------
PURITY_WINDOW = 3     # a pixel is a candidate only if its 3x3 neighbourhood is one class
BLOCK_PX = 200        # 2 km blocks: the unit that is kept whole in train / validation / test
GUARD_PX = 5          # 50 m left unsampled on each side of a block edge (100 m gap between blocks)
CELL_PX = 10          # 100 m cells used to spread the sample evenly in space
CAP_CROP = 60_000     # pixels per crop class, per region and season
CAP_NON_CROP = 8_000  # pixels per non-crop class, per region and season
N_FOLDS = 5
# Classes smaller than this are too few and too clustered to balance across folds (or to
# score reliably later); they are kept in the data but ignored when folds are drawn.
MIN_CLASS_FOR_FOLDS = 2_000
SEED = 20261006

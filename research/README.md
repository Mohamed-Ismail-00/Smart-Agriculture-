# Crop-type time-series dataset: Zankalon and Sidi Ghazi, Egypt

Sentinel-2 time series for about one million 10 m pixels in two Nile Delta irrigation
districts, each labelled with the crop that FAO mapped there in 2023-2024. It is the
training data for the crop classifier that replaces the platform's rule-based guess.

The data itself is not in git (`research/data/` is ignored). Everything here rebuilds it.

## Sources

| What | From | Licence |
|---|---|---|
| Crop labels | FAO WaPOR crop type maps `L3-CROP-TYPE.EGY-ZAN` and `EGY-SGZ`, 10 m, seasons 2023-2024, made from Sentinel-2 and field surveys with Egypt's irrigation and agriculture ministries | CC BY 4.0 (cite FAO) |
| Imagery | Sentinel-2 Level-2A surface reflectance (ESA / Copernicus), read from Microsoft Planetary Computer | free and open |

Mallawi, the third FAO site, is left out: its published legend does not match the class
codes in its files.

## Pipeline

Run from inside `research/` with the environment in `requirements.txt`.

| Step | Script | Does |
|---|---|---|
| 1 | `step1_sample_pixels.py` | warps each FAO map onto the Sentinel-2 grid, keeps interior pixels, draws a spatially spread sample per class, assigns 2 km blocks to five folds |
| 2 | `step2_download.py` | reads the ten bands for those pixels from every pass (resumable, about 12.6 GB of transfer) |
| 3 | `step3_build_dataset.py` | reflectance conversion, cloud screening, 5-day series and dekadal composites |
| 4 | `step4_export.py` | CSV and Excel exports, per-class curves, summary numbers |

Checks: `check_alignment.py` (maps vs. imagery), `check_extraction.py` (stored values vs.
an independent read), `check_learnable.py` (a nearest-mean-curve classifier as a sanity floor).

`dataset.py` loads the result for modelling.

## Design choices

- **Sentinel-2's own grid.** Pixels are native 10 m pixels in UTM 36N, never resampled; the
  label maps are warped instead (nearest neighbour). A 20 m band gives each pixel the value
  of the 20 m cell that contains it.
- **Interior pixels only.** A pixel is a candidate only if its 3x3 neighbourhood is one
  class, which removes mixed field-edge pixels and absorbs small registration error.
- **Spread sampling.** Candidates are taken round-robin from 100 m cells so one large field
  cannot dominate, up to 60,000 per crop class (8,000 per non-crop class) per region and season.
- **Spatial blocks.** Train / validation / test are whole 2 km blocks, with 50 m left
  unsampled along block edges, so no two pixels from different blocks are closer than 100 m.
  Neighbouring pixels are near-duplicates; a random pixel split would leak.
- **One orbit.** Only relative orbit 21, which covers both regions fully every 5 days.
  Orbit 64 clips one corner of Zankalon and would give those pixels twice the observations.
- **Same formulas as the platform.** The reflectance offset rule and the vegetation indices
  are imported from `services/backend`, so training data and live inference agree.
- **Cloud screening in three layers:** the Scene Classification mask (same classes the
  platform drops), a 100 m buffer around clouds and shadows, and a temporal test that drops a
  pass standing apart from both its neighbours the way haze (blue up) or shadow (NIR and
  SWIR down) would. Thresholds were set on real data: flagged passes are six times more
  common next to clouds and sit 0.10 NDVI below their neighbours.
- **Nothing is gap-filled in the stored arrays.** Missing stays missing; `dataset.fill_gaps`
  offers linear filling, and a causal variant for early-classification experiments that
  never looks at later dates.
- **Dekads.** The 10-day calendar (1-10, 11-20, 21-end) is the one FAO WaPOR uses; a dekad
  holds the median of its clear passes.

## Files (`research/data/dataset/`)

| File | Content |
|---|---|
| `samples.parquet` | one row per sample (a pixel in a season) |
| `{REGION}_{SEASON}.npz` | `passes` [samples, 5-day passes, 10 bands], `dekads` [samples, dekads, 10 bands], `dekad_n` (clear passes per dekad), the dates, `sample_id`; reflectance x 10000 as int16, -1 = missing |
| `csv/{REGION}_{SEASON}_timeseries.csv` | one row per sample and dekad: NDVI, EVI, NDWI, SAVI, GNDVI (gap-filled) and `n_clear` (0 = interpolated) |
| `csv/samples.csv`, `csv/sample_for_viewing.xlsx` | the sample table, and 100 samples per class for Excel |
| `qa/` | per-class mean curves, summary numbers, sanity-classifier scores |

Main columns of `samples`: `sample_id`, `pixel_id`, `region` (ZAN, SGZ), `season_key`
(W2324, S2023, S2024), `crop`, `is_crop`, `label_doubt`, `lon`, `lat`, `block_id`, `fold`,
`split`, `purity5` (share of the 5x5 neighbourhood with the same class), `weight` (interior
pixels of the class each sample stands for), `n_passes_clear`, `n_dekads_clear`,
`longest_gap_dekads`.

## Numbers

| | |
|---|---|
| Samples (pixel x season) | 1,074,827 |
| Distinct pixels | 993,610 |
| Spatial blocks | 314 (Zankalon 182, Sidi Ghazi 132) |
| Train / validation / test | 647,860 / 213,296 / 213,671 |
| Pixel-passes downloaded | 85.6 million, 10 bands each |
| Kept after cloud screening | 65.0 million (76%) |
| Rows in the dekadal CSV tables | 22,589,094 |

| Set | Samples | Passes | Dekads | Dekads with no clear pass |
|---|---|---|---|---|
| Zankalon, winter 2023-24 | 233,529 | 48 | 24 | 16.7% |
| Zankalon, summer 2024 | 231,231 | 35 | 18 | 6.2% |
| Sidi Ghazi, summer 2023 | 153,484 | 36 | 18 | 13.0% |
| Sidi Ghazi, winter 2023-24 | 306,839 | 48 | 24 | 26.8% |
| Sidi Ghazi, summer 2024 | 149,744 | 35 | 18 | 8.1% |

Crop samples with trusted names (914,464): winter - wheat 115,309, clover 115,457,
sugarbeet 71,149, orchards 56,808, vegetables 44,790, flax 18,951, beans 12,663; summer -
rice 174,824, cotton 125,994, maize 78,921, vegetables 61,375, orchards 38,223.

## Checks and results

- **Registration:** each of the five maps was slid up to 4 pixels in every direction against
  a clear scene; class separation is highest at zero offset for all five.
- **Extraction:** 1,080 stored values from six random units re-read through GDAL point
  sampling, all identical (and 540 of 540 during the pilot).
- **Files:** all 1,975 downloaded units open and match the pixel list.
- **Curves:** the mean NDVI / NDWI curves of the main crops follow their calendars (wheat
  peaks in February and is cut in April, clover greens in October, sugarbeet has the wettest
  canopy, rice starts flooded and peaks in August, maize peaks and dries before cotton).
- **Sanity classifier** (nearest class-mean curve, validated on separate blocks), macro-F1:
  Zankalon winter 0.86, summer 0.75; Sidi Ghazi summer 2023 0.68, winter 0.68, summer 2024
  0.80. Chance is 0.14-0.33. This is a floor, not a result.

## Known limitations

- **The labels are a map, not field visits.** FAO's maps are themselves a classification
  trained on field data, so they contain errors we cannot measure.
- **Doubtful class names** (`label_doubt = True`, 92,891 samples, all in Sidi Ghazi):
  winter "orchards" behave like an annual crop and are rice in summer; winter "medicinal
  plants" are flat sparse vegetation that the summer map calls bare soil; summer 2024
  "built-up" and "bare soil" carry a crop. Leave them out of cross-region tests.
  Zankalon orchards are 70-83% consistent between the winter and summer maps.
- **Small classes** cannot be scored alone: Sidi Ghazi winter vegetables (934), summer
  orchards (501 and 38), summer 2023 vegetables (162).
- **Winter cloud at Sidi Ghazi.** From late January to late March 2024 most passes were
  cloudy; 19% of its winter samples have a gap longer than 30 days.
- **No acquisitions between 9 and 24 September 2024** exist in the archive, so that dekad is
  empty in both summer 2024 sets.
- **Interior pixels are the easy ones.** Scores on this dataset will be higher than on
  field edges and very small plots.
- **Two districts, one year.** Enough to test transfer between regions and between two
  summers at Sidi Ghazi, not to claim the model works across Egypt.

## Citation for the labels

FAO. 2026. WaPOR: Crop type mapping (Zankalon; Sidi Ghazi), Egypt, 2023-2024, 10 m.
https://data.apps.fao.org/catalog/organization/wapor. Licence: CC-BY-4.0.

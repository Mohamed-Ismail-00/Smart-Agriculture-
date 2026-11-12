# 🧠 PROJECT MIND — Early Time-Series Crop Classification in the Nile Delta ("Ghait")
> Last updated: 2026-11-10 | Session #2 (preprocessing + feature engineering plan) | Session #1 created mind.md (earlier work was one long chat, 2026-10-05 → 2026-10-28)

## 1. Project Goal
- University ML course project (Mohamed Ismail, aiming for first place). Research title: **Early Time-Series Crop Classification in the Nile Delta** (old nickname "Ghait" is retired everywhere: user wants the name "Nile Delta time series" / the research title in all files).
- Question: identify the crop in a field from Sentinel-2 time series, **as early in the season as possible**.
- Built on a private fork of a team web platform (FastAPI + React + Postgres). The platform's current crop guess is rule-based + a RandomForest on synthetic data; the contribution is real ground truth + real time-series models.
- Priority order:
  1. Dataset (done) → EDA/cleaning notebook (done) → **models** (next, waits for TA material).
  2. Models in order: Random Forest, LightGBM, MiniRocket, LSTM/Transformer; Chronos-2 for forecast-then-classify (predict rest of the season curve, then classify).
  3. Evaluation: macro-F1, spatial-block splits, cross-region (train ZAN → test SGZ) and cross-year (SGZ S2023 vs S2024), early-classification curves (accuracy vs. dekads seen).
  4. Plug the final model into the platform (farmer draws field → crop prediction).
- "Done" = trained/evaluated models + report + model served in the platform.
- Out of scope: mobile app, Google sign-in work.

## 2. Tech Stack
- **Backend:** Python 3.11, FastAPI, SQLAlchemy, PostgreSQL 14, APScheduler, pandas/numpy, scikit-learn, pystac-client + planetary-computer + odc-stac/xarray/rioxarray (Sentinel-2), httpx/requests, python-jose/passlib, google-auth. `backend/requirements.txt` (unpinned).
- **Frontend:** React 19, Vite 8, react-router 7, Leaflet 1.9 + leaflet-draw 1.0.4 + react-leaflet 5, Recharts 3, vitest 4, ESLint 9. Capacitor libs still in package.json (used by `services/googleAuth.js`).
- **Infra:** Docker Compose (postgres, backend, scheduler, frontend Vite dev server, nginx proxy).
- **External APIs:** Microsoft Planetary Computer STAC (Sentinel-2 L2A), Open-Meteo, ISRIC SoilGrids, MODIS NDVI, Nominatim/OSM (search + reverse geocoding), Groq (AI insights, key not set).
- **ML/research:** `ml/research/.venv` (Python 3.11, `ml/research/requirements.txt`). EDA: conda env `ghait` (Python 3.12, pandas 3.0.6 + pyarrow, seaborn 0.13.2), kernel "Python (ghait)", spec `ml/eda/environment.yml`.
- **Data sources:** FAO WaPOR crop type maps L3 `EGY-ZAN`, `EGY-SGZ` (CC BY 4.0); Sentinel-2 L2A relative orbit 21.

## 3. Architecture & Code Map
```
backend/        FastAPI app (app/), Dockerfile, requirements.txt, pytest.ini
frontend/       React + Vite app (src/), Dockerfile, package.json
docker/         docker-compose.yml (+ local override), nginx/, postgres/ (Dockerfile, init.sql, seed.sql), data/ (runtime /data mount, ignored)
env/            .env.example (tracked); .env.backend, .env.db (secret, ignored)
ml/research/    dataset pipeline (step1..4), checks, config.py, dataset.py, data/ (ignored, ~12.6 GB raw)
ml/eda/         eda.ipynb, environment.yml, clean_samples.csv (ignored output)
ml/models/      features.py (shared features), 01_prepare_data.ipynb, 01_prepare_data_explained.md (Arabic step-by-step explanation for the user), data/ (ignored: meta.parquet, prep.json)
docs/           nile_delta_diagram.excalidraw (presentation diagram)
mind.md         this file
```
**Backend key files (`backend/app/`)**
- `main.py` → FastAPI app, creates tables on startup, admin from env, routers under `/api/v1`: auth, users, climate, ingestion, pipeline, lands, crops, soil, ai, activity_logs, notifications, trust; `health` at root.
- `connectors/sentinel.py` → STAC access, `boa_offset_dn()` (−1000 DN offset for baseline ≥04.00), `fetch_sentinel_visual_urls`, `fetch_sentinel_timeseries`. SCL invalid classes = (0,1,3,8,9,10) — research uses the same.
- `cv/indices.py` → vegetation index formulas (imported by research so training = inference).
- `lands/validator.py` → `validate_agricultural_land()` (OSM/MODIS checks; messages rewritten in plain language). `lands/schemas.py` `LandListItem` includes `description`.
- `pipeline/land_discovery_pipeline.py` → on land creation: climate, soil/ET₀, NDVI backfill (Sentinel), SoilGrids. `pipeline/land_monitoring_pipeline.py` → scheduled refresh (run by `scheduler/jobs.py`, container `agri_scheduler`).
- `crops/identification.py` → current rule-based crop guess (NDVI profile matching). `ml/crop_classifier.py` + `rf_crop_model.joblib` → old RF on synthetic data (deprecated; to be replaced by our model).
- `tasks/satellite_task.py` → per-land NDVI update, alerts.
- Unused but still present: AI chat backend (`api/ai.py` chat parts, `models/ai_chat.py`), irrigation/soil-moisture logic (`water/`, `lands/water_metrics.py`).

**Frontend key files (`frontend/src/`)**
- `App.jsx` routes: /login, /register, /dashboard, /lands, /lands/new, /lands/:id, /lands/compare, /profile, /logs.
- `components/map/MapDrawComponent.jsx` → land marking: `DELTA_GOVERNORATES` (8 bboxes), `searchPlaces()` (Nominatim, `countrycodes=eg`, ar/en by script), tools "Mark my field" (`place`: click drops screen-sized square, `START_BOX_SHARE=0.12`, needs zoom ≥ `MIN_MARK_ZOOM=14`) and "Draw corners" (`polygon`, `showArea:false`); Undo/Finish/Cancel; editable vertices (`editdrag` live stats, `edit` emits); area in ha + feddan (`HECTARES_PER_FEDDAN=0.420083`).
- `pages/lands/AddLandPage.jsx` → add land; sends `metadata_.trackingVariables` = all four; auto-fills name/description from reverse geocoding once per shape.
- `pages/lands/LandsPage.jsx` → cards with place label + ha·feddan. `features/land-detail/*` → detail sections (soil moisture/irrigation removed, values labelled "estimate").
- `components/AuthenticatedImage.jsx` → loads protected images as blob URLs (cache-aware revoke).
- `services/api.js` → API client (chat helpers removed).

**ML data flow**
FAO maps → `step1_sample_pixels.py` (interior pixels, spread sampling, 2 km blocks → 5 folds) → `step2_download.py` (10 bands per pass, resumable) → `step3_build_dataset.py` (reflectance offset, 3-layer cloud screening, 5-day + dekadal composites, no gap-filling in arrays) → `step4_export.py` (CSV/Excel/QA) → `ml/eda/eda.ipynb` → `ml/models/01_prepare_data.ipynb` (+ `features.py`) → models (next: `02_classic_models`).
- `ml/models/features.py` API: `load(season)` → bands [N,T,10] NaN + meta (clean ids only; winter = ZAN+SGZ W2324, summer = ZAN S2024 + SGZ S2023 + SGZ S2024); `channels(X)` → 14 (10 bands + ndvi, ndwi, gndvi, evi); `truncate(C,k)`; `fill(C)` (= `dataset.fill_gaps`, leak-free only after truncate); `flatten`/`feature_names` (`ndvi_d05`, order dekad-major); `phenology(C)` → 12 (`PHENOLOGY_NAMES`); `load_prep`, `encode`, `standardize`. Row order of `load` = order of `meta.parquet` per season.
- `prep.json` per season: classes (alphabetical; winter beans, built_up, clover, flax, orchards, sugarbeet, vegetables, water, wheat; summer bare_soil, built_up, cotton, maize, orchards, rice, roads, vegetables, water), dekads (24/18), channels, features (336/252), phenology names, balanced class_weights (0.33 rice … 28.7 roads), train-only mean/std per channel.
- Files in `ml/research/data/dataset/`: `samples.parquet`; `{REGION}_{SEASON}.npz` (passes/dekads int16 reflectance×10000, −1 = missing); `csv/{REGION}_{SEASON}_timeseries.csv` (one row per sample×dekad: ndvi, evi, ndwi, savi, gndvi gap-filled, `n_clear` 0 = interpolated); `csv/samples.csv`; `qa/`.
- Sample = one pixel in one season (1,074,827; 993,610 distinct pixels). Row = sample × dekad (22,589,094). Winter W2324 = 24 dekads (1 Oct–31 May); summer S2023/S2024 = 18 dekads (1 May–31 Oct).
- Regions: ZAN Zankalon (Sharqia), seasons W2324, S2024; SGZ Sidi Ghazi (Kafr El-Sheikh), seasons S2023, W2324, S2024.
- Splits already in samples: `block_id` (314 blocks), `fold` 0–4, `split` train 647,860 / val 213,296 / test 213,671.
- After EDA cleaning: **978,660 samples / 20,372,886 rows, 14 classes** (rice, cotton, clover, wheat, vegetables, orchards, maize, sugarbeet, built_up, water, flax, beans, bare_soil, roads). Ids in `ml/eda/clean_samples.csv`.

**Platform request flow:** browser → nginx :80 → `/api/*` → backend :8000 (FastAPI) → Postgres; `/` → Vite :5173. New land → validator → discovery pipeline in background → scheduler refreshes periodically.

## 4. Conventions & Rules
- **User:** Mohamed Ismail, student, Egyptian Arabic. Replies: simple, organized, bottom line first, tables, examples. Explanations follow the stored "explanation style" (brief first, gradual parts, define every English term at first use, change approach on "مش فاهم").
- **No over-engineering** (standing rule). Propose any unrequested change and wait for approval before applying it.
- Say what you are doing while working. Verify everything; never invent numbers. Write conclusions only from real outputs.
- **TA rule for notebooks:** apply an EDA/cleaning step only when the data needs it (slides are a menu, not a checklist). Structure: Library → 1 Data Understanding (Read, Random Sample, Size, Info, Description, Unique, Balance) → 2 Data Cleaning (Null, Duplicates) → 3 Outliers (shape → IQR/Z-score → treatment: Remove/Transformation/Imputation/Ignoring/Capping) → 4 EDA → 5 Summary. Needed code only, few comments, tidy.
- Notebook workflow: generate with nbformat builder script → `jupyter nbconvert --execute --inplace` → read outputs → write markdown conclusions → re-run.
- Git: work only on the user's private repo `origin` = https://github.com/Mohamed-Ismail-00/Smart-Agriculture- (never the old team repo). Commit/push only when asked. Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Never** print secrets (ADMIN_PASSWORD etc.); the user reads them from `env/.env.backend`.
- Do not touch the other projects' containers on this machine (ports 5432/8000, `innovera-review`, `lecture-assistant`).
- Don't mix side projects into this repo (see §9).
- Machine: 16 GB RAM, ~2–3 GB free; ~1.3 MB/s possibly metered link; power cuts happen. Keep jobs resumable, state download sizes first. Stop the platform (`docker compose stop`) before heavy notebooks. pandas 3: avoid `groupby().agg(nunique)` on strings (very slow).
- Docker Desktop on Windows can show bind-mounted file edits to containers with a delay: after editing backend code, wait/check (`MSYS_NO_PATHCONV=1 docker exec agri_backend grep … /app/app/...`) before running one-off scripts. Git Bash rewrites leading-slash args and env values (use `MSYS_NO_PATHCONV=1`, `MSYS2_ENV_CONV_EXCL`).
- Bash heredocs with nested quotes break here → write helper scripts with the Write tool. Use `python -I -X utf8` for scripts that print Unicode.

## 5. How to Run / Build / Deploy
- Start Docker Desktop first. Platform (from `docker/` so the override with local ports is loaded):
  `cd docker && docker compose up -d --build` → http://localhost ; stop: `docker compose down` (or `stop`/`start`).
- Local ports: nginx 80, frontend 5173, backend **8002**→8000, postgres **5434**→5432 (`docker/docker-compose.override.yml`, git-ignored via `.git/info/exclude`). Compose `name: smartagriculturedataplatform` keeps the DB volume.
- Env files: copy sections of `env/.env.example` into `env/.env.db` and `env/.env.backend`. Names: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_HOST, POSTGRES_PORT, DATABASE_URL, APP_ENV, LOG_LEVEL, SECRET_KEY, ENCRYPTION_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, ADMIN_EMAIL, ADMIN_PASSWORD, CORS_ORIGINS, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_IDS, IMAGES_DIR, LAND_MONITOR_INTERVAL_MINUTES, AI_AUTO_ANALYZE_HOURS, AI_INSIGHT_STALE_HOURS. Frontend: VITE_GOOGLE_CLIENT_ID (optional).
- Tests: `docker exec agri_backend python -m pytest app/tests/lands -q` (16 pass); full suite = 325 pass / 45 fail / 2 errors (all pre-existing). Frontend: `docker exec agri_frontend npx vitest run` (3 pass), `npm run build`; lint inside the container (host has no eslint).
- Dataset pipeline: `cd ml/research` then `.venv\Scripts\python.exe stepN_*.py` (see `ml/research/README.md`).
- EDA: `conda env create -f ml/eda/environment.yml`, open `ml/eda/eda.ipynb` with "Python (ghait)". Runs ~10 min, needs ~3 GB RAM.
- Prepare data: `ml/models/01_prepare_data.ipynb`, kernel `ghait` (same env, no extra packages); ~1.5 min, ~1.5 GB RAM (both seasons in memory). Built by a nbformat builder script (scratchpad, not in repo), run with `jupyter nbconvert --execute --inplace --ExecutePreprocessor.kernel_name=ghait`.
- Gotchas: localhost:8002 is currently captured by a WSL relay (wslrelay.exe) → use the API via http://localhost/api/... ; if Docker Desktop is closed everything fails with `dockerDesktopLinuxEngine` pipe error.

## 6. Decisions Log
| Date | Decision | Why | Alternatives rejected |
|---|---|---|---|
| 10-05 | Labels = FAO WaPOR ZAN + SGZ | real ground truth, 10 m, CC BY | Mallawi (legend ≠ file codes) |
| 10-05 | Imagery via Planetary Computer | platform already uses it | Google Earth Engine |
| 10-05 | Admin created from ADMIN_EMAIL/ADMIN_PASSWORD env | no passwords in repo | seeded accounts |
| 10-06 | ~1M samples as many small spatial blocks | TA requires a large dataset | fewer, larger fields |
| 10-06 | Orbit 21 only | covers both regions every 5 days | orbit 64 (clips ZAN corner, double obs) |
| 10-06 | Spatial 2 km block splits, 5 folds | neighbouring pixels leak | random pixel split |
| 10-06 | No gap-filling in stored arrays; CSVs gap-filled linearly | keep raw honest; `dataset.fill_gaps` (incl. causal) for experiments | mean/median fill |
| 10-07 | Deep models on Google Colab | no NVIDIA GPU | local GPU |
| 10-0x | One combined EDA notebook for all 5 sets | one dataset, compare regions/years | 5 separate EDAs |
| 10-0x | Remove `label_doubt` classes (SGZ W2324 orchards, medicinal_plants; SGZ S2024 built_up, bare_soil) | curves contradict names (e.g. "orchards" bare in winter) | keep them |
| 10-0x | Remove classes <2000 samples per region×season (9 classes, 3,276) | too few to train/score | merge into "other" |
| 10-0x | Outliers: IQR (data bimodal, not normal); treatment Ignoring | 96.6% of GNDVI outliers = water (real signature) | remove/cap/impute |
| 10-0x | Keep interpolated values (`n_clear`=0, 6–27%) | gradual growth; time-aware fill beats column mean | mean/median |
| 10-0x | Platform: remove About, Methodology, chatbot, soil moisture, irrigation UI | not needed, simpler UX | keep |
| 10-0x | Land marking = "place a square and drag corners" + polygon drawing | easier for farmers | circle/rectangle tools |
| 10-11 | Repo layout backend/frontend/docker/env/ml/docs; delete old team docs, mobile app, deploy workflows, root Dockerfile | clean, organised | keep |
| 10-11 | Platform runs from `docker/` folder | compose override auto-loaded there | root `-f` (skips override) |
| 10-18 | Research title "Early Time-Series Crop Classification in the Nile Delta" | contains early, time series, crop, classification, place | "Ghait …", shorter variants |
| 10-xx | Presentation diagram as `.excalidraw` (English labels) | editable on excalidraw.com; Arabic renders badly | Figma, hand-drawn |

## 7. Problems & Solutions (Bug Journal)
- **NDVI ~0.25 too low since 2022** — cause: L2A baseline ≥04.00 adds +1000 DN offset → fix: `boa_offset_dn()` per scene in `connectors/sentinel.py` (+ previews). Lesson: always check processing baseline.
- **Clouds looked like bare soil** — indices returned 0 for NaN pixels → keep NaN, medians ignore masked, skip dates with no clear pixels (`cv/indices.py`, `cv/ndvi.py`, pipelines).
- **Validator rejected fields near houses** — nearest OSM feature counted → only features containing the point (`lands/validator.py` `_point_on_feature`).
- **500 on another user's land / FK error on delete** → 404; delete provenance + declared-crop rows first (`lands/repository.py`).
- **Search box did nothing** — `<form>` nested in page form → `div` + Enter handler + `type="button"` (`MapDrawComponent.jsx`).
- **Polygon drawing stopped after 3 points** — leaflet-draw 1.0.4 `readableArea` bug with `showArea:true` → `showArea:false`.
- **Lands cards broken images** — StrictMode double effect revoked a shared cached blob URL → revoke only if not cached (`AuthenticatedImage.jsx`, `isImageBlobCached`).
- **EDA memory 4.5–6.6 GB** (categorical lost on concat) → add pyarrow (plain read 2.7 GB).
- **Moving `EDA/` failed (Permission denied)** — VS Code Jupyter kernel held the folder → move files individually, remove empty folder after kernel closed.
- **`.gitignore` `env/` and `ENV/` lines hid the new env folder** → removed; secrets still ignored by `.env.*`.
- **Research code pointed to `services/backend`** → `config.REPO = ROOT.parents[1]`, `sys.path` → `backend/` (`dataset.py`, `step3_build_dataset.py`).
- **DB looked empty after moving compose** — volume name follows compose folder → `name: smartagriculturedataplatform` in compose.
- **`docker compose -f docker/...` from root skips override** → run from `docker/`.
- **localhost:8002 returns nothing** — wslrelay.exe also listens on 127.0.0.1:8002 → use nginx `/api`; fix later by restarting WSL or changing port (not done).
- **Monitoring never refreshed lands** — (1) interval job first fires 24 h after start and the stack rarely runs 24 h; (2) the cycle crashed on every land: `ImportError: cannot import name 'run_sentinel_visual_fetch' from app.tasks.satellite_task` (function lives in `sentinel_task`). Fix: run at startup + correct import. Lesson: check scheduler logs after any refactor.
- **Weather gap after catch-up** — refresh fetched only the last 7 days. Fix: reach back to the last stored day (≤120).
- **New NDVI points hidden** — monitoring stores field-level rows (`zone_id` NULL) but the default series returned only the primary zone. Fix in `lands/service.py`.
- **Compare title invisible** — gradient text with undefined CSS var → transparent; use a solid colour.
- **Platform down after reboot** — Docker Desktop closed → start Docker Desktop, then `docker compose up -d`.
- Failed approaches (don't retry): bulk `rm -rf`/`git rm` was blocked by the auto-mode safety classifier until the user approved; heredocs with nested quotes in bash.

## 8. Changelog
- `2026-11-12`: platform redesign started (user: page by page, look only, all operations unchanged, Egyptian Delta farming identity, nothing that looks AI-made). Page 1 Dashboard mockup published, NOT implemented yet, awaiting approval: https://claude.ai/artifact/4AghuzSHPEtsa2yXbLrZks (source in session scratchpad `delta-dashboard.html`). Identity "silt, clover and wheat": tokens silt #3a2b1f (sidebar/ink), clover #2f6b3a (primary), leaf #7fa24a, wheat #c9a227 (one highlight per screen), Nile #2e6f8e (water/NDWI), ground #f2f4ee, cards white, dark theme defined; fonts Readex Pro (headings, numbers) + IBM Plex Sans Arabic (text); motif = aerial Delta parcel mosaic + canal line (canvas, seeded); rules: flat colour, no gradients/glow/purple/emoji, feddan first then ha, Coptic farming month + proverb on the dashboard (e.g. هاتور أبو الدهب المنتور; 12 Nov 2026 = 3 Hatour 1743). Dashboard changes proposed: plain greeting + month card, KPI row (lands, area feddan/ha, newest NDVI, season progress), NDVI chart with land chips (any land, not only the first), status donut → plain counts, lands table (area feddan, NDVI bar, image date, status). v2 (same link) adds real photographs of Egyptian farmers, all Wikimedia Commons, Wiki Loves Africa Egypt, CC BY-SA 4.0 (credit line required): "A farmer works in his field, cleaning the weeds..jpg" (Evon2023, Oct–Jan sowing, shown in Hatour), "Donkey and Farmer.jpg" (Mona Hassan Abo-Abda, Jan–Apr), "Egyptian farmer during wheat harvest season.jpg" (Ahmed Flex777, Apr–May), "Wheat harvest in Egypt.jpg" (Doaa Adel, May–Jun), "Rice planting 1.jpg" (Doaa Adel, Jun–Aug), "Rice harvest 4.jpg" (Doaa Adel, Aug–Oct); 640 px previews in session scratchpad `photos_raw/` (p8, p9, p1, p3, p5, p6). Month panel = photo of the current Coptic month with a flat silt band (month + proverb). For the real build, download larger versions into `frontend/src/assets/photos/` and keep the credit line. Planned page order: Dashboard → My lands → Add land → Land detail → Compare → Profile → Activity log → Login/Register.
- `2026-11-12`: **land detail page rebuilt** (user approved): order = header (name, status, description, coords, ha·feddan, last satellite image, stale-data warning >20 days) → season picker (Nile Delta seasons, winter 1 Oct–31 May, summer 1 May–31 Oct, newest with data by default, "now" tag, obs count) → crop card (confirmed crop or rule-based estimate labelled temporary + confirm button) → crop growth (NDVI + NDWI for the season, latest and peak) → satellite map + season images → weather and water need (season summary + one daily chart) → soil (compact) → one sources line. Removed: AI analysis, key-metric cards, mini NDVI bars, crop zones, crop intelligence (health score + harvest prediction), est. yield, 365-day climate/water card lists, time-range filter, per-section source lines and trust badges, DVI/SAVI/EVI/GNDVI chart lines. Mobile tabs: Crop, Satellite, Weather & soil. New files `frontend/src/features/land-detail/LandSeasonPicker.jsx`, `LandCropCard.jsx`, `LandGrowthSection.jsx`, `LandWeatherSection.jsx`, `LandSoilCard.jsx`; rewritten `landDetailUtils.jsx`, `hooks/useLandDetail.js`, `pages/lands/LandDetailsPage.jsx`, `LandSatelliteSection.jsx`, header + mobile nav edits; deleted `LandAiInsightsSection`, `LandMetricsSection`, `LandCropsSection`, `LandWaterSection`, `LandEnvironmentSection`, `LandTimeRangeFilter`, `components/charts/VegetationChart.jsx`; CSS in `pages/Lands.css` (old time-filter block removed, new block appended).
- `2026-11-12`: compare page: health score replaced by latest NDVI + date, crop marked "(estimate)", area with feddan, invisible title fixed (gradient used undefined `--blue-600`), top bar title "Compare Lands" → `pages/compare/CompareLandsPage.jsx`, `CompareLands.css`, `components/layout/Topbar.jsx`
- `2026-11-12`: monitoring fixed → `backend/app/scheduler/runner.py` (land_monitoring also runs at startup via `next_run_time`), `backend/app/pipeline/land_monitoring_pipeline.py` (import `run_sentinel_visual_fetch` from `sentinel_task`; weather catch-up reaches back to last stored day, max 120 days), `backend/app/lands/service.py` (default crops series = primary zone rows + newer field-level rows, `zone_id` per row)
- `2026-11-12`: land detail page reviewed (read-only), plan proposed; scheduler startup gap found → `mind.md`
- `2026-11-12`: removed the Groq "AI Agronomist / Deep Intelligence" panel from the dashboard (user request) and its AI state/calls from the hook; lint + build clean, dashboard verified in browser (0 errors). AI CSS kept: still used by `LandAiInsightsSection.jsx` → `frontend/src/pages/DashboardPage.jsx`, `frontend/src/hooks/useDashboard.js`
- `2026-11-12`: old name removed: notebook titles → research title (`ml/eda/eda.ipynb`, `ml/models/01_prepare_data.ipynb`), README title, diagram title/subtitle, `docs/ghait_diagram.excalidraw` → `docs/nile_delta_diagram.excalidraw` (git mv). Conda env/kernel name `ghait` left as is (only an env name).
- `2026-11-12`: reviewed `ml/models/features.py` + `01_prepare_data.ipynb`; findings recorded in §9 → `mind.md`
- `2026-11-10`: Arabic explanation of the phase written; notebook label fix (B05 grouped with visible bands by correlation) → `ml/models/01_prepare_data_explained.md`, `ml/models/01_prepare_data.ipynb`
- `2026-11-10`: preprocessing + feature engineering phase done (uncommitted) → `ml/models/features.py`, `ml/models/01_prepare_data.ipynb`, `ml/models/data/{meta.parquet,prep.json}`
- `2026-11-10`: whole project re-read; raw-array check; preprocessing + feature engineering plan proposed → `mind.md`
- `2026-10-28`: final modelling plan written (replaces the first proposal) → `mind.md`
- `2026-10-28`: mind.md corrected: TA folder is `Desktop/advisor/` (outside repo), not `ml/advisor/`; modelling plan proposed → `mind.md`
- `2026-10-28`: created `mind.md` (this file) → `mind.md`
- `2026-10-2x`: user removed the author line ("**Mohamed Ismail**") from the notebook title (uncommitted) → `ml/eda/eda.ipynb`
- `2026-10-11` `b92049f`: deleted old team docs, `packages/` (mobile), `frontend/android`, capacitor config, `.github/workflows`, root `Dockerfile`, `tests/system`, `scripts/`, `rebuild.ps1`, `backend/test.db`, `backend/app/test_stac.py`
- `2026-10-11` `27a754f`: reorganised folders; compose paths/`name`; `.gitignore`; short README; research paths → `docker/`, `env/`, `ml/`, `README.md`, `ml/research/config.py`, `dataset.py`, `step3_build_dataset.py`, `ml/research/README.md`
- `2026-10-11` `26cffb9`: map locator bar (governorates, AR/EN search, my location, coordinates), "Mark my field" + "Draw corners", feddan; removed About/Methodology pages, chatbot (`AIChatPanel`), soil-moisture/irrigation UI, AI hint + tracking options on Add Land; Lands page place label + area; plain validator messages; `LandListItem.description`; AuthenticatedImage fix; EDA notebook + env; diagram → `frontend/src/**`, `backend/app/lands/*`, `ml/eda/*`, `docs/ghait_diagram.excalidraw`
- `2026-10-07` `7cc980b`: dataset pipeline `ml/research/*`
- `2026-10-05` `afb93cf`, `db42877`, `3b81cc8`, `b75cac5`, `79e40b7`: cloud-NaN fix, reflectance offset, validator, 404/delete fixes, admin from env, team page removed, fork detached from team services, `.env.example`
- Outside git: A-to-Z reference doc (Claude Doc, Arabic) https://claude.ai/code/artifact/7e41d75f-7b86-42c9-9b70-c6f1075a8341 — still has old paths and pre-cleaning numbers.

## 9. Current State
- ✅ Done: dataset (1,074,827 samples); EDA notebook (clean = 978,660 samples, 14 classes); preprocessing + feature engineering (`ml/models/01_prepare_data.ipynb`, `features.py`); platform UX simplification; repo reorganisation + cleanup; presentation diagram; research title chosen.
- 🚧 In progress: nothing mid-edit. Commits `26cffb9`, `27a754f`, `b92049f` are **local only (not pushed)**. `ml/eda/eda.ipynb` (author line removed), `mind.md` and `ml/models/` are uncommitted.
- Findings of the prep notebook to carry into modelling: whole-season interpolation would put later-dekad info into 18–25% of gaps once k ≥ 9 → always truncate before fill; `peak_dekad` partly follows cloud gaps (SGZ winter wheat 72% peak at d14 vs ZAN 43%) → test phenology on val macro-F1 AND cross-region; B06/B07/B08/B8A r 0.97–0.995 kept (separate measurements), revisit with LightGBM importance; roads weight 28.7 (1,197 train).
- Review of `ml/models` on 2026-11-12 (read-only, nothing changed): pipeline correct (splits leak-free, cut-then-fill, train-only weights and scaling, indices never NaN when bands are finite so `fill` checking channel 0 is valid, outputs git-ignored by `data/`). Points for `02`+: (a) notebook title still says "Ghait:" → use the research title (ask); (b) `truncate` copies the whole array (~0.6 GB winter) → in model notebooks select the split first and slice `C[:, :k]` for per-k models; (c) RF per-k: `fill(C[:, :k])` instead of carrying the last value into hidden dekads; (d) roads weight 28.7 on 1,197 samples → also try sqrt-balanced weights; (e) 5-fold block CV only on folds 1–4 (fold 0 = test); (f) cross-year: same SGZ pixels exist in S2023 and S2024 → train on S2023 train blocks, test on S2024 test blocks only; (g) cross-region on shared classes only; (h) scikit-learn and LightGBM not installed in `ghait` yet.
- Readiness check 2026-11-12 (all PASS): both notebooks 0 errors and run top to bottom; 978,660 ids in clean_samples = meta.parquet; no block/pixel in two splits; fold 0=test, 1=val, 2–4=train; classes, y codes, class weights (recomputed from train), 336/252 feature names and 14 positive std per season all consistent. Colab upload set = 5 `.npz` + `samples.parquet` = 0.87 GB.
- Platform tour 2026-11-12 (headless browser, all pages): no console errors, no API 4xx/5xx. Findings: (1) Compare page shows top-bar title "Land Details" and its page title is not visible; (2) land detail opens on "Past month" with no records → all metrics "—" (last records older; 58 all-time); (3) no maximum land area: test land "Gharbiyya Governorate Farm" = 17,251 ha accepted; (4) test lands in DB: Zankalon test field (3.4 ha, description "E2E check"), Asyut Farm (14.9 ha) and suhag (8.3 ha) are outside the Delta, Gharbiyya (17,251 ha); (5) rule-based crop guess says "Corn" for the Zankalon field in winter with 45 days to harvest → wrong, to be replaced by our model; (6) Groq AI parts still visible: dashboard "Deep Intelligence", detail "AI Analysis", profile "AI API Keys"/"AI KEYS" (no key set); (7) brand shown as "AgriData Egypt".
- Land detail page review 2026-11-12 (Zankalon test field, "All time"; 14 blocks, ~3,300 lines in `pages/lands/LandDetailsPage.jsx` + `features/land-detail/*`): (1) same info repeated: NDVI in metric card + 6-line chart + 12-bar mini chart + zone cards + health; crop in metric card + banner + zones + intelligence; (2) unreliable/wrong outputs: "Corn" for the whole year although the curve shows a winter crop (peak Mar, cut May) then a summer crop, "Alfalfa" zone (not one of our classes), both zones same harvest 27 Dec→3 Jan, health 100 "dense canopy… flooding", Est. Yield always "—", "Current NDVI" is 2 months old; (3) the whole year is treated as one crop (no seasons); (4) time filter applies to some sections only, default "Past month" empty; (5) data stale (NDVI 16 Sep, weather 3 Oct) because `scheduler/runner.py` interval jobs first fire 24 h after start and the platform never runs 24 h → needs a run at startup; (6) noise: source line under every section, trust badges, "E2E check" description in header, "You described this land as"; (7) 365 daily cards each for climate and water. New order (approved and DONE 2026-11-12, see changelog): header (+ last update) → crop card (rule estimate labelled temporary, later our model) → season NDVI curve (NDVI + NDWI, season selector) → satellite map + images → weather & water summary (small chart) → soil (compact) → one data-sources line. Remove: AI analysis, mini NDVI bars, crop composition zones, crop intelligence (health + harvest), est. yield, daily lists, per-section sources/badges. Compare page also shows health score → align.
- Verification of the land detail work (2026-11-12): lint 0 errors on all changed files (1 old hook-deps warning), build OK, vitest 3/3, backend 325 pass / 45 fail / 2 errors = identical to before; headless browser: Zankalon page desktop (winter and summer 2026), phone width 390 px, compare, dashboard, lands → 0 console errors. Zankalon now has weather to 10 Nov 2026 with no gap and NDVI to 29 Oct 2026.
- **Scheduler container is STOPPED on purpose** (`docker compose stop scheduler`): its cycle re-downloads ~60 images of 3–4 MB per land (180-day lookback, then stores only new ones) and the test land Gharbiyya (17,251 ha) makes this very heavy on a metered link. Start again with `cd docker && docker compose start scheduler` after the test lands are deleted; consider fetching only dates not yet stored.
- Raw NetCDF save in the NDVI backfill logs "could not safely cast array from int64 to int32" (non-fatal, data stored).
- Rule-based crop estimate has no date and is not recomputed by monitoring (e.g. still "Corn" while the winter season shows bare soil); the crop card says it is temporary.
- 🐛 Known issues:
  - 45 old backend tests fail (pre-existing, e.g. tests register `role=admin`, old `insert_land_image(image_path=…)` signature, auth now required).
  - AI Insights section still shown; needs a Groq key or hiding (user undecided).
  - Unused backend code: chat, irrigation, soil moisture.
  - Nominatim misses small villages in Arabic ("زنكلون" 0 results, "zankalon" 5). "My location" not auto-tested.
  - Pre-existing frontend lint errors (no new ones added).
  - localhost:8002 captured by WSL relay.
- ⚠️ Fragile: `research/data` (12.6 GB, not backed up); `boa_offset_dn` and `cv/indices.py` are shared by platform and research — change both or neither; leaflet-draw 1.0.4 quirks; compose must run from `docker/`; the user's VS Code Jupyter kernels can lock `ml/eda/`.
- Side projects (outside this repo, out of scope): `Desktop/Crop Land Cover EDA` (LUCAS EDA), `Desktop/FIFA Player Value EDA` (FIFA 22/23 EDA, kernel "Python (crop-eda)").

## 10. Next Steps
0. **Next (user order 2026-11-12): platform clean-up first, then models.** Done: dashboard AI panel removed, land detail rebuilt, compare page fixed, monitoring fixed. Still open (ask the user): delete test lands (proposed: Gharbiyya 17,251 ha, Asyut, suhag; keep Zankalon), then restart the scheduler; add a max land area (proposed 500 ha); remove remaining Groq AI parts (profile AI keys + backend `ai` module + scheduler AI job); remove unused backend chat/irrigation/soil-moisture and health/harvest code; fix or delete the 45 old failing tests; brand name; make the satellite fetch skip dates already stored. Then models on Colab.
   - **Decision 2026-11-12: every model is trained on Google Colab** (user: faster, fewer problems). So no scikit-learn/LightGBM install locally. Colab bundle needed: 5 `.npz` + `samples.parquet` (0.87 GB) + `ml/models/features.py`, `ml/research/dataset.py`, `ml/research/config.py`, `backend/app/cv/indices.py` (dataset.py imports it), `ml/models/data/meta.parquet`, `prep.json`, `ml/eda/clean_samples.csv`, uploaded to Google Drive.
   - Models: floor (nearest class-mean, not trained) + 4 trained (RF, LightGBM, MiniRocket, LSTM) + Chronos-2 (pretrained forecaster, used zero-shot) = 6 in the comparison.
1. Final modelling plan written on 2026-10-28 (see "Final modelling plan" below), awaiting the user's approval; then start `ml/models/01_prepare_data`. TA material lives outside the repo at `Desktop/advisor/` (moved by the user; only the 4 Foundations files, nothing on modelling yet).
2. Modelling: features from cleaned CSVs (5 indices × dekads), use existing `split`/`fold`; RF → LightGBM → MiniRocket → LSTM (Colab); early-classification curves; cross-region and cross-year tests; Chronos-2 forecast-then-classify. Score with macro-F1.
3. Pending user decisions: push the 3 local commits; commit `mind.md` + notebook change; validator fix (reject land only when MODIS actually returned NDVI values — proposed, not approved); add a `df.columns` cell to `eda.ipynb` (proposed); AI Insights: hide or add Groq key; old failing tests: delete vs fix; remove unused backend chat/irrigation/soil code.
4. Suggested: back up `ml/research/data/dataset/`; update the A-to-Z doc with new paths and cleaning numbers; fix localhost:8002 (WSL).
5. Finally: replace `crops/identification.py` / `ml/crop_classifier.py` with the trained model in the platform.

**Preprocessing + feature engineering plan (2026-11-10, approved and done; first phase of the modelling plan)**
- Facts checked 2026-11-10 on the raw dekad arrays of the clean samples: 0 samples fully missing; missing dekads 6.2–26.9% per set; 4 dekads are 100% empty (ZAN W2324 d7, ZAN S2024 d14, SGZ S2024 d14, SGZ S2023 d1); first dekad missing 34–40% in winter, 100% in SGZ S2023; reflectance >1.0 ≈ 0% (max 1.54) → no treatment. Split = fold 0 test, fold 1 val, folds 2–4 train. TA slides (`Desktop/advisor/Data Foundations.pdf`) end at outliers + transformations; nothing on feature engineering. Neither env has scikit-learn/LightGBM yet.
- Deliverables: `ml/models/features.py` (numpy-only, reused by every model notebook and later by the backend) + `ml/models/01_prepare_data.ipynb` (TA style) + small outputs in `ml/models/data/` (git-ignored): `meta.parquet` (sample_id, region, season, crop, y, split, fold, block_id) and `prep.json` (class list per season, channel/feature names, train-only scaling stats, balanced class weights). No big feature arrays saved; features are built from the `.npz` on the fly.
- Preprocessing: keep the 978,660 clean ids; existing splits (check no pixel crosses splits); NaN kept in storage; fill rule = "truncate first, then fill" (`dataset.fill_gaps` on the first k dekads only, leak-free) for RF/MiniRocket/LSTM, LightGBM gets NaN; label encoding per season (winter 9, summer 9 classes); standardisation per channel fit on train only (LSTM/MiniRocket only); balanced class weights; no log/Box-Cox/Yeo-Johnson (trees don't need it, indices bounded). Not used: `n_clear`, region, lat/lon, `weight` (would hurt transfer or leak space).
- Feature engineering: 14 channels = 10 bands + NDVI, NDWI, GNDVI, EVI (SAVI dropped); two layouts: sequence [N, T, 14] and flat T×14 named like `ndvi_d05`; `truncate(X, k)` for early classification; candidate phenology features (NDVI/NDWI max, dekad of max, min, mean, std, largest rise), computed on the seen window only, kept only if LightGBM val macro-F1 rises in `02`.

**Final modelling plan (2026-10-28, awaiting user approval)**
- Data facts behind it: clean train/val/test = winter 278,799 / 90,724 / 89,978, summer 309,361 / 103,965 / 105,833. 72,231 pixels appear in 2 seasons, always in the same split (no cross-season leak). Region-only classes: winter flax, beans (SGZ), orchards, vegetables (ZAN); summer orchards, roads (ZAN), bare_soil (SGZ); cotton only 6,767 in ZAN, vegetables only 4,228 in SGZ → cross-region tests use shared classes only. Only SGZ has two summers (cross-year).
- Platform facts: `connectors/sentinel.py` fetches only B02,B03,B04,B08,B11 at 0.0001° (EPSG:4326) for the last 90 days → serving needs a new fetch path matching training (10 bands, UTM 10 m grid, season start → today, same SCL mask + cloud screening + dekads).
- Unit and input: pixel × season; one model per season (winter 24 dekads, summer 18). Input = dekadal composites from `.npz` (`dataset.load`), NaN kept, 14 channels = 10 bands + NDVI, NDWI, GNDVI, EVI (SAVI dropped, r=0.995 with EVI). Not the CSV (no bands, gap-filled with future values). No hand-made features unless they raise validation macro-F1.
- Models: (0) nearest class-mean floor; (1) Random Forest, classic reference, 100k-sample train subset (memory); (2) **LightGBM, main production candidate**: NaN-native, trained with random-truncation augmentation (dekads after k set to NaN) so one model per season answers at any date; (3) MiniRocket, time-series specialist comparison, Colab or ~60k subset (10k features/sample); (4) **LSTM with a prediction at every dekad**, deep candidate, Colab GPU, export ONNX; (5) Chronos-2 forecast-then-classify, research experiment on a test subset, Colab, not served.
- Rejected: XGBoost/CatBoost (same family as LightGBM), SVM/KNN (do not scale to ~300k × 336), TempCNN/Transformer (one deep model is enough; LSTM gives early outputs per step), image CNNs (we have pixels, not patches).
- Training rules: tune on val (or 5-fold block CV via `fold`), test opened once in the final notebook; class-balanced weights; LightGBM early stopping; RF depth/leaf limits; LSTM dropout, weight decay, early stopping, cloud-dropout augmentation; scaling fit on train only (LSTM, MiniRocket); causal gap filling for any truncated input; learning curves to watch the train-val gap.
- Metrics: macro-F1 (main), accuracy, per-class F1, confusion matrix; early curve (macro-F1 vs dekads seen); cross-region ZAN↔SGZ; cross-year SGZ S2023→S2024 (transfer only for LightGBM and LSTM).
- Choice for the platform: best cross-region macro-F1 at mid and full season, then early curve, then serving cost; if LSTM beats LightGBM only marginally, LightGBM wins.
- Integration: move the cloud screening + dekad compositing code into one shared module used by research and backend; new backend inference service: field polygon → per-pixel 14-channel dekads → model → majority vote with mean probability → crop + confidence + dekads seen; low confidence → "uncertain"; non-crop classes flag non-farmland.
- Notebooks (no new EDA per model; EDA is done once): `ml/models/01_prepare_data`, `02_classic_models` (floor, RF, LightGBM, early), `03_minirocket`, `04_lstm` (Colab), `05_chronos_forecast` (Colab), `06_final_evaluation` (test once, transfer, choose + export).

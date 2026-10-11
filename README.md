# Ghait - Smart Agriculture Data Platform

Crop type classification for the Nile Delta from Sentinel-2 time series, with a web platform where a farmer marks a field on the map and follows it.

## Project structure

```text
backend/     FastAPI application (API, lands, satellite pipeline, scheduler)
frontend/    React + Vite web application
docker/      docker-compose files, nginx proxy, postgres image and SQL
env/         environment files (.env.example is the template; real files are not committed)
ml/
  research/  scripts that build the dataset from Sentinel-2 and FAO WaPOR labels
  eda/       EDA and cleaning notebook
docs/        project diagram
```

## Run the platform

Requires Docker Desktop.

1. Copy the two sections of `env/.env.example` into `env/.env.db` and `env/.env.backend` and fill in the values.
2. From the `docker` folder:

```powershell
cd docker
docker compose up -d --build
```

3. Open http://localhost

Stop it, from the same folder, with:

```powershell
docker compose down
```

Services: `agri_nginx` (proxy, port 80), `agri_frontend` (Vite), `agri_backend` (FastAPI, port 8000), `agri_scheduler` (periodic land monitoring), `agri_postgres` (PostgreSQL).

## Machine learning

- Dataset pipeline: see `ml/research/README.md`.
- EDA: create the environment with `conda env create -f ml/eda/environment.yml`, then open `ml/eda/eda.ipynb` with the `ghait` kernel.

FROM postgres:14

# Init scripts are mounted via docker-compose into
# /docker-entrypoint-initdb.d/ — PostgreSQL runs them automatically
# on first container start in alphabetical order.
#
# Environment variables (POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD)
# are supplied by .env.db via docker-compose.

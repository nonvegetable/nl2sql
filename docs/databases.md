# Databases

The engine accepts SQLAlchemy URLs and exposes adapter-shaped connection operations through the API. SQLite works without an external driver; PostgreSQL, MySQL/MariaDB, and SQL Server use optional driver groups in `pyproject.toml`. Oracle and BigQuery remain provider integration targets and are not claimed as tested desktop support yet.

Connection metadata is separated from engine instances, which enables per-connection pools and prevents schema/vector context from being shared accidentally in future persistence implementations.

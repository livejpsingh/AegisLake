# 🐳 Local Infrastructure & Services Guide

AegisLake works alongside local Docker container services that provide Lakehouse query capabilities, observability, and metric aggregation.

---

## 1. Running Docker Services Summary

| Container Name | Image | Port | Local URL | Role |
| :--- | :--- | :---: | :--- | :--- |
| **`minilake`** | `ghcr.io/dmux/minilake:latest` | `8000` | [http://localhost:8000/ui/](http://localhost:8000/ui/) | Lakehouse Explorer UI & DuckDB SQL Console |
| **`minilake-api`** | `ghcr.io/dmux/minilake:latest` | `8000` | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive OpenAPI / Swagger documentation |
| **`bitestream-grafana`**| `grafana/grafana:11.2.0` | `3000` | [http://localhost:3000](http://localhost:3000) | Operational Risk & Metrics Visualizer |
| **`bitestream-prometheus`** | `prom/prometheus:v2.54.1` | `9090` | [http://localhost:9090](http://localhost:9090) | Time-series metrics collection & monitoring |
| **`bitestream-loki`** | `grafana/loki:3.1.1` | `3100` | [http://localhost:3100](http://localhost:3100) | Distributed log aggregation engine |
| **`bitestream-promtail`** | `grafana/promtail:3.1.1` | — | Internal | Log shipping agent |

---

## 2. Accessing MiniLake

The **MiniLake** container exposes a lightweight web user interface for browsing parquet tables and running ad-hoc SQL queries:
- **Web Console**: [http://localhost:8000/ui/](http://localhost:8000/ui/)
- **Swagger API**: [http://localhost:8000/docs](http://localhost:8000/docs)

You can query your local parquet files directly via DuckDB from the command line or through the UI:
```python
import duckdb

con = duckdb.connect()
# Query the governed silver layer directly
df = con.execute("SELECT * FROM 'data/silver/transactions_governed.parquet' LIMIT 5").df()
print(df)
```

---

## 3. Monitoring with Grafana & Prometheus

- **Grafana**: Available at [http://localhost:3000](http://localhost:3000). Default credentials (if not customized): `admin` / `admin`.
- **Prometheus**: Available at [http://localhost:9090](http://localhost:9090). Shows scraping health, target endpoints, and active alert rules.

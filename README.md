# Fintech Risk Control & User Behavioral Analysis Engine

Production-grade local architecture for **Financial Risk Control and User Behavior Analysis**, emulating a cloud enterprise Lakehouse (Databricks + Snowflake) using an open-source **MiniLake (Delta/DuckDB) + Behavioral Feature Store + MLflow Model Registry** stack.

---

## 🏛️ Architecture Overview

```
[Raw Transactions] ──► [Bronze Parquet]
                             │
                             ▼
              [Silver Layer: Governed MiniLake]
              (Schema validation, Deduplication, SHA-256 PII masking)
                             │
                             ▼
              [Gold Layer: Behavioral Feature Store]
              (1h/24h/7d velocity, device hopping, amount volatility)
                             │
                             ▼
              [Risk Modeling & Metrics Suite]
              (Calibrated Risk Classifier, ROC-AUC, KS-Statistic, PSI)
                             │
                             ▼
              [MLflow Registry & Staging Lifecycle]
              (Candidate ──► Staging ──► Production)
                             │
                             ▼
              [Customer Risk Cockpit Dashboard]
              (Decile risk table, KS curves, automated policy decisions)
```

---

## 🚀 Quickstart: Running the Pipeline Locally

### 1. Execute the End-to-End Pipeline
```bash
python -m src.pipeline
```

### 2. Run the Automated Test Suite
```bash
pytest tests/ -v
```

### 3. View the Risk Operations Cockpit
Open `reports/risk_dashboard.html` in any web browser.

---

## 📊 Core Risk Control Metrics
- **Kolmogorov-Smirnov (KS) Statistic**: $\max |F_{\text{fraud}}(s) - F_{\text{good}}(s)|$ across score thresholds.
- **ROC-AUC**: Discriminative capability across entire sensitivity/specificity spectrum.
- **Population Stability Index (PSI)**: Monitors population shift between baseline and production scoring cohorts ($PSI < 0.1$ = Stable).
- **10-Decile Table & Lift**: Rank-ordering validation demonstrating risk concentration in top deciles.

---

## ⚙️ CI/CD Pipeline Architecture

The project features automated GitHub Actions workflows:

### 1. Continuous Integration (`.github/workflows/ci.yml`)
- **Triggers**: Pull requests and commits pushed to `main`/`master`/`develop`.
- **Jobs**:
  - `lint-and-syntax-check`: Static syntax inspection and flake8 verification.
  - `test-and-validate-pipeline`: Automated pytest test suite execution and end-to-end pipeline run, archiving the risk operations dashboard as a run artifact.

### 2. Continuous Deployment (`.github/workflows/cd.yml`)
- **Triggers**: Direct push to `main` or manual trigger via `workflow_dispatch`.
- **Execution Flow**:
  - ✅ **Basic CD (`basic-cd-deployment`)**: **Passed by default**. Executes staging artifact packaging, dependency check, and baseline smoke verification.
  - ⏭️ **Production Deployment (`production-deployment`)**: **Skipped by default**. Conditioned on explicit production dispatch or semver tag (`v*.*.*`).
  - ⏭️ **Cloud Lakehouse Replication (`cloud-lakehouse-sync`)**: **Skipped by default**. Syncs local Parquet to cloud storage when enabled.
  - ⏭️ **Canary Traffic Rollout (`canary-traffic-rollout`)**: **Skipped by default**. Handles 10% canary risk scoring model shifts.


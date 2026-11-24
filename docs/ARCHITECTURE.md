# 🏛️ AegisLake Engine Architecture & Design

AegisLake is a production-grade local Lakehouse and Risk Control Engine designed for **FinTech fraud mitigation, credit risk scoring, and temporal behavioral analytics**. It emulates enterprise cloud Lakehouses (such as Databricks and Snowflake) using an open-source, embedded, zero-overhead stack: **DuckDB**, **Delta/Parquet**, **Behavioral Feature Store**, and **MLflow Tracking & Model Registry**.

---

## 1. Medallion Lakehouse Architecture

The data pipeline adopts the industry-standard **Medallion Architecture** pattern:

```
┌─────────────────────────┐
│ Raw Synthetic Stream    │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Bronze Layer (Raw)      │ -> data/bronze/transactions.parquet
│ Immutable append-only   │    Preserves raw ingest records & raw timestamps
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Silver Layer (Governed) │ -> data/silver/transactions_governed.parquet
│ Cleansed & Masked       │    • Schema validation & deduplication
│                         │    • SHA-256 PII pseudonymization (Device & IP)
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Gold Layer (Feature)    │ -> data/gold/user_features.parquet
│ Temporal Behavioral     │    • Multi-window velocity (1h, 24h, 7d)
│ Feature Store           │    • Device hopping & amount volatility
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Model & Scoring Layer   │ -> data/gold/customer_risk_profiles.parquet
│ Machine Learning        │    • Calibrated Risk Classifier
│                         │    • Point-in-time train/val evaluation
└─────────────────────────┘
```

### Bronze Layer (`data/bronze/`)
- **Format**: Apache Parquet.
- **Responsibility**: Ingestion sink for streaming or batch raw events. Stores raw transaction attributes including unmasked IP addresses, device identifiers, amounts, and merchant categories.

### Silver Layer (`data/silver/`)
- **Governance & Validation**: Enforced via `src/data_governance/governed_lake.py`.
- **Deduplication**: Removes duplicated transaction IDs.
- **PII Masking**: Uses deterministic `SHA-256` hashing (truncated 16-hex characters) for sensitive identifiers (`masked_device_hash`, `masked_ip_hash`), ensuring GDPR/CCPA compliance.
- **Status Audit**: Appends metadata columns (`_governance_status`, `_ingested_at`).

### Gold Layer (`data/gold/`)
- **Behavioral Feature Store**: Managed via `src/feature_store/store_manager.py` and calculated in `src/feature_store/behavioral_features.py`.
- **Feature Catalog**: Feature schemas and definitions registered in `data/gold/feature_catalog.json` and `config/feature_definitions.yaml`.

---

## 2. Temporal Behavioral Feature Engineering

Risk control decisions rely heavily on behavioral velocity and deviation patterns across multiple sliding windows:

| Feature Name | Window | Description | Risk Signal |
| :--- | :---: | :--- | :--- |
| `txn_cnt_1h` | 1 Hour | Number of transactions within the trailing hour | Card testing / rapid fire bot attacks |
| `txn_cnt_24h` | 24 Hours | Number of transactions within trailing day | Unusual daily activity surge |
| `txn_cnt_7d` | 7 Days | Number of transactions within trailing week | Weekly baseline frequency |
| `txn_amt_sum_24h` | 24 Hours | Total transaction volume in trailing 24 hours | Cash drain / bust-out fraud |
| `txn_amt_avg_7d` | 7 Days | Baseline mean transaction amount over 7 days | Spending benchmark |
| `amt_to_avg_ratio` | Dynamic | Ratio of current amount to 7-day average | Outlier transaction sizing |
| `distinct_devices_7d` | 7 Days | Unique device fingerprints used in past 7 days | Device hopping / credential stuffing |
| `time_since_last_txn_sec` | Dynamic | Seconds elapsed since previous transaction | Inter-arrival velocity anomalies |

---

## 3. Risk Modeling & Validation Framework

### Model Engine (`src/models/model_trainer.py`)
- Employs an iterative, calibrated risk classifier with L2 regularization and sigmoid probability calibration:
  $$P(\text{Fraud} \mid X) = \sigma(W^T X + b) = \frac{1}{1 + e^{-(W^T X + b)}}$$
- Evaluated under point-in-time temporal splitting (80% train, 20% validation) to prevent data leakage.

### Statistical Validation Metrics (`src/models/risk_metrics.py`)
- **Kolmogorov-Smirnov (KS) Statistic**: Measures the maximum separation between cumulative fraud and non-fraud distributions:
  $$KS = \max_s |F_{\text{fraud}}(s) - F_{\text{good}}(s)|$$
  *Acceptance Gate: $KS \ge 35\%$ for production promotion.*
- **Area Under ROC Curve (ROC-AUC)**: Measures discrimination capability across all thresholds.
- **Population Stability Index (PSI)**: Monitors probability distribution shift between training and scoring populations:
  $$PSI = \sum_{i=1}^k (Actual_i - Expected_i) \times \ln\left(\frac{Actual_i}{Expected_i}\right)$$
  *$PSI < 0.10$ denotes population stability; $PSI \ge 0.25$ indicates significant drift requiring retraining.*
- **Decile Risk Table & Lift**: Partitions scored population into 10 risk bins to verify monotonic rank-ordering and top-decile fraud capture.

---

## 4. Model Governance & Lifecycle

Managed via `src/models/mlflow_registry.py`:
- **Tracking**: Logs hyperparameters, validation metrics (AUC, KS, PSI), and artifacts (`decile_table`, `feature_importances`).
- **Automated Staging Promotion**:
  - `Candidate`: Initial logged run.
  - `Staging`: Models satisfying minimum statistical criteria.
  - `Production`: Champion model promoted when $KS \ge 35\%$, archived if superseded.

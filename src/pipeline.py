"""End-to-End Production Pipeline Orchestrator.
Executes full lifecycle:
1. Synthetic transaction generation.
2. Governed MiniLake ingestion (Bronze -> Silver with PII Masking).
3. Behavioral Feature Store computation & registration (Gold).
4. Point-in-time train/val split & Risk Model Training.
5. Risk Metrics evaluation (AUC, KS, PSI, Decile table).
6. Local MLflow logging & Model Registry promotion.
7. Customer risk profiling & interactive report generation.
"""
import os
import numpy as np
import pandas as pd

from src.data_governance.synthetic_generator import generate_synthetic_transactions
from src.data_governance.governed_lake import GovernedMiniLake
from src.feature_store.behavioral_features import BehavioralFeatureExtractor
from src.feature_store.store_manager import LocalFeatureStore
from src.models.model_trainer import RiskModelTrainer
from src.models.risk_metrics import RiskMetrics
from src.models.mlflow_registry import LocalMLflowRegistry
from src.dashboard.report_generator import generate_risk_dashboard


def run_pipeline():
    print("=" * 65)
    print("🚀 FINTECH RISK CONTROL & BEHAVIORAL ANALYSIS PIPELINE")
    print("=" * 65)

    # 1. Generate Transactions
    print("\n[Step 1/7] Generating synthetic transaction data stream...")
    raw_df = generate_synthetic_transactions(num_users=250, num_transactions=4000, seed=42)
    print(f"-> Generated {len(raw_df)} transactions. Total fraud cases: {raw_df['is_fraud'].sum()}")

    # 2. Ingest to MiniLake (Bronze -> Silver)
    print("\n[Step 2/7] Ingesting to Governed MiniLake (Bronze -> Silver)...")
    minilake = GovernedMiniLake()
    minilake.ingest_to_bronze(raw_df)
    silver_df = minilake.process_to_silver()
    print("-> Silver table successfully written with SHA-256 PII masking.")

    # 3. Behavioral Feature Engineering (Feature Store - Gold)
    print("\n[Step 3/7] Computing temporal behavioral features (Feature Store)...")
    feature_df = BehavioralFeatureExtractor.extract_features(silver_df)
    feature_store = LocalFeatureStore()
    feature_store.register_feature_table(feature_df)

    # 4. Point-in-time Training Set Creation
    print("\n[Step 4/7] Generating point-in-time training and validation sets...")
    training_data = feature_store.get_training_dataset(silver_df)

    # Temporal split: 80% train, 20% validation
    split_idx = int(len(training_data) * 0.80)
    train_df = training_data.iloc[:split_idx]
    val_df = training_data.iloc[split_idx:]

    feature_cols = feature_store.feature_names
    X_train = train_df[feature_cols].values
    y_train = train_df["is_fraud"].values
    X_val = val_df[feature_cols].values
    y_val = val_df["is_fraud"].values

    print(f"-> Train samples: {len(X_train)} (Fraud: {int(y_train.sum())})")
    print(f"-> Validation samples: {len(X_val)} (Fraud: {int(y_val.sum())})")

    # 5. Model Training & Risk Evaluation
    print("\n[Step 5/7] Training calibrated Risk Classifier...")
    model = RiskModelTrainer(learning_rate=0.08, n_iterations=400, reg_lambda=0.05)
    model.fit(X_train, y_train, feature_names=feature_cols)

    train_probs = model.predict_proba(X_train)
    val_probs = model.predict_proba(X_val)

    eval_metrics = RiskMetrics.calculate_ks_and_auc(y_val, val_probs)
    decile_table = RiskMetrics.generate_decile_table(y_val, val_probs)
    psi_score = RiskMetrics.calculate_psi(train_probs, val_probs)
    eval_metrics["psi"] = psi_score

    print("\n" + "-" * 45)
    print("📈 RISK CONTROL MODEL PERFORMANCE:")
    print(f"  • ROC-AUC Score:      {eval_metrics['auc']:.4f}")
    print(f"  • KS Statistic:       {eval_metrics['ks_stat'] * 100:.2f}% (Threshold: {eval_metrics['ks_threshold']:.4f})")
    print(f"  • Population Drift PSI: {eval_metrics['psi']:.4f} (Status: {'STABLE' if eval_metrics['psi'] < 0.1 else 'DRIFT'})")
    print("-" * 45)

    importances = model.get_feature_importances()
    print("Top Feature Importances:")
    for feat, imp in sorted(importances.items(), key=lambda x: -x[1])[:5]:
        print(f"  - {feat:25s}: {imp:.4f}")

    # 6. MLflow Tracking & Registry
    print("\n[Step 6/7] Logging run and promoting to MLflow Model Registry...")
    registry = LocalMLflowRegistry()
    run_id = registry.log_run(
        run_name="production_fraud_model",
        params={"lr": 0.08, "iterations": 400, "reg_lambda": 0.05},
        metrics=eval_metrics,
        artifacts={"decile_table": decile_table, "feature_importances": importances}
    )
    reg_entry = registry.register_model_version(run_id, eval_metrics, min_ks_threshold=0.35)
    eval_metrics["version"] = f"v{reg_entry['version']}"
    eval_metrics["stage"] = reg_entry["stage"]

    # 7. Customer Risk Profiling & Dashboard
    print("\n[Step 7/7] Generating Customer Risk Profiles & Operations Cockpit...")
    val_df_scored = val_df.copy()
    val_df_scored["risk_score"] = val_probs

    def assign_policy(score):
        if score >= 0.70:
            return "DECLINE"
        elif score >= 0.40:
            return "MANUAL_REVIEW"
        return "APPROVE"

    val_df_scored["decision"] = val_df_scored["risk_score"].apply(assign_policy)
    
    # Save gold risk profile via DuckDB
    import duckdb
    gold_risk_path = "data/gold/customer_risk_profiles.parquet"
    con = duckdb.connect()
    con.register("_gold_df", val_df_scored)
    con.execute(f"COPY _gold_df TO '{gold_risk_path}' (FORMAT PARQUET)")
    con.close()

    report_path = "reports/risk_dashboard.html"
    generate_risk_dashboard(eval_metrics, decile_table, val_df_scored, output_path=report_path)

    print("\n" + "=" * 65)
    print("✅ PIPELINE EXECUTION COMPLETED SUCCESSFULLY!")
    print(f"  • Governed Silver:  data/silver/transactions_governed.parquet")
    print(f"  • Gold Feature Store: data/gold/user_features.parquet")
    print(f"  • MLflow Registry:  mlruns/model_registry.json")
    print(f"  • Risk Cockpit UI:  {report_path}")
    print("=" * 65)


if __name__ == "__main__":
    run_pipeline()

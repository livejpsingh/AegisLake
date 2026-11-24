"""Test Suite for Fintech Risk Control Pipeline."""
import numpy as np
import pandas as pd
import pytest

from src.data_governance.governed_lake import GovernedMiniLake
from src.data_governance.synthetic_generator import generate_synthetic_transactions
from src.feature_store.behavioral_features import BehavioralFeatureExtractor
from src.feature_store.store_manager import LocalFeatureStore
from src.models.risk_metrics import RiskMetrics
from src.models.model_trainer import RiskModelTrainer
from src.models.mlflow_registry import LocalMLflowRegistry


def test_synthetic_data_generation():
    df = generate_synthetic_transactions(num_users=20, num_transactions=100, seed=123)
    assert len(df) == 100
    assert "transaction_id" in df.columns
    assert "is_fraud" in df.columns
    assert df["amount"].min() > 0


def test_governance_pii_masking(tmp_path):
    lake = GovernedMiniLake(base_dir=str(tmp_path))
    raw_df = generate_synthetic_transactions(num_users=10, num_transactions=50, seed=42)
    lake.ingest_to_bronze(raw_df)
    silver_df = lake.process_to_silver()

    assert "masked_device_hash" in silver_df.columns
    assert "masked_ip_hash" in silver_df.columns
    assert "_governance_status" in silver_df.columns
    # Verify hash is pseudonymized (hex string length 16)
    assert len(silver_df["masked_device_hash"].iloc[0]) == 16


def test_behavioral_feature_extraction():
    raw_df = generate_synthetic_transactions(num_users=5, num_transactions=30, seed=99)
    raw_df["masked_device_hash"] = "mock_hash"
    raw_df["masked_ip_hash"] = "mock_ip"

    features_df = BehavioralFeatureExtractor.extract_features(raw_df)
    expected_cols = [
        "txn_cnt_1h", "txn_cnt_24h", "txn_cnt_7d",
        "txn_amt_sum_24h", "txn_amt_avg_7d", "distinct_devices_7d",
        "time_since_last_txn_sec", "amt_to_avg_ratio"
    ]
    for col in expected_cols:
        assert col in features_df.columns
        assert not features_df[col].isnull().any()


def test_risk_metrics_ks_and_auc():
    # Synthetic ground truth and probabilities
    np.random.seed(42)
    y_true = np.array([1] * 50 + [0] * 150)
    # Give higher probabilities to bads
    y_prob = np.concatenate([
        np.random.beta(5, 2, size=50),
        np.random.beta(1, 4, size=150)
    ])

    metrics = RiskMetrics.calculate_ks_and_auc(y_true, y_prob)
    assert 0.5 <= metrics["auc"] <= 1.0
    assert 0.0 <= metrics["ks_stat"] <= 1.0
    assert metrics["ks_stat"] > 0.35, "Model discrimination should exhibit positive KS separation"

    # Decile table check
    decile_df = RiskMetrics.generate_decile_table(y_true, y_prob, n_bins=10)
    assert len(decile_df) == 10
    assert decile_df["Lift"].iloc[0] > 1.0, "Top decile should have lift > 1.0"


def test_mlflow_registry_lifecycle(tmp_path):
    reg = LocalMLflowRegistry(tracking_dir=str(tmp_path / "mlruns"))
    run_id = reg.log_run("test_run", {"lr": 0.1}, {"auc": 0.88, "ks_stat": 0.52}, {})
    model_entry = reg.register_model_version(run_id, {"ks_stat": 0.52}, min_ks_threshold=0.40)

    assert model_entry["version"] == 1
    assert model_entry["stage"] == "Production"

    prod = reg.get_production_model()
    assert prod["version"] == 1

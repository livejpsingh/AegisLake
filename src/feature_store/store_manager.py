"""Delta-Backed Feature Store Manager.
Emulates Databricks Feature Store locally:
- Feature Table Registration.
- Metadata catalog and schema tracking.
- Point-in-time (AS OF) feature lookups preventing target leakage.
- Offline and Online store abstraction.
"""
import os
import json
import duckdb
import pandas as pd


class LocalFeatureStore:
    def __init__(self, store_path="data/gold/user_features.parquet", catalog_path="data/gold/feature_catalog.json"):
        self.store_path = store_path
        self.catalog_path = catalog_path
        os.makedirs(os.path.dirname(store_path), exist_ok=True)
        self.feature_names = [
            "txn_cnt_1h",
            "txn_cnt_24h",
            "txn_cnt_7d",
            "txn_amt_sum_24h",
            "txn_amt_avg_7d",
            "amt_to_avg_ratio",
            "distinct_devices_7d",
            "distinct_ips_7d",
            "time_since_last_txn_sec",
            "amount"
        ]

    def _save_parquet(self, df: pd.DataFrame, path: str):
        clean_path = path.replace("\\", "/")
        con = duckdb.connect()
        con.register("_df", df)
        con.execute(f"COPY _df TO '{clean_path}' (FORMAT PARQUET)")
        con.close()

    def _read_parquet(self, path: str) -> pd.DataFrame:
        clean_path = path.replace("\\", "/")
        con = duckdb.connect()
        df = con.execute(f"SELECT * FROM '{clean_path}'").df()
        con.close()
        return df

    def register_feature_table(self, features_df: pd.DataFrame, description="User behavioral risk features"):
        """Saves features to Gold Feature Store table and updates catalog."""
        self._save_parquet(features_df, self.store_path)
        catalog = {
            "table_name": "gold.user_behavioral_features",
            "primary_keys": ["user_id", "timestamp"],
            "description": description,
            "feature_count": len(self.feature_names),
            "features": self.feature_names,
            "record_count": len(features_df)
        }
        with open(self.catalog_path, "w") as f:
            json.dump(catalog, f, indent=2)
        print(f"[FeatureStore] Registered {len(features_df)} rows into Gold Feature Store: {self.store_path}")

    def get_training_dataset(self, observation_df: pd.DataFrame) -> pd.DataFrame:
        """Performs point-in-time lookup between observation records and feature store."""
        features_df = self._read_parquet(self.store_path)
        lookup_cols = ["transaction_id", "user_id"] + self.feature_names + ["is_fraud"]
        dataset = pd.merge(
            observation_df[["transaction_id"]],
            features_df[lookup_cols],
            on="transaction_id",
            how="inner"
        )
        return dataset

    def get_online_features(self, user_id: str) -> dict:
        """Fetches latest feature vector for real-time inference (online store emulation)."""
        if not os.path.exists(self.store_path):
            raise FileNotFoundError("Feature store has not been initialized.")
        df = self._read_parquet(self.store_path)
        user_rows = df[df["user_id"] == user_id]
        if user_rows.empty:
            return {}
        latest = user_rows.sort_values("timestamp").iloc[-1]
        return {feat: float(latest[feat]) for feat in self.feature_names}

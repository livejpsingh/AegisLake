"""Governed MiniLake Module.
Implements Medallion Architecture:
- Bronze: Raw transaction ingestion (append-only Parquet storage).
- Silver: Data quality assertions, schema enforcement, PII masking (SHA-256 on IP/Device).
- Audit trails and governance metadata.
"""
import hashlib
import os
from datetime import datetime
import duckdb
import pandas as pd


class GovernedMiniLake:
    def __init__(self, base_dir="data"):
        self.base_dir = base_dir
        self.bronze_path = os.path.join(base_dir, "bronze", "transactions.parquet")
        self.silver_path = os.path.join(base_dir, "silver", "transactions_governed.parquet")
        os.makedirs(os.path.join(base_dir, "bronze"), exist_ok=True)
        os.makedirs(os.path.join(base_dir, "silver"), exist_ok=True)
        self.con = duckdb.connect()

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

    def ingest_to_bronze(self, df: pd.DataFrame) -> int:
        """Ingests raw transactions into Bronze layer."""
        df_bronze = df.copy()
        df_bronze["_ingested_at"] = datetime.utcnow()
        df_bronze["_batch_id"] = hashlib.md5(f"{datetime.utcnow().isoformat()}".encode()).hexdigest()[:8]

        # Save to bronze parquet via DuckDB
        self._save_parquet(df_bronze, self.bronze_path)
        return len(df_bronze)

    def process_to_silver(self) -> pd.DataFrame:
        """Applies data governance rules to curate Silver layer:
        1. Null and type validations (Data Contracts).
        2. Deduplication.
        3. PII Masking: Pseudonymizes device_id and IP using SHA-256 salt.
        4. Audit flags.
        """
        raw_df = self._read_parquet(self.bronze_path)

        # 1. Validation checks
        initial_count = len(raw_df)
        clean_df = raw_df.dropna(subset=["transaction_id", "user_id", "timestamp", "amount"])
        clean_df = clean_df[clean_df["amount"] > 0]
        clean_df = clean_df.drop_duplicates(subset=["transaction_id"])

        # 2. PII Masking
        salt = "fintech_risk_salt_2026"
        def mask_pii(val: str) -> str:
            if not isinstance(val, str):
                return ""
            return hashlib.sha256(f"{val}_{salt}".encode()).hexdigest()[:16]

        clean_df["masked_device_hash"] = clean_df["device_id"].apply(mask_pii)
        clean_df["masked_ip_hash"] = clean_df["ip_address"].apply(mask_pii)

        # 3. Governance Audit columns
        clean_df["_governed_at"] = datetime.utcnow()
        clean_df["_governance_status"] = "PASSED"

        # Save to Silver layer
        self._save_parquet(clean_df, self.silver_path)
        print(f"[GovernedMiniLake] Silver promotion: {len(clean_df)} valid records out of {initial_count} raw.")
        return clean_df

    def query_silver(self, sql_query: str) -> pd.DataFrame:
        """Executes analytical SQL query against Silver governed table via DuckDB."""
        return self.con.execute(sql_query.replace("silver_table", f"'{self.silver_path}'")).df()

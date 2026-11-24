"""Export pipeline outputs into clean Power BI-ready datasets (Parquet + CSV).
Generates:
1. data/gold/powerbi_customer_risk_profiles.csv
2. data/gold/powerbi_decile_summary.csv
"""
import os
import duckdb
import pandas as pd

def export_powerbi_tables():
    con = duckdb.connect()
    
    # Check if gold profiles exist
    source_parquet = "data/gold/customer_risk_profiles.parquet"
    if not os.path.exists(source_parquet):
        print(f"File {source_parquet} not found. Run pipeline first.")
        return

    # 1. Export main scored transactions / profiles to CSV for direct Power BI drag-and-drop
    df_profiles = con.execute(f"SELECT * FROM '{source_parquet}'").df()
    csv_profiles_path = "data/gold/powerbi_customer_risk_profiles.csv"
    df_profiles.to_csv(csv_profiles_path, index=False)
    print(f"✅ Exported {len(df_profiles)} records to {csv_profiles_path}")

    # 2. Generate and export 10-decile summary table for Power BI visualization
    df_sorted = df_profiles.sort_values(by="risk_score", ascending=False).reset_index(drop=True)
    df_sorted["decile"] = pd.qcut(df_sorted.index, q=10, labels=[f"D{i}" for i in range(1, 11)])

    decile_summary = df_sorted.groupby("decile", observed=False).agg(
        min_score=("risk_score", "min"),
        max_score=("risk_score", "max"),
        total_count=("risk_score", "count"),
        fraud_count=("is_fraud", "sum"),
        total_amount=("amount", "sum"),
        fraud_amount=("amount", lambda x: x[df_sorted.loc[x.index, "is_fraud"] == 1].sum())
    ).reset_index()

    decile_summary["fraud_rate_pct"] = (decile_summary["fraud_count"] / decile_summary["total_count"]) * 100
    decile_summary["cum_fraud_pct"] = (decile_summary["fraud_count"].cumsum() / decile_summary["fraud_count"].sum()) * 100
    overall_fraud_rate = df_sorted["is_fraud"].mean()
    decile_summary["lift"] = decile_summary["fraud_rate_pct"] / (overall_fraud_rate * 100) if overall_fraud_rate > 0 else 1.0

    csv_deciles_path = "data/gold/powerbi_decile_summary.csv"
    decile_summary.to_csv(csv_deciles_path, index=False)
    print(f"✅ Exported decile metrics to {csv_deciles_path}")
    con.close()

if __name__ == "__main__":
    export_powerbi_tables()

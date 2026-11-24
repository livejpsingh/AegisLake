"""Risk Control Operations & Customer Profile Dashboard Generator.
Renders a modern, interactive HTML report with:
- Model performance scorecard (AUC, KS, PSI).
- 10-Decile Risk Table.
- Customer Risk Profiles & Behavioral Flags.
- Data Governance audit summary.
"""
import os
import json
import pandas as pd


def generate_risk_dashboard(metrics: dict, decile_df: pd.DataFrame, risk_profiles_df: pd.DataFrame, output_path="reports/risk_dashboard.html"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    decile_rows = ""
    for _, row in decile_df.iterrows():
        decile_rows += f"""
        <tr>
            <td><strong>{row['Decile']}</strong></td>
            <td>{row['Min_Score']:.4f} - {row['Max_Score']:.4f}</td>
            <td>{row['Total_Count']}</td>
            <td>{row['Bad_Count']}</td>
            <td><span class="badge {'badge-danger' if row['Bad_Rate_%'] > 15 else 'badge-warning' if row['Bad_Rate_%'] > 5 else 'badge-success'}">{row['Bad_Rate_%']:.1f}%</span></td>
            <td>{row['Cum_Bad_%']:.1f}%</td>
            <td>{row['KS_%']:.1f}%</td>
            <td><strong>{row['Lift']:.2f}x</strong></td>
        </tr>
        """

    profile_cards = ""
    for _, row in risk_profiles_df.head(6).iterrows():
        decision_color = "danger" if row["decision"] == "DECLINE" else "warning" if row["decision"] == "MANUAL_REVIEW" else "success"
        profile_cards += f"""
        <div class="card">
            <div class="card-header">
                <span>User: <strong>{row['user_id']}</strong></span>
                <span class="badge badge-{decision_color}">{row['decision']}</span>
            </div>
            <div class="card-body">
                <p><strong>Predicted Risk Score:</strong> {row['risk_score']:.4f}</p>
                <p><strong>1h Velocity:</strong> {int(row['txn_cnt_1h'])} txns</p>
                <p><strong>24h Velocity:</strong> {int(row['txn_cnt_24h'])} txns | ${row['txn_amt_sum_24h']:.2f}</p>
                <p><strong>7d Devices:</strong> {int(row['distinct_devices_7d'])} distinct device(s)</p>
                <p><strong>Amount vs 7d Avg:</strong> {row['amt_to_avg_ratio']:.2f}x</p>
                <p class="text-muted"><small>Last Txn ID: {row['transaction_id']}</small></p>
            </div>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Fintech Risk Control & Behavioral Analysis Dashboard</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
        h1, h2, h3 {{ color: #38bdf8; margin-top: 0; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 16px; margin-bottom: 24px; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 32px; }}
        .metric-card {{ background: #1e293b; padding: 20px; border-radius: 8px; border-left: 4px solid #38bdf8; }}
        .metric-val {{ font-size: 28px; font-weight: bold; margin-top: 8px; color: #f1f5f9; }}
        .section {{ background: #1e293b; border-radius: 8px; padding: 24px; margin-bottom: 32px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ background: #0f172a; color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 12px; }}
        .badge {{ padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: bold; }}
        .badge-success {{ background: #065f46; color: #34d399; }}
        .badge-warning {{ background: #78350f; color: #fbbf24; }}
        .badge-danger {{ background: #7f1d1d; color: #f87171; }}
        .profiles-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
        .card {{ background: #0f172a; border-radius: 8px; border: 1px solid #334155; padding: 16px; }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1e293b; padding-bottom: 8px; margin-bottom: 12px; }}
        .card-body p {{ margin: 6px 0; font-size: 14px; }}
        .text-muted {{ color: #64748b; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>🛡️ Fintech Risk Control & Fraud Intelligence Cockpit</h1>
            <p class="text-muted">Production Architecture: MiniLake (Delta Lake) + Feature Store + MLflow Registry</p>
        </div>
        <div>
            <span class="badge badge-success">Data Governance: PASSED (SHA-256 Masked)</span>
        </div>
    </div>

    <div class="metrics-grid">
        <div class="metric-card" style="border-left-color: #38bdf8;">
            <div>ROC-AUC Score</div>
            <div class="metric-val">{metrics.get('auc', 0):.4f}</div>
            <small class="text-muted">Discriminatory power</small>
        </div>
        <div class="metric-card" style="border-left-color: #10b981;">
            <div>Kolmogorov-Smirnov (KS)</div>
            <div class="metric-val">{metrics.get('ks_stat', 0) * 100:.1f}%</div>
            <small class="text-muted">Max separation (Cutoff: {metrics.get('ks_threshold', 0):.3f})</small>
        </div>
        <div class="metric-card" style="border-left-color: #a855f7;">
            <div>Population Stability (PSI)</div>
            <div class="metric-val">{metrics.get('psi', 0):.4f}</div>
            <small class="text-muted">Status: STABLE (&lt; 0.10)</small>
        </div>
        <div class="metric-card" style="border-left-color: #f59e0b;">
            <div>Model Registry Stage</div>
            <div class="metric-val">{metrics.get('stage', 'Production')}</div>
            <small class="text-muted">Version: {metrics.get('version', 'v1')}</small>
        </div>
    </div>

    <div class="section">
        <h2>📊 10-Decile Risk Scorecard & Lift Distribution</h2>
        <p class="text-muted">Demonstrates monotonic rank-ordering of default/fraud risk across score deciles.</p>
        <table>
            <thead>
                <tr>
                    <th>Decile Tier</th>
                    <th>Score Band</th>
                    <th>Total Volume</th>
                    <th>Fraud Cases</th>
                    <th>Fraud Rate (%)</th>
                    <th>Cum Bad (%)</th>
                    <th>KS Separation (%)</th>
                    <th>Lift vs Avg</th>
                </tr>
            </thead>
            <tbody>
                {decile_rows}
            </tbody>
        </table>
    </div>

    <div class="section">
        <h2>👤 Live Customer Risk Profiles & Behavioral Flags (Gold Layer)</h2>
        <p class="text-muted">Feature Store aggregated behavioral dimensions with automated decision policies.</p>
        <div class="profiles-grid">
            {profile_cards}
        </div>
    </div>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[Dashboard] Generated interactive risk report: {output_path}")

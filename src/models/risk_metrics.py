"""Financial Risk Control Evaluation Metrics Engine.
Computes core fintech risk metrics:
1. Kolmogorov-Smirnov (KS) Statistic: Maximum separation between cumulative Good and Bad distributions.
2. ROC-AUC & PR-AUC.
3. Decile Risk Table: 10 binned risk tiers, Delinquency/Fraud rate, Cumulative Bad %, Lift.
4. Population Stability Index (PSI): Drift between baseline (training) and actual (production).
"""
import numpy as np
import pandas as pd


class RiskMetrics:
    @staticmethod
    def calculate_ks_and_auc(y_true: np.ndarray, y_prob: np.ndarray) -> dict:
        """Calculates KS Statistic and ROC-AUC without external library dependencies."""
        y_true = np.asarray(y_true, dtype=int)
        y_prob = np.asarray(y_prob, dtype=float)

        # Sort descending by predicted probability
        order = np.argsort(-y_prob)
        y_true_sorted = y_true[order]
        y_prob_sorted = y_prob[order]

        n_total = len(y_true)
        n_bad = np.sum(y_true == 1)
        n_good = n_total - n_bad

        if n_bad == 0 or n_good == 0:
            return {"ks_stat": 0.0, "ks_threshold": 0.5, "auc": 0.5}

        # Cumulative bad and good rates
        cum_bad = np.cumsum(y_true_sorted == 1) / n_bad
        cum_good = np.cumsum(y_true_sorted == 0) / n_good

        # KS statistic is max difference
        diff = np.abs(cum_bad - cum_good)
        ks_idx = np.argmax(diff)
        ks_stat = float(diff[ks_idx])
        ks_threshold = float(y_prob_sorted[ks_idx])

        # ROC-AUC calculation via trapezoidal rule
        # TPR = cum_bad, FPR = cum_good
        tpr = np.concatenate(([0.0], cum_bad))
        fpr = np.concatenate(([0.0], cum_good))
        if hasattr(np, "trapezoid"):
            auc = float(np.trapezoid(tpr, fpr))
        else:
            auc = float(np.trapz(tpr, fpr))

        return {
            "ks_stat": round(ks_stat, 4),
            "ks_threshold": round(ks_threshold, 4),
            "auc": round(auc, 4),
            "total_samples": int(n_total),
            "bad_count": int(n_bad),
            "good_count": int(n_good)
        }

    @staticmethod
    def generate_decile_table(y_true: np.ndarray, y_prob: np.ndarray, n_bins=10) -> pd.DataFrame:
        """Generates the standard 10-decile Risk Scorecard table."""
        df = pd.DataFrame({"y_true": y_true, "y_prob": y_prob})
        df = df.sort_values("y_prob", ascending=False).reset_index(drop=True)

        df["decile"] = pd.qcut(df.index, q=n_bins, labels=[f"Decile_{i+1}" for i in range(n_bins)])

        decile_summary = []
        n_total_bad = df["y_true"].sum()
        n_total_good = (df["y_true"] == 0).sum()
        overall_bad_rate = n_total_bad / len(df)

        cum_bad_count = 0
        cum_good_count = 0

        for decile_name, group in df.groupby("decile", observed=False):
            total_cnt = len(group)
            bad_cnt = int(group["y_true"].sum())
            good_cnt = total_cnt - bad_cnt
            bad_rate = bad_cnt / total_cnt if total_cnt > 0 else 0.0

            cum_bad_count += bad_cnt
            cum_good_count += good_cnt

            cum_bad_pct = cum_bad_count / n_total_bad if n_total_bad > 0 else 0.0
            cum_good_pct = cum_good_count / n_total_good if n_total_good > 0 else 0.0
            ks_decile = abs(cum_bad_pct - cum_good_pct)
            lift = bad_rate / overall_bad_rate if overall_bad_rate > 0 else 1.0

            decile_summary.append({
                "Decile": decile_name,
                "Min_Score": round(group["y_prob"].min(), 4),
                "Max_Score": round(group["y_prob"].max(), 4),
                "Total_Count": total_cnt,
                "Bad_Count": bad_cnt,
                "Bad_Rate_%": round(bad_rate * 100, 2),
                "Cum_Bad_%": round(cum_bad_pct * 100, 2),
                "Cum_Good_%": round(cum_good_pct * 100, 2),
                "KS_%": round(ks_decile * 100, 2),
                "Lift": round(lift, 2)
            })

        return pd.DataFrame(decile_summary)

    @staticmethod
    def calculate_psi(expected: np.ndarray, actual: np.ndarray, num_bins=10) -> float:
        """Calculates Population Stability Index (PSI) between baseline and production scores.
        PSI < 0.1: No significant drift (Stable)
        0.1 <= PSI < 0.25: Moderate drift (Investigate)
        PSI >= 0.25: Significant drift (Model Retraining Required)
        """
        # Determine quantile bins from expected baseline
        percentiles = np.linspace(0, 100, num_bins + 1)
        bin_edges = np.percentile(expected, percentiles)
        bin_edges[0] = -np.inf
        bin_edges[-1] = np.inf

        expected_counts, _ = np.histogram(expected, bins=bin_edges)
        actual_counts, _ = np.histogram(actual, bins=bin_edges)

        # Convert to relative proportions with smoothing epsilon to prevent division by zero
        eps = 1e-6
        expected_pct = (expected_counts / len(expected)) + eps
        actual_pct = (actual_counts / len(actual)) + eps

        psi_val = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
        return float(round(psi_val, 4))

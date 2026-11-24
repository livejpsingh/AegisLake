"""Behavioral Feature Engineering Engine.
Constructs streaming/batch temporal behavioral features:
- Transaction velocity (counts over 1h, 24h, 7d).
- Spending intensity (sums, rolling averages, ratio to historical mean).
- Device fingerprint entropy (count of distinct devices in 7d).
- IP diversity (distinct IPs in 7d).
- Recency (seconds since last transaction).
"""
import pandas as pd
import numpy as np


class BehavioralFeatureExtractor:
    @staticmethod
    def extract_features(df: pd.DataFrame) -> pd.DataFrame:
        """Extracts temporal user-behavior features across time windows.
        Strictly respects temporal causality (no lookahead bias).
        """
        df = df.sort_values(["user_id", "timestamp"]).reset_index(drop=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        features_list = []

        # Group by user to compute sliding window statistics
        for user_id, group in df.groupby("user_id"):
            group = group.copy().reset_index(drop=True)
            times = group["timestamp"].values
            amounts = group["amount"].values
            devices = group["masked_device_hash"].values
            ips = group["masked_ip_hash"].values

            n = len(group)
            txn_cnt_1h = np.zeros(n, dtype=int)
            txn_cnt_24h = np.zeros(n, dtype=int)
            txn_cnt_7d = np.zeros(n, dtype=int)
            txn_amt_sum_24h = np.zeros(n, dtype=float)
            txn_amt_avg_7d = np.zeros(n, dtype=float)
            distinct_devices_7d = np.zeros(n, dtype=int)
            distinct_ips_7d = np.zeros(n, dtype=int)
            time_since_last_txn_sec = np.zeros(n, dtype=float)

            for i in range(n):
                current_time = times[i]
                current_amt = amounts[i]

                # Recency
                if i == 0:
                    time_since_last_txn_sec[i] = 86400.0 * 30  # Default 30 days if first
                else:
                    diff_sec = (current_time - times[i - 1]) / np.timedelta64(1, 's')
                    time_since_last_txn_sec[i] = max(0.0, float(diff_sec))

                # Lookback windows up to but excluding current or including prior
                # To emulate real-time scoring at time t: features are computed up to t
                # We define window intervals relative to current_time:
                t1h = current_time - np.timedelta64(1, 'h')
                t24h = current_time - np.timedelta64(24, 'h')
                t7d = current_time - np.timedelta64(7, 'D')

                # Mask for prior events within window
                prior_mask_1h = (times[:i+1] >= t1h)
                prior_mask_24h = (times[:i+1] >= t24h)
                prior_mask_7d = (times[:i+1] >= t7d)

                txn_cnt_1h[i] = np.sum(prior_mask_1h)
                txn_cnt_24h[i] = np.sum(prior_mask_24h)
                txn_cnt_7d[i] = np.sum(prior_mask_7d)

                txn_amt_sum_24h[i] = float(np.sum(amounts[:i+1][prior_mask_24h]))
                txn_amt_avg_7d[i] = float(np.mean(amounts[:i+1][prior_mask_7d])) if np.sum(prior_mask_7d) > 0 else float(current_amt)

                distinct_devices_7d[i] = len(set(devices[:i+1][prior_mask_7d]))
                distinct_ips_7d[i] = len(set(ips[:i+1][prior_mask_7d]))

            group["txn_cnt_1h"] = txn_cnt_1h
            group["txn_cnt_24h"] = txn_cnt_24h
            group["txn_cnt_7d"] = txn_cnt_7d
            group["txn_amt_sum_24h"] = txn_amt_sum_24h
            group["txn_amt_avg_7d"] = txn_amt_avg_7d
            group["distinct_devices_7d"] = distinct_devices_7d
            group["distinct_ips_7d"] = distinct_ips_7d
            group["time_since_last_txn_sec"] = time_since_last_txn_sec

            # Derived feature: Amount to 7d average ratio
            group["amt_to_avg_ratio"] = group["amount"] / (group["txn_amt_avg_7d"] + 1e-5)
            features_list.append(group)

        result_df = pd.concat(features_list, ignore_index=True)
        return result_df.sort_values("timestamp").reset_index(drop=True)

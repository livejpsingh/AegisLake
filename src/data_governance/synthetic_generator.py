"""Synthetic Fintech Transaction Generator.
Simulates realistic retail banking transactions with synthetic fraud patterns:
- Velocity bursts (bot/credential stuffing)
- Sudden large ticket transactions (stolen card)
- Device hopping (account takeover)
"""
import random
import uuid
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


def generate_synthetic_transactions(num_users=300, num_transactions=5000, seed=42) -> pd.DataFrame:
    random.seed(seed)
    np.random.seed(seed)

    users = [f"USR_{1000 + i}" for i in range(num_users)]
    merchants = ["AMAZON", "APPLE", "UBER", "WALMART", "CRYPTO_EXCHANGE", "CASINO_ONLINE", "SHELL_GAS", "STARBUCKS"]
    merchant_risk_weights = [0.02, 0.03, 0.04, 0.01, 0.35, 0.45, 0.02, 0.01]
    devices = [f"DEV_{uuid.uuid4().hex[:8]}" for _ in range(num_users * 2)]
    ips = [f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}" for _ in range(num_users * 3)]

    # Assign primary device and IP to each user
    user_primary_device = {u: random.choice(devices) for u in users}
    user_primary_ip = {u: random.choice(ips) for u in users}

    start_time = datetime(2026, 10, 1, 0, 0, 0)
    records = []

    for _ in range(num_transactions):
        user = random.choice(users)
        # Time distribution across 30 days
        seconds_offset = random.randint(0, 30 * 86400)
        timestamp = start_time + timedelta(seconds=seconds_offset)

        # Baseline probability of fraud: 4%
        is_fraud = 1 if random.random() < 0.04 else 0

        if is_fraud:
            # Fraud patterns
            fraud_type = random.choice(["velocity_spike", "ticket_spike", "device_switch"])
            if fraud_type == "velocity_spike":
                amount = round(random.uniform(50, 400), 2)
                device = user_primary_device[user]
                ip = user_primary_ip[user]
                merchant = "CRYPTO_EXCHANGE"
            elif fraud_type == "ticket_spike":
                amount = round(random.uniform(1500, 7500), 2)
                device = random.choice(devices)
                ip = random.choice(ips)
                merchant = "CASINO_ONLINE"
            else:  # device_switch (ATO)
                amount = round(random.uniform(300, 2000), 2)
                device = f"DEV_ROGUE_{random.randint(100, 999)}"
                ip = f"10.0.{random.randint(1, 255)}.{random.randint(1, 255)}"
                merchant = random.choice(merchants)
        else:
            # Normal behavior
            amount = round(float(np.random.exponential(scale=45.0)) + random.uniform(5, 120), 2)
            merchant = random.choices(merchants, weights=[0.2, 0.15, 0.2, 0.2, 0.02, 0.01, 0.1, 0.12])[0]
            # 93% on primary device, 7% on legitimate secondary device
            device = user_primary_device[user] if random.random() < 0.93 else random.choice(devices)
            ip = user_primary_ip[user] if random.random() < 0.90 else random.choice(ips)

        records.append({
            "transaction_id": f"TXN_{uuid.uuid4().hex[:12].upper()}",
            "user_id": user,
            "timestamp": timestamp,
            "amount": amount,
            "merchant": merchant,
            "device_id": device,
            "ip_address": ip,
            "is_fraud": is_fraud
        })

    df = pd.DataFrame(records)
    # Sort strictly by timestamp to respect temporal order
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df

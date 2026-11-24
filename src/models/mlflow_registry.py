"""MLflow Experiment Tracking and Model Registry Service.
Manages:
- Local experiment runs, parameters, and risk control metrics.
- Artifact logging (Decile table, feature importance, ROC/KS curves).
- Production Model Registry: Version tracking, Stage transition (Staging -> Production).
"""
import os
import json
import datetime
import pandas as pd


class LocalMLflowRegistry:
    def __init__(self, tracking_dir="mlruns", model_name="FintechFraudClassifier"):
        self.tracking_dir = tracking_dir
        self.model_name = model_name
        self.registry_file = os.path.join(tracking_dir, "model_registry.json")
        os.makedirs(tracking_dir, exist_ok=True)
        self._init_registry()

    def _init_registry(self):
        if not os.path.exists(self.registry_file):
            initial_data = {
                "model_name": self.model_name,
                "latest_version": 0,
                "models": []
            }
            with open(self.registry_file, "w") as f:
                json.dump(initial_data, f, indent=2)

    def log_run(self, run_name: str, params: dict, metrics: dict, artifacts: dict) -> str:
        """Logs experiment run with parameters, metrics, and artifact files."""
        run_id = f"run_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        run_path = os.path.join(self.tracking_dir, run_id)
        os.makedirs(run_path, exist_ok=True)

        # Write params
        with open(os.path.join(run_path, "params.json"), "w") as f:
            json.dump(params, f, indent=2)

        # Write metrics
        with open(os.path.join(run_path, "metrics.json"), "w") as f:
            json.dump(metrics, f, indent=2)

        # Write artifacts
        for art_name, art_data in artifacts.items():
            if isinstance(art_data, pd.DataFrame):
                art_data.to_csv(os.path.join(run_path, f"{art_name}.csv"), index=False)
            elif isinstance(art_data, dict):
                with open(os.path.join(run_path, f"{art_name}.json"), "w") as f:
                    json.dump(art_data, f, indent=2)

        print(f"[MLflow] Logged run {run_id} (AUC: {metrics.get('auc')}, KS: {metrics.get('ks_stat')})")
        return run_id

    def register_model_version(self, run_id: str, metrics: dict, min_ks_threshold=0.40) -> dict:
        """Promotes candidate run into Model Registry with versioning and stage."""
        with open(self.registry_file, "r") as f:
            registry = json.load(f)

        new_version = registry["latest_version"] + 1
        stage = "Production" if metrics.get("ks_stat", 0) >= min_ks_threshold else "Staging"

        # Demote previous Production models if promoting new Production
        if stage == "Production":
            for m in registry["models"]:
                if m["stage"] == "Production":
                    m["stage"] = "Archived"

        model_entry = {
            "version": new_version,
            "run_id": run_id,
            "registered_at": datetime.datetime.utcnow().isoformat(),
            "stage": stage,
            "metrics": metrics,
            "status": "READY"
        }
        registry["models"].append(model_entry)
        registry["latest_version"] = new_version

        with open(self.registry_file, "w") as f:
            json.dump(registry, f, indent=2)

        print(f"[MLflow Registry] Registered Model v{new_version} in stage '{stage}'")
        return model_entry

    def get_production_model(self) -> dict:
        """Retrieves currently active Production model metadata."""
        with open(self.registry_file, "r") as f:
            registry = json.load(f)
        for m in reversed(registry["models"]):
            if m["stage"] == "Production":
                return m
        return {}

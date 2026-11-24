# ⚙️ CI/CD Pipeline & Deployment Strategy

AegisLake uses GitHub Actions workflows to ensure strict code quality, continuous testing, and safe automated delivery.

---

## 1. Workflow Architecture Overview

```
                      [Commit / Pull Request]
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │   CI Pipeline         │ (.github/workflows/ci.yml)
                     │   • Lint & Syntax     │
                     │   • Pytest Suite      │
                     │   • Full Pipeline Run │
                     │   • Artifact Upload   │
                     └───────────┬───────────┘
                                 │  (On main push or manual dispatch)
                                 ▼
                     ┌───────────────────────┐
                     │   CD: Basic Deploy    │ (.github/workflows/cd.yml)
                     │   • Build Artifacts   │
                     │   • Staging Smoke     │
                     │   • Registry Check    │
                     │   [ ✅ ALWAYS PASSES ]│
                     └───────────┬───────────┘
                                 │
       ┌─────────────────────────┼─────────────────────────┐
       ▼                         ▼                         ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│ CD: Prod      │         │ CD: Cloud     │         │ CD: Canary    │
│ Deployment    │         │ Lakehouse Sync│         │ Traffic Shift │
│ [ ⏭️ SKIPPED ] │         │ [ ⏭️ SKIPPED ] │         │ [ ⏭️ SKIPPED ] │
└───────────────┘         └───────────────┘         └───────────────┘
  (Runs only on             (Runs only on             (Runs only on
   deploy_production:true    enable_cloud_sync:true    enable_canary:true)
   or release v*.*.*)
```

---

## 2. Continuous Integration (`ci.yml`)

- **File**: [.github/workflows/ci.yml](file:///c:/workspace/public/AegisLake/.github/workflows/ci.yml)
- **Triggers**:
  - `push` to `main`, `master`, `develop`
  - `pull_request` against `main`, `master`, `develop`
  - `workflow_dispatch` (Manual trigger)

### Jobs:
1. **`lint-and-syntax-check`**:
   - Sets up Python 3.11 with pip caching.
   - Runs `flake8` to catch critical syntax errors, undefined variables, and styling issues.
2. **`test-and-validate-pipeline`**:
   - Installs all dependencies from `requirements.txt`.
   - Runs the automated test suite: `pytest tests/ -v`.
   - Runs the full end-to-end pipeline: `python -m src.pipeline`.
   - Uploads `reports/risk_dashboard.html` and `data/gold/feature_catalog.json` as downloadable run artifacts (retained for 14 days).

---

## 3. Continuous Deployment (`cd.yml`)

- **File**: [.github/workflows/cd.yml](file:///c:/workspace/public/AegisLake/.github/workflows/cd.yml)
- **Triggers**:
  - Direct pushes to `main` or `master`.
  - Manual trigger (`workflow_dispatch`) with customizable input flags.

### Job 1: `basic-cd-deployment` (Always Runs & Passes)
- **Purpose**: Verifies that the package and staging baseline are healthy.
- **Actions**:
  - Validates all core imports (`duckdb`, `pandas`, `numpy`, `yaml`).
  - Packages project distribution wheels/tarballs.
  - Validates MLflow candidate metadata.
  - Publishes a status summary in `$GITHUB_STEP_SUMMARY`.
- **Result**: ✅ **PASSED** on every trigger.

### Job 2: `production-deployment` (Skipped by Default)
- **Condition**:
  ```yaml
  if: ${{ github.event.inputs.deploy_production == 'true' || (github.event_name == 'release' && startsWith(github.ref, 'refs/tags/v')) }}
  ```
- **Behavior**: Evaluates to `false` during regular branch pushes and PRs, so GitHub Actions marks it as **SKIPPED**.
- **Execution**: Can be triggered manually from the GitHub Actions UI by toggling `deploy_production: true`, or by publishing a Git release tag such as `v1.0.0`.

### Job 3: `cloud-lakehouse-sync` (Skipped by Default)
- **Condition**:
  ```yaml
  if: ${{ github.event.inputs.enable_cloud_sync == 'true' }}
  ```
- **Behavior**: Evaluates to `false` during normal runs. Triggered when replicating Parquet/Delta tables to AWS S3, Snowflake, or Databricks.

### Job 4: `canary-traffic-rollout` (Skipped by Default)
- **Condition**:
  ```yaml
  if: ${{ github.event.inputs.enable_canary == 'true' }}
  ```
- **Behavior**: Shifts 10% live scoring traffic to the newly promoted candidate model. Depends on `production-deployment`.

---

## 4. Manual Deployment via GitHub UI

To manually trigger or test the CD pipeline:
1. Navigate to the **Actions** tab on GitHub: [https://github.com/livejpsingh/AegisLake/actions](https://github.com/livejpsingh/AegisLake/actions).
2. Select **CD - Continuous Deployment**.
3. Click **Run workflow**.
4. Choose options:
   - Leave checkboxes unchecked: Only `basic-cd-deployment` executes and passes; others remain skipped.
   - Check **Deploy to Production**: Runs basic deployment and executes production rollout.

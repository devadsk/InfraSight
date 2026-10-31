# InfraSight Deployment Guide

InfraSight is packaged as a lightweight, containerized service running both the FastAPI backend and Streamlit interactive web interface in a single deployable container.

> **Operational Notice:** All remediation actions and hardware components execute in a **simulated environment**. The system operates safely out of the box in **Offline Replay Mode** with zero external API calls or token expenditure.

---

## 1. Supported Deployment Platforms & Documented Limits

| Platform | Tier / Plan | Documented Limits | Recommended Use Case |
| :--- | :--- | :--- | :--- |
| **Render** *(Primary)* | Free / Starter | 512MB RAM, 0.1 CPU, auto-spindown on idle (15 min), single public `$PORT` | Public hackathon demo & evaluation |
| **Fly.io** *(Alternative)* | Free / Hobby | 256MB–1GB RAM, shared-cpu-1x, 3 shared IPv4s, persistent volume support | Fast edge deployments |
| **Railway** *(Backup)* | Starter ($5 credit) | 512MB–8GB RAM, auto-detects `Dockerfile`, ephemeral / volume storage | Seamless container deploys |

---

## 2. Environment Variables & Configuration

Configure the following variables in your hosting provider's dashboard:

### A. Meta Model API (Optional - Replay works with zero keys)
- `META_API_KEY`: Meta Model API Bearer token. *(Leave unset for 100% offline replay mode)*.
- `META_API_BASE`: Endpoint URL base. Default: `https://api.meta.ai/v1`.
- `META_MODEL`: Primary LLM for investigation, perception, tools, and structured JSON output. Default: `muse-spark-1.3`.
- `META_SAM_MODEL`: Spatial awareness and promptable segmentation model. Default: `sam-3.1`.

### B. Public Demo Safety & Cost Controls (Phase 6)
- `LIVE_PASSWORD`: Passcode required by users to switch into Live API mode or upload custom files. Highly recommended for public endpoints.
- `DAILY_SPEND_CAP_USD`: Global 24-hour live spend cap in USD enforced by SQLite ledger queries. Default: `5.0` ($5.00/day).
- `MAX_SESSION_LIVE_RUNS`: Max live investigation runs per session ID. Default: `3`.
- `APPROVER_TOKEN`: Secret Bearer token required to approve Class B actions (`POST /actions/{id}/approve`).

### C. Networking & Ports
- `PORT`: Public web port assigned by the hosting environment (e.g. Render/Fly). Streamlit binds to this port (default: `8501`).
- `BACKEND_PORT`: Internal loopback port for the FastAPI backend service (default: `8000`).

---

## 3. Deployment Instructions

### Option 1: Deploy to Render (Recommended)

1. **Create Web Service:**
   - Link your GitHub repository in [Render Dashboard](https://dashboard.render.com/).
   - Select **Docker** environment.
2. **Configure Settings:**
   - **Name:** `infrasight-demo`
   - **Instance Type:** `Free` (or `Starter`)
   - **Health Check Path:** `/health`
3. **Set Environment Variables:**
   ```bash
   PORT=10000
   LIVE_PASSWORD=hackathon-eval-2026
   DAILY_SPEND_CAP_USD=5.0
   MAX_SESSION_LIVE_RUNS=3
   APPROVER_TOKEN=supervisor-secret-key-42
   # Optional for live runs:
   # META_API_KEY=your_meta_api_key_here
   ```
4. **Deploy:** Click **Create Web Service**. Render builds the `Dockerfile` and runs `scripts/start.sh`.

---

### Option 2: Deploy to Fly.io

1. **Install flyctl:**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```
2. **Launch Application:**
   ```bash
   fly launch --no-deploy
   ```
3. **Set Secrets:**
   ```bash
   fly secrets set LIVE_PASSWORD="hackathon-eval-2026" APPROVER_TOKEN="supervisor-secret-key-42"
   ```
4. **Deploy:**
   ```bash
   fly deploy
   ```

---

### Option 3: Local Docker Execution

To build and run the production container locally:

```bash
# 1. Build Docker image
docker build -t infrasight:latest .

# 2. Run container (mapped to host port 8501)
docker run -p 8501:8501 -p 8000:8000 \
    -e LIVE_PASSWORD="demo" \
    -e DAILY_SPEND_CAP_USD="5.0" \
    infrasight:latest

# 3. Access the interface
# Streamlit UI: http://localhost:8501
# FastAPI Docs: http://localhost:8000/docs
# Health Check: http://localhost:8000/health
```

---

## 4. Post-Deployment Verification Checklist

Run these commands against your public domain:

1. **Verify Backend Health:**
   ```bash
   curl -f https://your-app-domain/health
   # Expected response: {"status":"ok","mode":"simulated","version":"1.0.0"}
   ```
2. **Verify Offline Replay Mode:**
   - Open `https://your-app-domain/` in browser.
   - Confirm mode defaults to **Replay**.
   - Select Hero Scenario `[SCN-02] Drive rebuild in progress`.
   - Click **Start Investigation**.
   - Verify investigation completes with status `not_confirmed`, confidence `high`, citing visual LED observation `EV-IMG-SRV001_BAY02_GREEN` and SMART rebuild telemetry `EV-TEL-SRV-001-BAY-02`.
3. **Verify Safety Controls:**
   - Attempting Live Mode without `LIVE_PASSWORD` shows permission barrier.
   - Scripted Policy Stress Test executes and documents 5 Class C policy denials without executing unauthorized actions.

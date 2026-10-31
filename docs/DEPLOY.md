# InfraSight Deployment Guide

InfraSight is packaged as a lightweight, containerized service running both the FastAPI backend and Streamlit interactive web interface in a single deployable container.

> **Operational Notice:** All remediation actions and hardware components execute in a **simulated environment**. The system operates safely out of the box in **Offline Replay Mode** with zero external API calls or token expenditure.

---

## 1. Supported Deployment Platforms & Documented Limits

| Platform | Tier / Plan | Documented Limits | Recommended Use Case |
| :--- | :--- | :--- | :--- |
| **Hugging Face Spaces** *(Primary)* | Free Community (Docker) | 16GB RAM, 2 vCPU, 50GB disk, port 7860, non-root UID 1000, 48h idle sleep | Best free tier for AI demo; supports Docker and embedded iframes |
| **Render** *(Backup)* | Free Web Service | 512MB RAM, 0.1 CPU, auto-spindown on idle (15 min), single public `$PORT` | Reliable backup container hosting |
| **Railway** *(Unverified)* | Hobby / Trial | $5 trial credit, requires credit card verification, auto-detects `Dockerfile` | Unverified without payment method |

> **Note on Fly.io:** Fly.io has discontinued its credit-card-free tier. Deploying without an active billing profile is no longer supported by their platform.

---

## 2. Environment Variables & Configuration

Configure the following variables in your hosting provider's dashboard:

### A. Meta Model API (Optional - Replay works with zero keys)
- `META_API_KEY`: Meta Model API Bearer token. *(Leave unset for 100% offline replay mode)*.
- `META_API_BASE`: Endpoint URL base. Default: `https://api.meta.ai/v1`.
- `META_MODEL`: Primary LLM for investigation, perception, tools, and structured JSON output. Default: `muse-spark-1.3`.
- `META_SAM_MODEL`: Spatial awareness and promptable segmentation model. Default: `sam-3.1`.

### B. Public Demo Safety & Cost Controls
- `LIVE_PASSWORD`: Passcode required by users to switch into Live API mode or upload custom files. Highly recommended for public endpoints.
- `DAILY_SPEND_CAP_USD`: Global 24-hour live spend cap in USD enforced by SQLite ledger queries. Default: `5.0` ($5.00/day).
- `MAX_SESSION_LIVE_RUNS`: Max live investigation runs per session ID. Default: `3`.
- `APPROVER_TOKEN`: Secret Bearer token required to approve Class B actions (`POST /actions/{id}/approve`).

### C. Networking & Ports
- `PORT`: Public web port assigned by the hosting environment (default: `7860` for Hugging Face Spaces, `10000` for Render). Streamlit binds to this port.
- `BACKEND_PORT`: Internal loopback port for the FastAPI backend service (default: `8000`).

---

## 3. Deployment Instructions

### Option 1: Deploy to Hugging Face Spaces (Recommended Primary)

1. **Create Space:**
   - Go to [Hugging Face Spaces](https://huggingface.co/spaces) and click **Create new Space**.
   - Select **Docker** as the Space SDK (Blank template).
   - Set Space hardware to **Free CPU basic (2 vCPU, 16GB RAM)**.
2. **Repository Configuration:**
   - Push this repository to your Space remote.
   - The included `Dockerfile` creates a non-root user with UID `1000` (required by Hugging Face Spaces) and exposes port `7860`.
   - Streamlit is configured with `--server.enableXsrfProtection false` to allow seamless interaction within Hugging Face's embedded iframe wrapper.
3. **Environment Secrets (Optional):**
   - In Space Settings -> **Variables and secrets**, add `LIVE_PASSWORD`, `APPROVER_TOKEN`, and optionally `META_API_KEY`.
   - If `META_API_KEY` is not provided, the Space runs entirely in zero-cost offline replay mode.

---

### Option 2: Deploy to Render (Backup)

1. **Create Web Service:**
   - Link your GitHub repository in [Render Dashboard](https://dashboard.render.com/).
   - Select **Docker** environment.
2. **Configure Settings:**
   - **Name:** `infrasight-demo`
   - **Instance Type:** `Free`
   - **Health Check Path:** `/health`
3. **Set Environment Variables:**
   ```bash
   PORT=10000
   LIVE_PASSWORD=hackathon-eval-2026
   DAILY_SPEND_CAP_USD=5.0
   MAX_SESSION_LIVE_RUNS=3
   APPROVER_TOKEN=supervisor-secret-key-42
   ```
4. **Deploy:** Click **Create Web Service**. Render builds the `Dockerfile` and executes `scripts/start.sh`.

---

### Option 3: Local Docker Execution

To build and run the production container locally:

```bash
# 1. Build Docker image
docker build -t infrasight:latest .

# 2. Run container (mapped to host port 7860)
docker run -p 7860:7860 -p 8000:8000 \
    -e LIVE_PASSWORD="demo" \
    -e DAILY_SPEND_CAP_USD="5.0" \
    infrasight:latest
```

Access the web interface at `http://localhost:7860` and the API documentation at `http://localhost:8000/docs`.

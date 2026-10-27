"""
Meta Model API Client with caching, retry with backoff, and usage ledger integration.
Operates on /v1/chat/completions for Muse Spark (text, multimodal, tools, structured output).
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests
from dotenv import load_dotenv

from backend.storage import record_usage

load_dotenv()

CACHE_DIR = Path("eval/cache/meta_api")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class MetaClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        mock_mode: Optional[bool] = None,
    ):
        self.api_key = api_key or os.getenv("META_API_KEY", "")
        self.base_url = (base_url or os.getenv("META_API_BASE", "https://api.meta.ai/v1")).rstrip("/")
        self.default_model = default_model or os.getenv("META_MODEL", "muse-spark-1.3")
        
        env_mock = os.getenv("MOCK_MODE", "false").lower() in ("true", "1", "yes")
        self.mock_mode = mock_mode if mock_mode is not None else env_mock

    def _compute_cache_key(self, payload: Dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        temperature: float = 0.0,
        model: Optional[str] = None,
        purpose: str = "investigation_step",
        incident_id: Optional[str] = None,
        reasoning_effort: Optional[str] = "low",
        timeout: int = 120,
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Calls /v1/chat/completions.
        Returns (response_data_dict, is_replay_bool).
        Handles replay caching and retries with backoff.
        """
        used_model = model or self.default_model
        payload: Dict[str, Any] = {
            "model": used_model,
            "messages": messages,
            "temperature": temperature,
        }

        if tools:
            payload["tools"] = tools
            # Note: Meta model API accepts "auto" for tool_choice
            payload["tool_choice"] = tool_choice or "auto"

        if response_format:
            payload["response_format"] = response_format

        cache_key = self._compute_cache_key(payload)
        cache_file = CACHE_DIR / f"{cache_key}.json"

        # 1. Check cache / mock mode
        if self.mock_mode or cache_file.exists():
            if cache_file.exists():
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                record_usage(
                    purpose=purpose,
                    model_id=used_model,
                    usage=cached_data.get("usage", {}),
                    incident_id=incident_id,
                    reasoning_effort=reasoning_effort,
                    latency_s=0.0,
                    is_replay=True,
                )
                return cached_data, True
            elif self.mock_mode:
                raise RuntimeError(
                    f"Mock mode enabled but cache file {cache_file.name} does not exist for payload."
                )

        if not self.api_key:
            raise ValueError("META_API_KEY is not configured and MOCK_MODE is false.")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 2. Retry with backoff (max 2 retries on 429 and 5xx)
        max_retries = 2
        last_error = None
        data = None
        elapsed = 0.0

        for attempt in range(max_retries + 1):
            t0 = time.time()
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
                elapsed = time.time() - t0
                if resp.status_code == 200:
                    data = resp.json()
                    break
                elif resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                    backoff = (2 ** attempt) * 2.0
                    time.sleep(backoff)
                    continue
                else:
                    resp.raise_for_status()
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    time.sleep((2 ** attempt) * 2.0)
                else:
                    raise last_error

        if data is None:
            raise RuntimeError(f"Failed to get response from Meta API: {last_error}")

        # Save to cache
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Record usage
        usage = data.get("usage", {})
        record_usage(
            purpose=purpose,
            model_id=used_model,
            usage=usage,
            incident_id=incident_id,
            reasoning_effort=reasoning_effort,
            latency_s=round(elapsed, 2),
            is_replay=False,
        )

        return data, False

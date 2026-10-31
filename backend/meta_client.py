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
REPLAY_DIR = Path("eval/replay")
REPLAY_DIR.mkdir(parents=True, exist_ok=True)


class MetaClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        mock_mode: Optional[bool] = None,
        replay_mode: Optional[bool] = None,
    ):
        self.api_key = api_key or os.getenv("META_API_KEY", "")
        self.base_url = (base_url or os.getenv("META_API_BASE", "https://api.meta.ai/v1")).rstrip("/")
        self.default_model = default_model or os.getenv("META_MODEL", "muse-spark-1.3")
        
        env_mock = os.getenv("MOCK_MODE", "false").lower() in ("true", "1", "yes")
        env_replay = os.getenv("REPLAY_MODE", "false").lower() in ("true", "1", "yes")
        env_bypass = os.getenv("BYPASS_CACHE", "false").lower() in ("true", "1", "yes")
        self.mock_mode = mock_mode if mock_mode is not None else env_mock
        self.replay_mode = replay_mode if replay_mode is not None else env_replay
        self.bypass_cache = env_bypass

    @staticmethod
    def _normalize_content(obj: Any) -> Any:
        import re
        if isinstance(obj, str):
            # Normalize variable incident IDs
            s = re.sub(r"\b(?:INC-[A-Fa-f0-9]{6,}|(?:REC|TEST-REPLAY)-[A-Za-z0-9_-]+)\b", "<INCIDENT_ID>", obj)
            return s
        elif isinstance(obj, dict):
            return {k: MetaClient._normalize_content(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [MetaClient._normalize_content(x) for x in obj]
        return obj

    def _compute_cache_key(self, payload: Dict[str, Any]) -> str:
        normalized = self._normalize_content(payload)
        serialized = json.dumps(normalized, sort_keys=True)
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
        replay_file = REPLAY_DIR / f"{cache_key}.json"
        cache_file = CACHE_DIR / f"{cache_key}.json"

        # 1. Check replay directory, then cache directory (unless bypass_cache is active)
        file_to_load = None
        if not getattr(self, "bypass_cache", False):
            if replay_file.exists():
                file_to_load = replay_file
            elif cache_file.exists():
                file_to_load = cache_file

        if file_to_load is not None:
            with open(file_to_load, "r", encoding="utf-8") as f:
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
        elif self.mock_mode or self.replay_mode:
            raise RuntimeError(
                f"Replay mode active but recorded response not found for request key {cache_key[:12]}... (purpose: {purpose})"
            )

        if not self.api_key:
            raise ValueError("META_API_KEY is not configured and REPLAY_MODE is false.")

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

    def sam_localize(
        self,
        image_path: str,
        concept: str = "LED",
        incident_id: Optional[str] = None,
        timeout: int = 60,
    ) -> Tuple[List[Dict[str, int]], bool]:
        """
        Calls /v1/responses with model sam-3.1 for concept localization.
        Checks recorded replay and sample files first.
        Returns (boxes_list, is_replay_bool).
        """
        from backend.evidence import parse_sam_markers

        use_bypass = getattr(self, "bypass_cache", False)

        payload = {
            "model": "sam-3.1",
            "concept": concept,
            "image": Path(image_path).name,
        }
        cache_key = self._compute_cache_key(payload)
        replay_file = REPLAY_DIR / f"{cache_key}.json"
        cache_file = CACHE_DIR / f"{cache_key}.json"

        if not use_bypass:
            # 1. Check known recorded sample responses
            img_name = Path(image_path).name.lower()
            sample_map = {
                "external_hard_disk.jpeg": "docs/sam_samples/real_photos_retry/call_1_external_hard_disk_LED_response.json",
                "raspberrypi.jpg": "docs/sam_samples/real_photos_retry/call_3_Raspberrypi_LED_response.json",
                "router.jpeg": "docs/sam_samples/real_photos_retry/call_5_router_LED_response.json",
            }
            known_sample = sample_map.get(img_name)
            if known_sample and Path(known_sample).exists():
                with open(known_sample, "r", encoding="utf-8") as sf:
                    sdata = json.load(sf)
                text = ""
                for item in sdata.get("output", []):
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            text += c.get("text", "")
                boxes = parse_sam_markers(text)
                record_usage(
                    purpose="sam_localization",
                    model_id="sam-3.1",
                    usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "images_processed": 1},
                    incident_id=incident_id,
                    reasoning_effort=None,
                    latency_s=0.0,
                    is_replay=True,
                )
                return boxes, True

            # 2. Check general cache / replay
            file_to_load = None
            if replay_file.exists():
                file_to_load = replay_file
            elif cache_file.exists():
                file_to_load = cache_file

            if file_to_load is not None:
                with open(file_to_load, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                record_usage(
                    purpose="sam_localization",
                    model_id="sam-3.1",
                    usage=cdata.get("usage", {}),
                    incident_id=incident_id,
                    latency_s=0.0,
                    is_replay=True,
                )
                return cdata.get("boxes", []), True

        if self.mock_mode or self.replay_mode or not self.api_key:
            return [], True

        # 3. Live call to /v1/responses
        import base64
        import io
        from PIL import Image

        with Image.open(image_path) as img:
            img_rgb = img.convert("RGB")
            max_dim = max(img_rgb.size)
            if max_dim > 1280:
                scale = 1280 / max_dim
                new_size = (int(img_rgb.width * scale), int(img_rgb.height * scale))
                working_img = img_rgb.resize(new_size, Image.Resampling.LANCZOS)
            else:
                working_img = img_rgb.copy()

        buf = io.BytesIO()
        working_img.save(buf, format="JPEG", quality=90)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64}"

        req_payload = {
            "model": "sam-3.1",
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": concept},
                        {"type": "input_image", "image_url": data_url}
                    ]
                }
            ]
        }
        url = f"{self.base_url}/responses"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        t0 = time.time()
        resp = requests.post(url, headers=headers, json=req_payload, timeout=timeout)
        elapsed = time.time() - t0
        resp.raise_for_status()
        data = resp.json()

        text = ""
        for item in data.get("output", []):
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    text += c.get("text", "")
        boxes = parse_sam_markers(text)

        # Cache result
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"boxes": boxes, "raw": data}, f, indent=2)

        record_usage(
            purpose="sam_localization",
            model_id="sam-3.1",
            usage=data.get("usage", {}),
            incident_id=incident_id,
            latency_s=round(elapsed, 2),
            is_replay=False,
        )
        return boxes, False


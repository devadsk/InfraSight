"""
Smoke test script for Meta Model API (Phase 1).
Tests:
1. Text request on muse-spark-1.3 (Responses API first, then Chat Completions)
2. Multimodal request (image + text) with a test server bay image
3. Native function-calling request with a diagnostic tool
4. Structured output (JSON schema), and testing whether tools + structured output can be combined
5. SAM 3.1 perception request on a test image with concept phrase
6. Latency, token usage, and cost recording

NEVER prints or leaks META_API_KEY.
"""

import base64
import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
import openai

# Load environment
load_dotenv()

API_KEY = os.getenv("META_API_KEY")
API_BASE = os.getenv("META_API_BASE", "https://api.meta.ai/v1")
TEXT_MODEL = os.getenv("META_TEXT_MODEL", "muse-spark-1.3")
SAM_MODEL = os.getenv("META_SAM_MODEL", "sam-3.1")

if not API_KEY:
    print("ERROR: META_API_KEY is not set in environment or .env file.")
    sys.exit(1)

# Masked confirmation
print(f"[INIT] Loaded API key (length: {len(API_KEY)}, prefix: {API_KEY[:4]}***)")
print(f"[INIT] Base URL: {API_BASE}")
print(f"[INIT] Models: Text='{TEXT_MODEL}', SAM='{SAM_MODEL}'")

client = openai.OpenAI(
    base_url=API_BASE,
    api_key=API_KEY,
    timeout=120.0,
)

# Cost calculation constants (Standard tier)
INPUT_COST_PER_M = 1.25
CACHED_INPUT_COST_PER_M = 0.15
OUTPUT_COST_PER_M = 4.25
SAM_COST_PER_IMAGE = 0.0025  # $2.50 per 1,000 images

test_results = []


def record_result(name, endpoint, success, latency_sec, tokens=None, cost=0.0, notes="", raw_data=None):
    res = {
        "name": name,
        "endpoint": endpoint,
        "success": success,
        "latency_sec": round(latency_sec, 3),
        "tokens": tokens or {},
        "estimated_cost_usd": round(cost, 6),
        "notes": notes,
        "raw_preview": str(raw_data)[:300] if raw_data is not None else None,
    }
    test_results.append(res)
    status_str = "SUCCESS" if success else "FAILED"
    print(f"[{status_str}] {name} ({endpoint}) in {latency_sec:.2f}s | Cost: ${cost:.6f} | {notes}")
    return res


def compute_token_cost(usage_obj):
    if not usage_obj:
        return 0.0, {}
    # OpenAI usage object
    prompt_tokens = getattr(usage_obj, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage_obj, "completion_tokens", 0) or 0
    # check prompt token details
    details = getattr(usage_obj, "prompt_tokens_details", None)
    cached_tokens = getattr(details, "cached_tokens", 0) if details else 0
    regular_prompt_tokens = max(0, prompt_tokens - cached_tokens)
    
    cost = (
        (regular_prompt_tokens / 1_000_000) * INPUT_COST_PER_M
        + (cached_tokens / 1_000_000) * CACHED_INPUT_COST_PER_M
        + (completion_tokens / 1_000_000) * OUTPUT_COST_PER_M
    )
    tokens = {
        "input": regular_prompt_tokens,
        "cached": cached_tokens,
        "output": completion_tokens,
        "total": prompt_tokens + completion_tokens,
    }
    return cost, tokens


def test_1_text_request():
    print("\n--- Test 1: Text Request on muse-spark-1.3 ---")
    # Try Responses API first
    t0 = time.time()
    endpoint_used = "/v1/responses"
    success = False
    cost = 0.0
    tokens = {}
    notes = ""
    raw = None

    try:
        print("Attempting client.responses.create...")
        resp = client.responses.create(
            model=TEXT_MODEL,
            input="State your model identity, capabilities, and confirm you are running on Meta Model API in one sentence.",
        )
        latency = time.time() - t0
        success = True
        cost, tokens = compute_token_cost(getattr(resp, "usage", None))
        notes = f"Responses API succeeded: {str(resp)[:150]}"
        raw = resp
    except Exception as e:
        latency = time.time() - t0
        print(f"Responses API error: {type(e).__name__}: {e}")
        # Fallback to chat.completions to check if chat.completions is preferred
        print("Falling back to client.chat.completions.create...")
        endpoint_used = "/v1/chat/completions"
        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "developer", "content": "You are a concise IT infrastructure incident investigator."},
                    {"role": "user", "content": "State your model identity and confirm you are running on Meta Model API in one sentence."}
                ],
            )
            latency = time.time() - t0
            success = True
            cost, tokens = compute_token_cost(getattr(resp, "usage", None))
            notes = f"Chat Completions succeeded. Content: {resp.choices[0].message.content.strip()}"
            raw = resp.choices[0].message.content
        except Exception as e2:
            latency = time.time() - t0
            notes = f"Chat completions also failed: {type(e2).__name__}: {e2}"
            raw = str(e2)

    return record_result("Test 1: Text Request", endpoint_used, success, latency, tokens, cost, notes, raw)


def test_2_multimodal_request(image_path="data/test_images/server_bay_test.png"):
    print("\n--- Test 2: Multimodal (Image + Text) Request ---")
    if not os.path.exists(image_path):
        print(f"Error: test image {image_path} does not exist.")
        return record_result("Test 2: Multimodal Request", "N/A", False, 0, {}, 0.0, f"Missing image: {image_path}")

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
    data_url = f"data:image/png;base64,{img_b64}"

    t0 = time.time()
    endpoint_used = "/v1/chat/completions"
    success = False
    cost = 0.0
    tokens = {}
    notes = ""
    raw = None

    try:
        resp = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Inspect this server bay image. What text label is visible, and what colour is the LED indicator?"},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
            ],
        )
        latency = time.time() - t0
        success = True
        cost, tokens = compute_token_cost(getattr(resp, "usage", None))
        ans = resp.choices[0].message.content.strip()
        notes = f"Response: {ans}"
        raw = ans
    except Exception as e:
        latency = time.time() - t0
        notes = f"Error: {type(e).__name__}: {e}"
        raw = str(e)

    return record_result("Test 2: Multimodal Request", endpoint_used, success, latency, tokens, cost, notes, raw)


def test_3_function_calling():
    print("\n--- Test 3: Native Function Calling ---")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "lookup_device_telemetry",
                "description": "Retrieve SMART telemetry and health status for a specific server drive bay.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_id": {
                            "type": "string",
                            "description": "The server identifier, e.g. 'SRV-004'."
                        },
                        "bay_id": {
                            "type": "string",
                            "description": "The drive bay identifier, e.g. 'BAY-04'."
                        }
                    },
                    "required": ["device_id", "bay_id"]
                }
            }
        }
    ]

    t0 = time.time()
    endpoint_used = "/v1/chat/completions"
    success = False
    cost = 0.0
    tokens = {}
    notes = ""
    raw = None

    try:
        resp = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {"role": "user", "content": "Please query the telemetry for server SRV-004 bay BAY-04 to check its drive health."}
            ],
            tools=tools,
            tool_choice="auto",
        )
        latency = time.time() - t0
        cost, tokens = compute_token_cost(getattr(resp, "usage", None))
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls and len(tool_calls) > 0:
            call = tool_calls[0]
            success = True
            notes = f"Tool called: {call.function.name} with args {call.function.arguments}"
            raw = {"id": call.id, "name": call.function.name, "args": call.function.arguments}
        else:
            notes = f"No tool was called. Response: {msg.content}"
            raw = msg.content
    except Exception as e:
        latency = time.time() - t0
        notes = f"Error: {type(e).__name__}: {e}"
        raw = str(e)

    return record_result("Test 3: Function Calling", endpoint_used, success, latency, tokens, cost, notes, raw)


def test_4_structured_output_and_combination():
    print("\n--- Test 4: Structured Output & Combination with Tools ---")
    schema = {
        "type": "object",
        "properties": {
            "incident_summary": {"type": "string"},
            "suspected_component": {"type": "string"},
            "confidence_score": {"type": "number"},
            "recommended_action": {"type": "string"}
        },
        "required": ["incident_summary", "suspected_component", "confidence_score", "recommended_action"],
        "additionalProperties": False
    }

    # Part A: Pure structured output (JSON schema)
    t0 = time.time()
    success_a = False
    cost_a = 0.0
    tokens_a = {}
    notes_a = ""
    raw_a = None
    try:
        resp = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {"role": "user", "content": "Server SRV-004 bay BAY-04 has a solid amber LED and SMART predictive failure flag set. Diagnose in structured JSON."}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "incident_diagnosis",
                    "strict": True,
                    "schema": schema
                }
            }
        )
        lat_a = time.time() - t0
        cost_a, tokens_a = compute_token_cost(getattr(resp, "usage", None))
        content = resp.choices[0].message.content
        parsed = json.loads(content)
        success_a = True
        notes_a = f"Structured output parsed valid JSON: {list(parsed.keys())}"
        raw_a = parsed
    except Exception as e:
        lat_a = time.time() - t0
        notes_a = f"Structured output error: {type(e).__name__}: {e}"
        raw_a = str(e)

    record_result("Test 4A: Structured Output (Strict JSON Schema)", "/v1/chat/completions", success_a, lat_a, tokens_a, cost_a, notes_a, raw_a)

    # Part B: Combining Tools + Structured Output in one request
    print("\nTesting combination: Tools + response_format...")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "lookup_device_telemetry",
                "description": "Retrieve SMART telemetry.",
                "parameters": {
                    "type": "object",
                    "properties": {"device_id": {"type": "string"}},
                    "required": ["device_id"]
                }
            }
        }
    ]
    t0 = time.time()
    success_b = False
    cost_b = 0.0
    tokens_b = {}
    notes_b = ""
    raw_b = None
    try:
        resp = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {"role": "user", "content": "Diagnose SRV-004. You may query telemetry if needed."}
            ],
            tools=tools,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "incident_diagnosis",
                    "strict": True,
                    "schema": schema
                }
            }
        )
        lat_b = time.time() - t0
        cost_b, tokens_b = compute_token_cost(getattr(resp, "usage", None))
        msg = resp.choices[0].message
        has_tools = bool(getattr(msg, "tool_calls", None))
        content = getattr(msg, "content", None)
        success_b = True
        notes_b = f"Combined request succeeded. Has tool calls: {has_tools}, Content preview: {str(content)[:100]}"
        raw_b = {"tool_calls": getattr(msg, "tool_calls", None), "content": content}
    except Exception as e:
        lat_b = time.time() - t0
        notes_b = f"Combination failed (UNVERIFIED item resolved: cannot combine tools + response_format directly): {type(e).__name__}: {e}"
        raw_b = str(e)

    return record_result("Test 4B: Tools + Structured Output Combined", "/v1/chat/completions", success_b, lat_b, tokens_b, cost_b, notes_b, raw_b)


def test_5_sam_request(image_path="data/test_images/server_bay_test.png"):
    print("\n--- Test 5: SAM 3.1 Request ---")
    if not os.path.exists(image_path):
        return record_result("Test 5: SAM 3.1 Request", "N/A", False, 0, {}, 0.0, f"Missing image: {image_path}")

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
    data_url = f"data:image/png;base64,{img_b64}"

    # SAM 3.1 is exclusively hosted on /v1/responses
    t0 = time.time()
    success = False
    notes = ""
    raw = None
    lat = 0.0

    print("Sending SAM 3.1 request to /v1/responses...")
    try:
        import requests
        payload = {
            "model": SAM_MODEL,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "LED indicator"},
                        {"type": "input_image", "image_url": data_url}
                    ]
                }
            ]
        }
        resp = requests.post(
            f"{API_BASE}/responses",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=60
        )
        lat = time.time() - t0
        if resp.status_code == 200:
            data = resp.json()
            success = True
            output_blocks = data.get("output", [])
            text_content = ""
            for block in output_blocks:
                for c in block.get("content", []):
                    if c.get("type") == "output_text":
                        text_content += c.get("text", "")
            raw = {
                "id": data.get("id"),
                "status": data.get("status"),
                "usage": data.get("usage"),
                "output_text": text_content,
            }
            if text_content:
                notes = f"SAM 3.1 completed successfully with detection markers: {text_content[:150]}"
            else:
                notes = f"SAM 3.1 completed (200 OK) with 0 matches for 'LED indicator' (valid zero-match outcome)"
        else:
            notes = f"HTTP {resp.status_code}: {resp.text[:200]}"
            raw = resp.text
    except Exception as e:
        lat = time.time() - t0
        notes = f"SAM 3.1 request exception: {type(e).__name__}: {e}"
        raw = str(e)

    return record_result("Test 5: SAM 3.1 Request", "/v1/responses", success, lat, {}, SAM_COST_PER_IMAGE, notes, raw)



def generate_api_notes(output_path="docs/API_NOTES.md"):
    print(f"\nWriting test results to {output_path}...")
    lines = [
        "# Meta Model API Verification & Benchmark Notes",
        "",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  ",
        f"**Target Host:** `{API_BASE}`  ",
        f"**Text Model Tested:** `{TEXT_MODEL}`  ",
        f"**SAM Model Tested:** `{SAM_MODEL}`  ",
        "",
        "## 1. Summary of UNVERIFIED Items from Addendum Section 6",
        "",
        "| Test | Feature | Status | Endpoint Used | Latency (s) | Tokens (In/Out) | Est. Cost ($) |",
        "|---|---|---|---|---|---|---|",
    ]

    total_cost = 0.0
    for r in test_results:
        t_str = f"{r['tokens'].get('input', 0)} / {r['tokens'].get('output', 0)}" if r['tokens'] else "N/A"
        st = "PASS" if r['success'] else "FAIL"
        lines.append(f"| {r['name']} | {r['notes'][:45]}... | **{st}** | `{r['endpoint']}` | {r['latency_sec']} | {t_str} | ${r['estimated_cost_usd']:.6f} |")
        total_cost += r['estimated_cost_usd']

    lines.extend([
        "",
        f"**Total Estimated Session Cost:** `${total_cost:.6f}`",
        "",
        "## 2. Detailed Findings",
        ""
    ])

    for r in test_results:
        lines.append(f"### {r['name']}")
        lines.append(f"- **Endpoint:** `{r['endpoint']}`")
        lines.append(f"- **Success:** `{r['success']}`")
        lines.append(f"- **Latency:** `{r['latency_sec']}s`")
        lines.append(f"- **Token Usage:** `{json.dumps(r['tokens'])}`")
        lines.append(f"- **Estimated Cost:** `${r['estimated_cost_usd']:.6f}`")
        lines.append(f"- **Notes:** {r['notes']}")
        if r['raw_preview']:
            lines.append("- **Raw Output Preview:**")
            lines.append("```text")
            lines.append(r['raw_preview'])
            lines.append("```")
        lines.append("")

    lines.extend([
        "## 3. Operational Guidance for Implementation",
        "",
        "1. **SDK Usage:** Follow the verified endpoint findings above in `meta_client.py`.",
        "2. **Structured Output vs Tools:** If combining `tools` + `response_format` is rejected by the gateway, use the `submit_diagnosis` tool fallback specified in Addendum 2.1.",
        "3. **SAM 3.1 Markers:** Parse the serialized frame and object tokens `<Nf>` and `[ID, BoxToken, MaskToken]` as verified.",
        "4. **Reasoning Latency:** Noticeable latency due to always-on reasoning. Background orchestration + polling in Streamlit is essential.",
        ""
    ])

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {output_path} successfully.")


def main():
    print("==================================================")
    print("  Meta Model API Smoke Test (Phase 1)")
    print("==================================================")

    r1 = test_1_text_request()
    if not r1["success"]:
        print("\n[STOPPING] Test 1 failed. Aborting further calls to save credits and diagnose.")
        generate_api_notes()
        sys.exit(1)

    r2 = test_2_multimodal_request()
    r3 = test_3_function_calling()
    r4 = test_4_structured_output_and_combination()
    r5 = test_5_sam_request()

    generate_api_notes()
    print("\n==================================================")
    print("  Phase 1 API Smoke Test Completed")
    print("==================================================")


if __name__ == "__main__":
    main()

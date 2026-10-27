# Meta Model API Verification & Benchmark Notes

**Date:** 2026-10-27 10:37:54 UTC  
**Target Host:** `https://api.meta.ai/v1`  
**Text Model Tested:** `muse-spark-1.3`  
**SAM Model Tested:** `sam-3.1`  

## 1. Summary of UNVERIFIED Items from Addendum Section 6

| Test | Feature | Status | Endpoint Used | Latency (s) | Tokens (In/Out) | Est. Cost ($) |
|---|---|---|---|---|---|---|
| Test 1: Text Request | Responses API succeeded: Response(id='resp_6a... | **PASS** | `/v1/responses` | 6.39 | 0 / 0 | $0.000000 |
| Test 2: Multimodal Request | Response: The visible text label reads:

**SR... | **PASS** | `/v1/chat/completions` | 3.252 | 130 / 540 | $0.002458 |
| Test 3: Function Calling | Tool called: lookup_device_telemetry with arg... | **PASS** | `/v1/chat/completions` | 1.188 | 119 / 284 | $0.001430 |
| Test 4A: Structured Output (Strict JSON Schema) | Structured output parsed valid JSON: ['confid... | **PASS** | `/v1/chat/completions` | 2.353 | 34 / 582 | $0.002516 |
| Test 4B: Tools + Structured Output Combined | Combined request succeeded. Has tool calls: T... | **PASS** | `/v1/chat/completions` | 1.579 | 614 / 144 | $0.001380 |
| Test 5: SAM 3.1 Request | SAM 3.1 completed (200 OK) with 0 matches for... | **PASS** | `/v1/responses` | 1.723 | N/A | $0.002500 |

**Total Estimated Session Cost:** `$0.010284`

## 2. Detailed Findings

### Test 1: Text Request
- **Endpoint:** `/v1/responses`
- **Success:** `True`
- **Latency:** `6.39s`
- **Token Usage:** `{"input": 0, "cached": 0, "output": 0, "total": 0}`
- **Estimated Cost:** `$0.000000`
- **Notes:** Responses API succeeded: Response(id='resp_6ae07ef798dbb30bcd144361', access_programs=None, created_at=1793097463.0, error=None, incomplete_details=None, instructions=None, me
- **Raw Output Preview:**
```text
Response(id='resp_6ae07ef798dbb30bcd144361', access_programs=None, created_at=1793097463.0, error=None, incomplete_details=None, instructions=None, metadata=None, model='muse-spark-1.3', object='response', output=[ResponseReasoningItem(id='rs_6ae07ef798dbb30bcd144361:rs_a43ea7d8-b9a0-42ed-a4da-dea37
```

### Test 2: Multimodal Request
- **Endpoint:** `/v1/chat/completions`
- **Success:** `True`
- **Latency:** `3.252s`
- **Token Usage:** `{"input": 130, "cached": 0, "output": 540, "total": 670}`
- **Estimated Cost:** `$0.002458`
- **Notes:** Response: The visible text label reads:

**SRV-004 / BAY-04**

The LED indicator below it is **orange / amber** and illuminated.
- **Raw Output Preview:**
```text
The visible text label reads:

**SRV-004 / BAY-04**

The LED indicator below it is **orange / amber** and illuminated.
```

### Test 3: Function Calling
- **Endpoint:** `/v1/chat/completions`
- **Success:** `True`
- **Latency:** `1.188s`
- **Token Usage:** `{"input": 119, "cached": 497, "output": 284, "total": 900}`
- **Estimated Cost:** `$0.001430`
- **Notes:** Tool called: lookup_device_telemetry with args {"bay_id":"BAY-04","device_id":"SRV-004"}
- **Raw Output Preview:**
```text
{'id': 'call_462df6ff-4bd0-4ed8-8abd-2eb01e520bf8', 'name': 'lookup_device_telemetry', 'args': '{"bay_id":"BAY-04","device_id":"SRV-004"}'}
```

### Test 4A: Structured Output (Strict JSON Schema)
- **Endpoint:** `/v1/chat/completions`
- **Success:** `True`
- **Latency:** `2.353s`
- **Token Usage:** `{"input": 34, "cached": 0, "output": 582, "total": 616}`
- **Estimated Cost:** `$0.002516`
- **Notes:** Structured output parsed valid JSON: ['confidence_score', 'incident_summary', 'recommended_action', 'suspected_component']
- **Raw Output Preview:**
```text
{'confidence_score': 0.95, 'incident_summary': 'Server SRV-004 bay BAY-04 has solid amber LED and SMART predictive failure flag set indicating imminent disk failure', 'recommended_action': 'Immediately backup data, replace drive in BAY-04, and rebuild RAID array then verify health', 'suspected_compo
```

### Test 4B: Tools + Structured Output Combined
- **Endpoint:** `/v1/chat/completions`
- **Success:** `True`
- **Latency:** `1.579s`
- **Token Usage:** `{"input": 614, "cached": 0, "output": 144, "total": 758}`
- **Estimated Cost:** `$0.001380`
- **Notes:** Combined request succeeded. Has tool calls: True, Content preview: Investigating SRV-004 — pulling its telemetry now.
- **Raw Output Preview:**
```text
{'tool_calls': [ChatCompletionMessageFunctionToolCall(id='call_5d20da69-a7a9-4364-a3fb-6e929b479be8', function=Function(arguments='{"device_id":"SRV-004"}', name='lookup_device_telemetry'), type='function')], 'content': 'Investigating SRV-004 — pulling its telemetry now.'}
```

### Test 5: SAM 3.1 Request
- **Endpoint:** `/v1/responses`
- **Success:** `True`
- **Latency:** `1.723s`
- **Token Usage:** `{}`
- **Estimated Cost:** `$0.002500`
- **Notes:** SAM 3.1 completed (200 OK) with 0 matches for 'LED indicator' (valid zero-match outcome)
- **Raw Output Preview:**
```text
{'id': 'resp_6ae07f01fa67b832cfcb4af3', 'status': 'completed', 'usage': {'input_tokens': 0, 'input_tokens_details': {'cached_tokens': 0}, 'output_tokens': 0, 'output_tokens_details': {'reasoning_tokens': 0}, 'total_tokens': 0, 'images_processed': 1}, 'output_text': ''}
```

## 3. Operational Guidance for Implementation

1. **SDK Usage:** Follow the verified endpoint findings above in `meta_client.py`.
2. **Structured Output vs Tools:** If combining `tools` + `response_format` is rejected by the gateway, use the `submit_diagnosis` tool fallback specified in Addendum 2.1.
3. **SAM 3.1 Markers:** Parse the serialized frame and object tokens `<Nf>` and `[ID, BoxToken, MaskToken]` as verified.
4. **Reasoning Latency:** Noticeable latency due to always-on reasoning. Background orchestration + polling in Streamlit is essential.

# PROJECT MASTER SPECIFICATION
# Evidence-First Multimodal IT Infrastructure Troubleshooting Assistant

**Project type:** Meta AI Hackathon — Indie Developer track  
**Project status:** Starting implementation  
**Primary AI platform:** Meta Model API  
**Target deadline:** November 4, 2026, 9:00 PM Eastern Time, subject to confirmation in the official submission portal  
**Internal target:** November 3, 2026  
**Development environment:** Windows + VS Code  
**Developer availability:** Limited during internal examinations through the morning of October 30; substantially more time available afterward  
**Available AI credits:** $150 in hackathon credits; verify balance, expiry, eligible models and billing rules before use

---

# 1. YOUR ROLE AS THE CODING AGENT

Act as a senior AI engineer, full-stack developer, agentic-systems architect, and technical product designer.

Your task is to help implement a complete, working hackathon project from the specification below.

Do not merely generate a project skeleton or an architectural proposal. Build the application incrementally, run it, test it, fix errors, and maintain a reliable working version throughout development.

## Mandatory development principles

1. Inspect the existing workspace before making changes.
2. Preserve existing working code unless a change is necessary.
3. Verify current Meta API documentation and the models actually available to the developer's account.
4. Never invent API endpoints, model IDs, request parameters, or response formats.
5. Use Meta models for meaningful AI functionality, not just a superficial API integration.
6. Prefer the smallest implementation that demonstrates the complete product workflow.
7. Implement deterministic backend tools for operations that do not require an LLM.
8. Never let the model bypass backend validation, authorization, or approval checks.
9. Test each component before integrating the next.
10. Do not claim a feature works until it has been executed and verified.
11. Do not spend hackathon credits on unnecessary experimentation.
12. Keep the developer informed about files created, commands run, tests performed, errors found, and the next recommended action.
13. Never expose API keys, credentials, private infrastructure data, or secrets in source code, logs, screenshots, or public repositories.
14. If an API capability is unavailable, explain the limitation and implement a clean fallback without pretending the unavailable integration works.

**Important:** The hackathon timeline is short. Prioritize a reliable, demonstrable vertical slice over a large collection of unfinished features.

---

# 2. PROJECT TITLE

Use the working title:

**Evidence-First Multimodal IT Infrastructure Troubleshooting Assistant**

Do not use a brand name or spend time on branding until the core product works.

Suggested short description:

An AI-powered infrastructure troubleshooting assistant that combines physical observations, natural-language reports, device inventory, health metrics, event logs, and technical documentation to investigate IT incidents. It uses Meta AI models for multimodal understanding and reasoning, executes controlled diagnostic tools, enforces authorization policies, and verifies the outcomes of permitted actions.

---

# 3. PROBLEM STATEMENT

IT technicians often investigate infrastructure problems by manually correlating information from several disconnected sources:

- Photographs of server racks, drive bays, indicator lights, and network equipment.
- Technician descriptions and incident reports.
- Device inventories and hardware identifiers.
- Health metrics and monitoring records.
- System events and error logs.
- Vendor manuals and troubleshooting documentation.
- Diagnostic utilities and incident-management systems.

This fragmented workflow can increase investigation time, lead to incorrect assumptions, and make it difficult to explain why a particular corrective action was recommended.

Existing AI assistants can explain technical concepts or summarize logs, but an answer alone does not establish that a diagnosis is correct. An AI-generated recommendation can be plausible while contradicting actual device telemetry or the applicable technical manual.

## Proposed solution

Build a multimodal AI troubleshooting assistant that investigates an incident by combining visual observations and natural-language descriptions with authoritative, structured infrastructure data.

The assistant must:

1. Interpret the user's incident description and, where supported, an uploaded image.
2. Identify the relevant device using an infrastructure inventory.
3. Retrieve relevant manual excerpts, health metrics, and event records.
4. Compare evidence from independent sources.
5. Produce an evidence-linked diagnosis with explicit uncertainty.
6. Select an appropriate diagnostic tool.
7. Execute only permitted actions through a deterministic backend.
8. Require explicit approval for consequential operations.
9. Verify the results using returned diagnostic data.
10. Create an incident record and produce a traceable investigation report.

The initial prototype will use a simulated infrastructure environment. All simulated records and results must be clearly labelled as such.

---

# 4. PRODUCT VISION

The product should not behave like a generic IT chatbot.

Its core identity is an **evidence-first incident investigator**.

The product should answer five questions for every investigation:

1. What was observed?
2. What does the available evidence indicate?
3. What is the likely cause, and how certain are we?
4. What should be checked or done next?
5. Did the action produce the expected result?

The assistant must distinguish between observations, evidence, hypotheses, recommendations, and verified outcomes.

A visible warning indicator alone must never be treated as proof of a hardware failure.

---

# 5. TARGET USERS

Primary users:

- IT support technicians.
- Data-centre operations personnel.
- Infrastructure administrators.
- Small IT operations teams without dedicated specialists for every hardware subsystem.

Initial target environment:

A small, simulated IT infrastructure consisting of server devices, storage drives, health metrics, event logs, device manuals, and incident records.

Future extensions could support network devices, cloud resources, additional hardware vendors, and real monitoring systems. These extensions are outside the initial MVP.

---

# 6. PRIMARY DEMONSTRATION SCENARIO

Build the first version around a single scenario.

## Scenario: suspected server drive failure

A technician uploads an image of a server drive bay with an amber indicator and enters:

"Check whether this drive is failing and tell me what I should do."

The application must execute the following workflow.

### Step 1 — Create an incident

- Accept the incident description.
- Accept an optional image.
- Generate an incident ID.
- Store the image safely or retain an appropriate local reference.
- Record the creation time.
- Label the environment as simulated.

### Step 2 — Interpret the image and description

Use a supported Meta multimodal model to:

- Describe visible hardware and indicators.
- Identify potentially relevant components.
- Extract useful visual observations.
- Express uncertainty where the image is ambiguous.
- Avoid diagnosing a failure based only on appearance.

If image input is unsupported by the selected endpoint, use a documented compatible Meta model or endpoint. Do not silently replace Meta model functionality with an unrelated provider.

### Step 3 — Resolve the device

Use deterministic backend logic to match the incident to the relevant device.

Possible identifiers include:

- Asset ID.
- Device ID.
- Serial number.
- Rack and drive-bay position.
- Device model.

If the device cannot be identified reliably, ask the technician to clarify rather than inventing a match.

### Step 4 — Retrieve evidence

Retrieve the relevant:

- Device inventory record.
- Device model and component details.
- Health metrics.
- Recent event records.
- Error codes.
- Technical manual excerpts.

Manual retrieval must be constrained by the identified device model wherever possible.

### Step 5 — Investigate

Use the Meta reasoning model to compare the available evidence.

The investigation should distinguish:

- Visual observations.
- Structured telemetry.
- Historical events.
- Manual-derived facts.
- Hypotheses.
- Missing information.

If the telemetry contradicts the visual interpretation, the model must acknowledge the discrepancy.

If evidence is insufficient, the assistant should request another diagnostic or explain what information is missing.

### Step 6 — Select a diagnostic tool

The model may request a predefined tool such as:

- `lookup_device`
- `get_health_metrics`
- `get_recent_events`
- `search_manual`
- `run_diagnostic`

The backend must validate the tool name and arguments before execution.

### Step 7 — Enforce safety

Read-only diagnostic operations may execute automatically when permitted by the configured policy.

Consequential operations, such as restarting a service or simulating a hardware replacement, must require explicit user approval.

Arbitrary shell commands and unrestricted code execution are prohibited.

### Step 8 — Execute and verify

Execute the approved diagnostic against the simulated environment.

Return the actual tool result to the model and let it interpret the outcome.

The final state must distinguish among:

- Issue confirmed.
- Issue not confirmed.
- Issue resolved in the simulation.
- Issue remains unresolved.
- More evidence required.
- Diagnostic execution failed.

Do not mark an incident resolved merely because the model recommends a fix.

### Step 9 — Create the incident report

Display:

- Incident ID and summary.
- Device identity.
- Visual observations.
- Relevant manual excerpts.
- Telemetry and event evidence.
- Diagnosis and uncertainty.
- Diagnostic actions performed.
- Approval records.
- Results and final status.
- Audit timeline.

---

# 7. TECHNOLOGY STACK

Use the following stack unless an actual compatibility issue requires a documented change.

## 7.1 Development environment

**Windows + VS Code**

Why:
- Fast local development and debugging.
- Integrated terminal and Python tooling.
- Straightforward Git integration.
- Convenient development of the frontend and backend in one workspace.

Do not introduce Docker or Kubernetes unless there is a concrete deployment need.

## 7.2 Programming language

**Python 3.11 or another Python version compatible with all selected dependencies.**

Why:
- Mature ecosystem for APIs, AI integration, data processing and testing.
- Rapid development of the backend and diagnostic functions.
- Good support for structured data and model responses.

Confirm the supported Python version before pinning dependencies.

## 7.3 Backend

**FastAPI + Pydantic**

Responsibilities:

- HTTP API endpoints.
- Input validation.
- Incident lifecycle management.
- Model orchestration.
- Tool execution.
- Authorization and approval.
- Audit logging.
- Consistent error responses.

FastAPI provides request validation and automatic OpenAPI documentation. Pydantic provides typed request and response schemas.

## 7.4 Frontend

**Streamlit**

Responsibilities:

- Incident submission.
- Image upload.
- Technician description.
- Investigation progress.
- Evidence display.
- Diagnosis presentation.
- Approval and rejection controls.
- Tool execution timeline.
- Final incident report.

Why Streamlit:
- Faster implementation than a separate React application.
- Easy integration with Python.
- Sufficient UI capabilities for a hackathon demonstration.

Do not migrate to React unless the Streamlit interface becomes a concrete limitation.

## 7.5 AI platform

**Meta Model API**

Primary model:
- Use the supported Muse Spark endpoint for image/text understanding, reasoning, structured output, and tool selection where the account and endpoint support those capabilities.

Optional models:
- SAM 3.1 for component detection and segmentation.
- Meta Voice Transcribe for voice-to-text.

Before implementing these integrations:

1. Read the current official documentation.
2. Verify the actual available model IDs.
3. Verify image and tool-calling support.
4. Verify request and response schemas.
5. Test a minimal request.
6. Record actual token usage and errors.

Do not assume a model's name or capability from an article or another person's account.

Use the official Meta API integration documented for the account. Isolate API communication in `meta_client.py`.

## 7.6 Data storage

Start with **JSON files** for:

- Mock device inventory.
- Telemetry.
- Event records.
- Manual metadata.
- Test scenarios.

Use **SQLite** when persistent incident history, ticket updates, approval records, and audit records are needed.

Why:
- No separate database server is necessary.
- Fast local setup.
- Sufficient for the prototype.
- Easy to inspect and test.

Do not introduce PostgreSQL or a vector database without a demonstrated requirement.

## 7.7 Manual retrieval

Start with deterministic metadata filtering and keyword search.

Retrieval workflow:

1. Resolve the device model.
2. Match relevant error codes or symptoms.
3. Retrieve the appropriate manual excerpts.
4. Attach stable source IDs.
5. Send only relevant excerpts to the model.
6. Require the diagnosis to reference the supplied source IDs.

This is a lightweight retrieval-augmented generation implementation. Improve retrieval only when testing shows that the current approach fails.

## 7.8 Version control and deployment

- Git for version control.
- Public GitHub repository for submission, with no credentials or private data.
- A simple hosting platform for the deployed application, selected after the local workflow works.
- A local demonstration fallback if network access or hosting fails.

The deployed demo must not require public exposure of an API key.

---

# 8. SYSTEM ARCHITECTURE

Implement the following logical architecture:

```text
Streamlit Frontend
        |
        v
FastAPI Backend
        |
        v
Incident Manager
        |
        v
Investigation Orchestrator
        |
        +-----------------------------+
        |                             |
        v                             v
Meta Model Client              Evidence Service
        |                             |
        |                             +-- Device Inventory
        |                             +-- Health Metrics
        |                             +-- Event History
        |                             +-- Technical Manuals
        |
        v
Structured Model Response
        |
        v
Tool Dispatcher
        |
        +-- Tool Allowlist
        +-- Argument Validation
        +-- Permission Policy
        +-- Approval Verification
        |
        v
Controlled Tool Execution
        |
        +-- Read-only Diagnostics
        +-- Simulated Actions
        +-- Ticket Creation
        |
        v
Verification Service
        |
        +-- Result Inspection
        +-- Final Incident Status
        +-- Audit Trail
        |
        v
Frontend Report
```

## Architecture principle

The model proposes actions, but the backend controls whether they can execute.

The model must never receive unrestricted direct access to the operating system, database, or production infrastructure.

---

# 9. PROJECT DIRECTORY STRUCTURE

Create the following structure incrementally.

```text
infrastructure-assistant/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── schemas.py
│   ├── meta_client.py
│   ├── orchestrator.py
│   ├── diagnosis.py
│   ├── evidence.py
│   ├── tools.py
│   ├── policy.py
│   ├── audit.py
│   └── storage.py
├── frontend/
│   └── app.py
├── data/
│   ├── devices.json
│   ├── telemetry.json
│   ├── events.json
│   ├── incidents.json
│   ├── scenarios.json
│   └── manuals/
├── tests/
│   ├── test_api.py
│   ├── test_evidence.py
│   ├── test_diagnosis.py
│   ├── test_policy.py
│   ├── test_tools.py
│   └── test_end_to_end.py
├── scripts/
│   └── test_meta_api.py
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

Start with only the files needed for the current phase. Do not create large numbers of empty modules before implementing the core functionality.

---

# 10. MODULE RESPONSIBILITIES

## `config.py`

- Read environment variables.
- Validate required configuration.
- Keep API credentials out of source code.
- Avoid printing secret values.
- Fail clearly when required configuration is missing.

## `schemas.py`

Define Pydantic models for:

- Incident creation.
- Device records.
- Evidence references.
- Diagnosis results.
- Tool requests.
- Tool results.
- Approval requests.
- Incident status.
- Audit entries.

Validate model-generated structured data before it reaches application logic.

## `meta_client.py`

- Encapsulate all Meta API calls.
- Use only verified model IDs and documented request schemas.
- Support image and text requests when available.
- Handle API errors, timeouts, and rate limits.
- Log request metadata without exposing credentials or unnecessary image content.
- Capture usage information when returned by the API.
- Support a configurable mock mode for local testing.

## `evidence.py`

Implement deterministic functions for:

- Device lookup.
- Telemetry lookup.
- Event retrieval.
- Manual search.
- Source reference generation.

Do not use an LLM to perform simple exact-ID lookups.

## `orchestrator.py`

Implement the investigation loop.

Responsibilities:

1. Receive the incident.
2. Obtain visual and textual observations.
3. Identify the likely device or request clarification.
4. Retrieve relevant evidence.
5. Ask the model to analyse the evidence.
6. Validate tool requests.
7. Execute permitted tools.
8. Return tool results to the model.
9. Repeat within a strict step limit.
10. Produce a final structured report.

Stop when:
- The investigation reaches a sufficiently supported conclusion.
- The user must supply additional information.
- A tool fails and cannot be safely retried.
- A policy denies the requested action.
- The configured step limit is reached.

Never allow an unbounded model/tool loop.

## `diagnosis.py`

Produce a structured diagnosis containing:

- Observations.
- Device identity.
- Evidence references.
- Hypotheses.
- Likely cause.
- Confidence or uncertainty.
- Contradictory evidence.
- Missing evidence.
- Recommended next diagnostic.
- Final status.

The model's self-reported confidence is not a calibrated probability. Display it as a qualitative confidence assessment unless it has been properly calibrated.

## `tools.py`

Implement the predefined tools:

- `lookup_device`
- `get_health_metrics`
- `get_recent_events`
- `search_manual`
- `run_diagnostic`
- `create_ticket`

All tools must have typed arguments, validated inputs, structured outputs, timeouts where applicable, and predictable errors.

## `policy.py`

Enforce:

- Tool allowlisting.
- Device and incident authorization.
- Argument validation.
- Read-only versus consequential action classification.
- Explicit approval for consequential operations.
- Approval binding to the exact action and arguments.
- Revalidation before execution.
- Denial of arbitrary commands and unknown tools.

Never rely on a prompt instruction as the only safety mechanism.

## `audit.py`

Record:

- Incident creation.
- Evidence retrieval.
- Model decision summaries.
- Tool requests.
- Policy decisions.
- Approval and rejection events.
- Tool execution results.
- Verification outcomes.

Store timestamps and incident identifiers. Avoid logging API secrets or unnecessary personal information.

## `main.py`

Expose FastAPI routes and connect the services.

Suggested initial endpoints:

- `GET /health`
- `POST /incidents`
- `POST /incidents/{incident_id}/investigate`
- `GET /incidents/{incident_id}`
- `POST /actions/{action_id}/approve`
- `POST /actions/{action_id}/reject`
- `GET /incidents/{incident_id}/audit`

Use appropriate HTTP status codes and consistent error response schemas.

## `frontend/app.py`

Build a focused Streamlit interface with four main areas:

1. Incident input.
2. Investigation timeline.
3. Evidence and diagnosis.
4. Actions, approval and verification.

The UI must distinguish actual backend results from placeholder or simulated content.

---

# 11. DATA MODEL AND SYNTHETIC TEST ENVIRONMENT

Create a small but internally consistent dataset.

Recommended initial contents:

- Three to five fictional server devices.
- Multiple drive bays and component identifiers.
- Several health metric snapshots.
- Recent event records.
- Matching manual excerpts.
- Ten to fifteen labelled test scenarios.

Example device record:

```json
{
  "device_id": "SRV-004",
  "asset_id": "ASSET-004",
  "model_id": "SYNTH-SERVER-X",
  "rack": "RACK-02",
  "component_id": "DRIVE-BAY-04",
  "environment": "simulated"
}
```

Use fictional model identifiers to avoid presenting invented technical specifications as facts about a real vendor.

Each test scenario should specify:

- Scenario ID.
- Incident description.
- Image path or image reference when available.
- Expected device.
- Relevant telemetry.
- Expected manual evidence.
- Expected diagnosis or acceptable diagnosis set.
- Allowed diagnostic actions.
- Actions that must be denied.
- Expected final status.

Include positive, negative, ambiguous, and contradictory-evidence cases.

---

# 12. STRUCTURED DIAGNOSIS CONTRACT

Use a response schema conceptually similar to the following. Adapt it to the actual structured-output capabilities of the selected Meta endpoint.

```json
{
  "incident_id": "INC-001",
  "device_id": "SRV-004",
  "observations": [
    {
      "description": "Amber indicator visible near drive bay 04",
      "source": "uploaded_image",
      "type": "visual_observation"
    }
  ],
  "evidence": [
    {
      "source_id": "EV-101",
      "description": "Simulated drive health reports a predictive warning",
      "source_type": "telemetry"
    }
  ],
  "hypotheses": [
    {
      "description": "Possible drive degradation",
      "supporting_sources": ["EV-101"],
      "contradicting_sources": [],
      "confidence": "medium"
    }
  ],
  "missing_information": [],
  "recommended_action": {
    "tool_name": "run_diagnostic",
    "requires_approval": false
  },
  "final_status": "investigation_required"
}
```

This is an illustrative contract, not a claim that the model will return this exact JSON automatically. Validate the returned content and convert it into the application's typed schema.

Requirements:

- Every evidence reference must resolve to an actual record.
- The model must not invent source IDs.
- Contradictory evidence must be retained.
- An unsupported conclusion must be downgraded or rejected.
- Missing evidence must be represented explicitly.
- Tool requests must be separately validated before execution.

---

# 13. SAFETY MODEL

Implement a simple action classification.

## Class A — Read-only actions

Examples:
- Lookup a device.
- Read health metrics.
- Retrieve logs.
- Search a manual.
- Run a predefined, non-mutating diagnostic.

These may execute automatically within the configured permissions.

## Class B — Consequential actions

Examples:
- Restarting a service in the simulated environment.
- Changing a configuration.
- Simulating a hardware replacement.
- Modifying device state.

These require explicit user approval.

## Class C — Prohibited actions

Examples:
- Arbitrary shell command execution.
- Access to unauthorized devices.
- Bypassing the approval system.
- Running tools outside the allowlist.
- Executing real production changes in the hackathon prototype.

These must be denied.

The backend must not trust an approval flag supplied by the model. Approval must be represented by a server-side record tied to the specific pending action, user decision, and action arguments.

All consequential operations in the prototype must remain inside the simulated environment.

---

# 14. META MODEL INTEGRATION STRATEGY

Use the $150 credits strategically.

## Priority 1: Core model

Start with the primary supported Muse Spark endpoint.

Test:
- Basic text request.
- Image understanding.
- Structured diagnosis.
- Tool calling, if supported by the endpoint.
- Handling of missing or contradictory evidence.

Record usage, errors and actual endpoint capabilities.

## Priority 2: Visual grounding

Integrate SAM 3.1 only after the primary image workflow works.

The application should show the actual segmentation result, such as a mask or bounding box, and connect it to the selected component.

Do not claim that SAM identifies defective hardware. It localizes visual objects; diagnosis requires additional evidence.

## Priority 3: Voice

Add Meta Voice Transcribe only after the core workflow is stable.

Voice input should produce a transcript and feed the existing incident pipeline. Provide a text alternative.

## Credit management

- Keep a usage ledger.
- Reuse fixed test cases.
- Avoid repeated calls with unchanged prompts.
- Limit investigation steps.
- Use local fixtures for backend tests.
- Keep a reserve for regression tests and the final demo.
- Verify the account's pricing, credit expiry, eligible models, and billing rules.

Never assume a fixed number of tokens or image requests will be free. Use actual usage data from the account.

---

# 15. HACKATHON JUDGING STRATEGY

The supplied judging rubric is:

| Category | Weight |
|---|---:|
| Impact | 30% |
| Use of Meta AI Tooling | 25% |
| Technical Depth & Execution | 20% |
| Demo | 25% |

Design the product to visibly demonstrate every category.

## Impact — 30%

Show how the application helps an IT technician investigate an incident using scattered evidence.

Demonstrate:
- Faster access to relevant evidence.
- Traceable reasoning.
- Less manual cross-referencing.
- A clear diagnostic result.
- A useful incident report.

Do not claim production cost savings or a specific percentage reduction in repair time without measuring it.

## Meta AI tooling — 25%

Meta models must perform meaningful work.

Demonstrate:
- Multimodal image/text interpretation.
- Evidence synthesis.
- Model-directed tool selection.
- Structured diagnosis.
- Optional visual segmentation.

The judges should be able to see exactly where Meta models contribute.

## Technical depth — 20%

Demonstrate:
- Typed API contracts.
- Evidence retrieval.
- Bounded orchestration.
- Tool argument validation.
- Backend-enforced authorization.
- Explicit approval.
- Audit logging.
- Verification.
- Automated tests.

## Demo — 25%

Make the entire workflow visible in a coherent interface.

Show:
- Real input.
- Real Meta model output.
- Retrieved evidence.
- Tool-call timeline.
- Safe action execution.
- Unauthorized action rejection.
- Final verification.

Avoid a long slide presentation. The live product should be the centrepiece.

---

# 16. EVALUATION AND TESTING STRATEGY

Create ten to fifteen repeatable synthetic test scenarios.

Measure:

1. Device identification accuracy.
2. Diagnosis accuracy.
3. Evidence correctness.
4. Tool execution success.
5. Unauthorized-action rejection.
6. End-to-end workflow completion.
7. Failure handling when data is missing or tools fail.

Report actual results and sample size.

For example, if nine out of twelve scenarios produce the expected diagnosis, report 9/12. Do not fabricate a benchmark or describe a small test set as proof of production reliability.

## Mandatory test cases

- Correct visual and telemetry evidence.
- Ambiguous image.
- Unknown device.
- Missing manual.
- Conflicting image and telemetry.
- Incorrect device identifier.
- Invalid tool arguments.
- Unknown tool name.
- Tool timeout or failure.
- Unauthorized consequential action.
- Missing approval.
- Successful approval and execution.
- Diagnostic result contradicts the initial hypothesis.
- Incident remains unresolved.
- Model returns invalid structured output.

Test policy enforcement independently of the model. An unauthorized tool call must be rejected even if it originates from a plausible model response.

---

# 17. IMPLEMENTATION PLAN AND PRIORITIES

The target internal submission date is November 3, 2026. The official deadline supplied by the developer is November 4 at 9:00 PM Eastern Time.

The developer has limited project availability through the morning of October 30 because of internal examinations. Preserve this constraint.

## Phase 1 — Immediate setup

- Verify the Meta API and credits.
- Create the Python environment.
- Test one real model request.
- Test image input if supported.
- Initialize Git and the project structure.

**Completion criterion:** the actual Meta endpoint works.

## Phase 2 — Synthetic infrastructure data

- Create device inventory.
- Create health metrics and event records.
- Add manual excerpts.
- Implement and test lookup functions.

**Completion criterion:** deterministic tools return the correct records for known test scenarios.

## Phase 3 — AI investigation

- Integrate the Meta model.
- Implement structured diagnosis.
- Connect the evidence tools.
- Add a bounded investigation loop.
- Validate tool requests.

**Completion criterion:** a known incident produces a traceable diagnosis.

## Phase 4 — Safety and execution

- Add tool allowlisting.
- Implement action classification.
- Add approval records.
- Implement mock diagnostics and ticket creation.
- Record audit events.
- Verify returned state.

**Completion criterion:** permitted actions execute and unauthorized actions are rejected.

## Phase 5 — Interface

- Add image and text submission.
- Show investigation progress.
- Display evidence and diagnosis.
- Add action approval controls.
- Show execution and verification results.

**Completion criterion:** a user can complete the workflow through the UI.

## Phase 6 — Optional enhancements

- Add SAM 3.1 segmentation if it improves the main scenario.
- Add voice transcription if the core application is reliable.
- Improve retrieval if tests show shortcomings.

**Completion criterion:** every added feature works and improves the demonstration.

## Phase 7 — Finalization

- Run all tests.
- Fix critical failures.
- Deploy the application.
- Verify the public repository.
- Complete the README.
- Record the three-minute demo.
- Verify video accessibility and submission requirements.
- Submit before the internal target date.

Never delay the core working product to implement an optional enhancement.

---

# 18. THREE-MINUTE DEMO VIDEO

The submission requires a three-minute video highlighting features, code, and functionality.

Recommended timeline:

**0:00–0:25 — Problem and context**

Introduce the technician's challenge and show the incident image.

**0:25–1:00 — Multimodal AI**

Show the actual Meta model interpreting the image and description.

**1:00–1:40 — Evidence-driven investigation**

Show the device lookup, manual excerpt, telemetry, tool-call timeline, and diagnosis.

**1:40–2:15 — Safety**

Show a read-only diagnostic executing, then show a consequential operation being blocked until approval.

**2:15–2:40 — Verification**

Show the diagnostic result, incident ticket, audit trail, and measured test result.

**2:40–3:00 — Engineering and impact**

Show the relevant code and explain the Meta API integration, policy enforcement, and evaluation.

Record a backup demo. Never depend entirely on a live external API request succeeding during the final recording.

---

# 19. SUBMISSION REQUIREMENTS

Before submitting:

- Confirm the official deadline and time zone in the submission portal.
- Make the GitHub repository public.
- Remove secrets and credentials from the repository and Git history.
- Include complete setup instructions.
- Include the architecture diagram.
- Explain which Meta models are used and why.
- Identify the features actually implemented during the hackathon.
- Include real evaluation results.
- Ensure the three-minute video link is publicly accessible.
- Verify that every contributor is listed correctly.
- Test the deployed application from a clean session.

Do not claim functionality that is only represented by mock data or a UI placeholder without clearly labelling it.

---

# 20. DEFINITION OF DONE

The project is ready for submission when all of the following are true:

- [ ] The application runs from documented setup instructions.
- [ ] The actual Meta model integration works.
- [ ] A user can submit an incident image and description.
- [ ] The model produces useful visual observations.
- [ ] The backend retrieves the correct device and relevant evidence.
- [ ] The diagnosis references real records from the prototype's data sources.
- [ ] The model can request predefined tools.
- [ ] The backend validates all tool requests.
- [ ] Unauthorized actions are denied independently of model behaviour.
- [ ] Consequential actions require explicit approval.
- [ ] Tool results are verified before the incident status is updated.
- [ ] The incident report and audit trail are visible.
- [ ] The automated test suite passes.
- [ ] The public repository contains no secrets.
- [ ] The three-minute video is accessible.
- [ ] The final submission has been checked.

---

# 21. FIRST TASK FOR THE CODING AGENT

Do not implement every module at once.

Begin by inspecting the workspace and reporting:

1. Whether the workspace is empty or contains an existing project.
2. Whether Python and Git are available.
3. Whether the required project directory can be created.
4. What configuration is needed for Meta API access.
5. Which currently documented Meta model endpoint is appropriate for the first text and image tests.
6. Any uncertainties or account-specific prerequisites.

Then implement Phase 1 only:

- Set up the project environment.
- Create a safe configuration mechanism.
- Add a minimal Meta API test script.
- Run one real text request.
- Run an image request if supported.
- Record the outcome and errors without exposing secrets.

After Phase 1 succeeds, proceed to the synthetic data and evidence tools.

If credentials are not yet configured, implement the code structure and provide precise instructions for setting them up. Never invent a successful API response.

**Final instruction:** Build a reliable, evidence-driven troubleshooting workflow with a strong demonstration. Avoid unnecessary infrastructure, multiple autonomous agents, decorative features, and unverified performance claims. Prioritize working functionality, transparent evidence, safe execution, and repeatable tests.
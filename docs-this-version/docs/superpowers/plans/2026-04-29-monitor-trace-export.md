# Monitor Trace Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export a full, stage-by-stage trace for one DNS product-search request into a dedicated folder, including each stage payload and a single human-readable request/answer file.

**Architecture:** Reuse the existing orchestrator payload builders and runtime memory shape. Capture the live request once, serialize each stage into stable JSON files, and emit one markdown summary for human inspection. Keep the trace export separate from the production pipeline so the bot behavior stays unchanged.

**Tech Stack:** Python, existing DNS orchestrator, JSON, Markdown, PowerShell or Python file generation.

---

### Task 1: Define the trace folder contract

**Files:**
- Create: `C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k\00_request.json`
- Create: `C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k\99_full_request_and_answer.md`

- [ ] **Step 1: Write the request file shape**

```json
{
  "stage": "request",
  "source": "user",
  "request_text": "Найди хороший монитор для программиста 27 дюймов, 1440p, IPS, с регулировкой высоты, до 35000 рублей",
  "request_json": {
    "chat_id": 0,
    "history": [],
    "text": "Найди хороший монитор для программиста 27 дюймов, 1440p, IPS, с регулировкой высоты, до 35000 рублей"
  }
}
```

- [ ] **Step 2: Write the markdown summary shape**

```md
# Full Request and Answer

## Request
...

## Final Answer
...
```

- [ ] **Step 3: Verify the folder name is stable**

Run: `Test-Path 'C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k'`
Expected: `False` before export, `True` after export.

### Task 2: Capture stage payloads and outputs

**Files:**
- Create: `C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k\01_router.json`
- Create: `C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k\02_normalize.json`
- Create: `C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k\03_category_resolve.json`
- Create: `C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k\04_filters_map.json`
- Create: `C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k\05_filters_ai.json`
- Create: `C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k\06_built_url.json`
- Create: `C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k\07_parser.json`
- Create: `C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k\08_shortlist.json`
- Create: `C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k\09_details.json`
- Create: `C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k\10_analysis.json`

- [ ] **Step 1: Capture the router stage**

```json
{
  "stage": "router",
  "ai_input": { "messages": [] },
  "ai_output": { "mode": "product_search", "response_style": "structured", "reason": "" }
}
```

- [ ] **Step 2: Capture normalize, filters, shortlist, and analysis with the same schema**

```json
{
  "stage": "normalize",
  "ai_input": { "messages": [] },
  "ai_output": { "product_type": "monitor", "query": "монитор", "price_min": 17500, "price_max": 36750, "brand": "", "wishes": ["27_inch", "1440p", "ips", "height_adjustable"], "soft_wishes": [] }
}
```

- [ ] **Step 3: Capture DNS stages as structured JSON**

```json
{
  "stage": "filters_map",
  "requested": { "section_url": "" },
  "received": { "count": 0, "filters": [] }
}
```

### Task 3: Export the trace atomically

**Files:**
- Create all files under `C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k\`

- [ ] **Step 1: Generate the trace from one live request**

Run the export script against:
`Найди хороший монитор для программиста 27 дюймов, 1440p, IPS, с регулировкой высоты, до 35000 рублей`

- [ ] **Step 2: Write the files in one pass**

Each file must contain valid JSON or Markdown and must be non-empty.

- [ ] **Step 3: Sanity-check the trace**

Run:
```powershell
Get-ChildItem 'C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k'
```
Expected: 11 files, all with stable names.

### Task 4: Validate the output

**Files:**
- Test: `C:\1all_project\Dns_test_standalone\artifacts\dns_traces\monitor_27_1440p_height_35k\99_full_request_and_answer.md`

- [ ] **Step 1: Check the summary file**

Expected: one full request section and one full answer section, no truncation.

- [ ] **Step 2: Check the stage files**

Expected: each stage file contains both what was sent and what was received.

- [ ] **Step 3: Confirm no bot behavior changed**

Expected: this is trace export only; no production logic changes.


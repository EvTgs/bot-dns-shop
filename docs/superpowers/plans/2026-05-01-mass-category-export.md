# Mass Category Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one export flow that builds category snapshots for smartphones, tablets, and laptops: each category gets a filter dump and a device dump.

**Architecture:** Reuse the existing DNS parser and orchestrator entrypoints, but drive them from one parameterized export script that loops over the three categories. The export should write only to `backend/test/snapshots`, keep filter dumps separate from product dumps, and avoid changing core parsing behavior. Keep the implementation small: one new script, one small menu/helper integration if needed, and path updates only where required.

**Tech Stack:** Python 3.11+, existing `app` package, `dns_search_parser`, `ai_orchestrator`, `json`, `pathlib`, `subprocess`, `pytest`.

---

### Task 1: Add a category export script

**Files:**
- Create: `C:\1all_project\Dns_project\DNSpars_v1_tgbot\scripts\export_category_snapshots.py`
- Test: `C:\1all_project\Dns_project\DNSpars_v1_tgbot\backend\test\python_test\test_category_export.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

def test_category_export_writes_six_files(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    result = export_category_snapshots(out_dir, categories=["smartphone", "tablet", "laptop"])
    assert sorted(p.name for p in out_dir.iterdir()) == [
        "01_laptop_devices.md",
        "01_laptop_filters.md",
        "01_smartphone_devices.md",
        "01_smartphone_filters.md",
        "01_tablet_devices.md",
        "01_tablet_filters.md",
    ]
    assert result["categories"] == ["smartphone", "tablet", "laptop"]
    assert result["files_written"] == 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest C:\1all_project\Dns_project\DNSpars_v1_tgbot\backend\test\python_test\test_category_export.py -v`
Expected: FAIL because `export_category_snapshots` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def export_category_snapshots(out_dir: Path, categories: list[str]) -> dict[str, object]:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest C:\1all_project\Dns_project\DNSpars_v1_tgbot\backend\test\python_test\test_category_export.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/export_category_snapshots.py backend/test/python_test/test_category_export.py
git commit -m "feat: add category snapshot export"
```

### Task 2: Wire the export into the existing menu

**Files:**
- Modify: `C:\1all_project\Dns_project\DNSpars_v1_tgbot\backend\src\app\windows_menu.py`
- Test: `C:\1all_project\Dns_project\DNSpars_v1_tgbot\backend\test\python_test\test_windows_menu.py`

- [ ] **Step 1: Write the failing test**

```python
def test_menu_contains_category_export_action() -> None:
    assert parse_menu_choice("7") == "export_category_snapshots"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest C:\1all_project\Dns_project\DNSpars_v1_tgbot\backend\test\python_test\test_windows_menu.py -v`
Expected: FAIL because menu option 7 is missing.

- [ ] **Step 3: Write minimal implementation**

```python
MENU_ACTIONS["7"] = "export_category_snapshots"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest C:\1all_project\Dns_project\DNSpars_v1_tgbot\backend\test\python_test\test_windows_menu.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/windows_menu.py backend/test/python_test/test_windows_menu.py
git commit -m "feat: add category export to menu"
```

### Task 3: Move export outputs to the new snapshot layout

**Files:**
- Modify: `C:\1all_project\Dns_project\DNSpars_v1_tgbot\backend\src\app\project_paths.py`
- Modify: `C:\1all_project\Dns_project\DNSpars_v1_tgbot\scripts\export_category_snapshots.py`
- Test: `C:\1all_project\Dns_project\DNSpars_v1_tgbot\backend\test\python_test\test_project_paths.py`

- [ ] **Step 1: Write the failing test**

```python
def test_snapshot_paths_point_under_backend_test() -> None:
    from app.project_paths import ARTIFACTS_DIR, SNAPSHOTS_DIR
    assert "backend\\test\\artifacts" in str(ARTIFACTS_DIR)
    assert "backend\\test\\snapshots" in str(SNAPSHOTS_DIR)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest C:\1all_project\Dns_project\DNSpars_v1_tgbot\backend\test\python_test\test_project_paths.py -v`
Expected: FAIL until paths are updated.

- [ ] **Step 3: Write minimal implementation**

```python
ARTIFACTS_DIR = PROJECT_ROOT / "backend" / "test" / "artifacts"
SNAPSHOTS_DIR = PROJECT_ROOT / "backend" / "test" / "snapshots"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest C:\1all_project\Dns_project\DNSpars_v1_tgbot\backend\test\python_test\test_project_paths.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/project_paths.py scripts/export_category_snapshots.py backend/test/python_test/test_project_paths.py
git commit -m "fix: route snapshot paths into backend test tree"
```


from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from app.windows_menu import parse_menu_choice


def test_menu_has_category_export_action() -> None:
    assert parse_menu_choice("7") == "export_category_snapshots"


def test_category_export_script_writes_six_snapshot_files(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[3]
    script_path = project_root / "scripts" / "export_category_snapshots.py"
    out_dir = tmp_path / "ai_total"
    spec = importlib.util.spec_from_file_location("export_category_snapshots", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.inspect_dns_section_filters = lambda section_url: {"section_url": section_url, "filters": []}
    module.collect_products_by_url = lambda section_url, limit, allow_browser=True: (
        [{"name": "Dummy", "price": 1, "url": section_url, "code": "x"}],
        "httpx",
        section_url,
        section_url,
    )
    result = module.export_category_snapshots(out_dir)
    assert result["files_written"] == 6
    assert sorted(p.name for p in out_dir.iterdir()) == [
        "01_laptop_devices.md",
        "01_laptop_filters.md",
        "01_smartphone_devices.md",
        "01_smartphone_filters.md",
        "01_tablet_devices.md",
        "01_tablet_filters.md",
    ]

from __future__ import annotations

import importlib.util
from pathlib import Path


def load_module(script_name: str):
    project_root = Path(__file__).resolve().parents[3]
    script_path = project_root / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_compact_snapshot_file_removes_urls_and_compacts_specs(tmp_path: Path) -> None:
    module = load_module("compact_dns_snapshot.py")
    input_path = tmp_path / "source.md"
    output_path = tmp_path / "compact.md"
    input_path.write_text(
        """# source

```json
{
  "items": [
    {
      "name": "A",
      "url": "https://example.com/a",
      "specs": [
        {"name": "Тип матрицы", "value": "AMOLED"},
        {"name": "Дополнительно", "value": "NFC"}
      ]
    }
  ]
}
```
""",
        encoding="utf-8",
    )

    result = module.compact_snapshot_file(input_path, output_path, specs_mode="named_join", short_keys=True)

    assert result["output"] == str(output_path)
    text = output_path.read_text(encoding="utf-8")
    assert "https://example.com/a" not in text
    assert "Тип матрицы: AMOLED; Дополнительно: NFC" in text

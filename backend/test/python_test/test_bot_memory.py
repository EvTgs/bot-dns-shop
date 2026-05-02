from pathlib import Path

from app.bot_memory import append_turn, load_chat_context, load_chat_memory, reset_chat_memory, save_chat_context, write_memory_payload


def test_memory_is_scoped_by_chat_id(tmp_path: Path) -> None:
    path = tmp_path / "memory.json"

    append_turn(10, "user", "one", path=path)
    append_turn(20, "user", "two", path=path)

    assert load_chat_memory(10, path=path) == [{"role": "user", "content": "one"}]
    assert load_chat_memory(20, path=path) == [{"role": "user", "content": "two"}]


def test_reset_clears_only_current_chat(tmp_path: Path) -> None:
    path = tmp_path / "memory.json"
    append_turn(10, "user", "one", path=path)
    append_turn(20, "user", "two", path=path)

    reset_chat_memory(10, path=path)

    assert load_chat_memory(10, path=path) == []
    assert load_chat_memory(20, path=path) == [{"role": "user", "content": "two"}]


def test_memory_keeps_last_eight_turns(tmp_path: Path) -> None:
    path = tmp_path / "memory.json"

    for index in range(10):
        append_turn(10, "user", f"msg-{index}", path=path)

    history = load_chat_memory(10, path=path)
    assert len(history) == 8
    assert history[0]["content"] == "msg-2"
    assert history[-1]["content"] == "msg-9"


def test_memory_saves_context_separately_from_history(tmp_path: Path) -> None:
    path = tmp_path / "memory.json"
    append_turn(10, "user", "one", path=path)
    save_chat_context(10, {"resolved_url": "https://example", "products": [{"name": "A"}]}, path=path)

    assert load_chat_memory(10, path=path) == [{"role": "user", "content": "one"}]
    assert load_chat_context(10, path=path) == {"resolved_url": "https://example", "products": [{"name": "A"}]}


def test_memory_write_is_atomic_via_temp_file_replace(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "memory.json"
    path.write_text("{}", encoding="utf-8")
    original_write_text = Path.write_text
    original_replace = Path.replace
    replace_calls: list[tuple[str, str]] = []

    def guarded_write_text(self: Path, *args, **kwargs):
        if self == path:
            raise AssertionError("target file must not be written directly")
        return original_write_text(self, *args, **kwargs)

    def tracked_replace(self: Path, target: Path | str):
        replace_calls.append((self.name, Path(target).name))
        return original_replace(self, target)

    monkeypatch.setattr(Path, "write_text", guarded_write_text)
    monkeypatch.setattr(Path, "replace", tracked_replace)

    write_memory_payload(path, {"10": {"history": [{"role": "user", "content": "one"}]}})

    assert load_chat_memory(10, path=path) == [{"role": "user", "content": "one"}]
    assert replace_calls
    assert replace_calls[-1][1] == "memory.json"

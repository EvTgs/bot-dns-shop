from __future__ import annotations

import re
import random


MATRIX_NOISE_CHARS = "░▒▓01"


def build_matrix_animation_frames(text: str, steps: int = 18, rng_seed: int | None = None) -> list[str]:
    final_text = trim_matrix_text(text)
    if not final_text:
        return ["Готово."]
    reveal_positions = [index for index, char in enumerate(final_text) if not char.isspace()]
    if not reveal_positions:
        return [final_text]
    total_steps = max(2, steps)
    rng = random.Random(rng_seed)
    frames: list[str] = []
    for step_index in range(total_steps - 1):
        visible_count = int(len(reveal_positions) * step_index / (total_steps - 1))
        visible_positions = set(reveal_positions[:visible_count])
        frame_chars: list[str] = []
        for char_index, char in enumerate(final_text):
            if char.isspace() or char_index in visible_positions:
                frame_chars.append(char)
                continue
            frame_chars.append(rng.choice(MATRIX_NOISE_CHARS))
        frame = "".join(frame_chars)
        if not frames or frames[-1] != frame:
            frames.append(frame)
    if not frames or frames[-1] != final_text:
        frames.append(final_text)
    return frames


def build_block_reveal_frames(text: str, steps: int = 18, rng_seed: int | None = None) -> list[str]:
    final_text = trim_matrix_text(text).strip("\n")
    if not final_text:
        return ["Готово."]
    lines = final_text.splitlines()
    if len(lines) == 1:
        return build_matrix_animation_frames(final_text, steps=steps, rng_seed=rng_seed)

    total_steps = max(2, steps)
    max_reveals = min(len(lines), total_steps - 1)
    rng = random.Random(rng_seed)
    frames: list[str] = [build_noise_line(rng)]
    for visible_count in range(1, max_reveals):
        frames.append(build_revealed_lines_frame(lines[:visible_count], rng))
    if frames[-1] != final_text:
        frames.append(final_text)
    return dedupe_frames(frames)


def build_progressive_reveal_frames(
    text: str,
    reveal_size: int,
    unit: str = "char",
    rng_seed: int | None = None,
) -> list[str]:
    final_text = trim_matrix_text(text).strip("\n")
    if not final_text:
        return ["Готово."]
    rng = random.Random(rng_seed)
    if unit == "word":
        return build_word_reveal_frames(final_text, rng)
    return build_char_reveal_frames(final_text, max(1, reveal_size), rng)


def build_char_reveal_frames(text: str, reveal_size: int, rng: random.Random) -> list[str]:
    total_visible = count_nonspace_chars(text)
    if total_visible <= 0:
        return [text]
    frames: list[str] = [build_noise_line(rng)]
    for visible_count in range(reveal_size, total_visible, reveal_size):
        prefix = take_nonspace_char_prefix(text, visible_count)
        frames.append(append_noise_tail(prefix, build_noise_line(rng)))
    if frames[-1] != text:
        frames.append(text)
    return dedupe_frames(frames)


def build_word_reveal_frames(text: str, rng: random.Random) -> list[str]:
    total_words = count_words(text)
    if total_words <= 0:
        return [text]
    frames: list[str] = [build_noise_line(rng)]
    for visible_count in range(1, total_words):
        prefix = take_word_prefix(text, visible_count)
        frames.append(append_noise_tail(prefix, build_noise_line(rng)))
    if frames[-1] != text:
        frames.append(text)
    return dedupe_frames(frames)


def build_noise_line(rng: random.Random) -> str:
    return f"{rng.choice(('▓▓░', '▒▓01', '░▒▓', '01▓', '▓01'))} {rng.choice(('▓▓░', '▒▓01', '░▒▓', '01▓', '▓01'))}"


def append_noise_tail(prefix: str, noise: str) -> str:
    if not prefix:
        return noise
    if prefix.endswith((" ", "\n", "\t")):
        return f"{prefix}{noise}"
    return f"{prefix} {noise}"


def take_nonspace_char_prefix(text: str, visible_count: int) -> str:
    if visible_count <= 0:
        return ""
    seen = 0
    for index, char in enumerate(text):
        if not char.isspace():
            seen += 1
        if seen >= visible_count:
            return text[: index + 1]
    return text


def take_word_prefix(text: str, visible_count: int) -> str:
    if visible_count <= 0:
        return ""
    seen = 0
    for match in re.finditer(r"\S+|\s+", text):
        token = match.group(0)
        if token.isspace():
            continue
        seen += 1
        if seen >= visible_count:
            return text[: match.end()]
    return text


def count_nonspace_chars(text: str) -> int:
    return sum(1 for char in text if not char.isspace())


def count_words(text: str) -> int:
    return sum(1 for match in re.finditer(r"\S+", text))


def build_revealed_lines_frame(lines: list[str], rng: random.Random) -> str:
    if not lines:
        return build_noise_line(rng)
    noise = build_noise_line(rng)
    if len(lines) == 1:
        return f"{lines[0]} {noise}"
    return "\n".join([*lines[:-1], f"{lines[-1]} {noise}"])


def dedupe_frames(frames: list[str]) -> list[str]:
    deduped: list[str] = []
    for frame in frames:
        if not deduped or deduped[-1] != frame:
            deduped.append(frame)
    return deduped


def trim_matrix_text(value: str) -> str:
    if len(value) <= 3900:
        return value
    return value[:3897].rstrip() + "..."

from app.telegram_matrix import (
    build_block_reveal_frames,
    build_matrix_animation_frames,
    build_progressive_reveal_frames,
)


def test_build_matrix_animation_frames_reveals_final_message() -> None:
    frames = build_matrix_animation_frames("ABC\n12", steps=4, rng_seed=7)

    assert frames
    assert frames[-1] == "ABC\n12"
    assert any(any(char in frame for char in "░▒▓01") for frame in frames[:-1])
    assert len(frames) >= 4


def test_build_block_reveal_frames_reveals_final_card() -> None:
    frames = build_block_reveal_frames("A\nB\nC", steps=4, rng_seed=7)

    assert frames
    assert frames[-1] == "A\nB\nC"
    assert any(any(char in frame for char in "░▒▓01") for frame in frames[:-1])


def test_build_progressive_reveal_frames_by_three_characters() -> None:
    frames = build_progressive_reveal_frames("это тест это тест", reveal_size=3, unit="char", rng_seed=7)

    assert frames
    assert frames[-1] == "это тест это тест"
    assert frames[1].startswith("это")
    assert any(char in frames[1] for char in "░▒▓01")


def test_build_progressive_reveal_frames_by_word() -> None:
    frames = build_progressive_reveal_frames("это тест это тест", reveal_size=1, unit="word", rng_seed=7)

    assert frames
    assert frames[-1] == "это тест это тест"
    assert frames[1].startswith("это")
    assert frames[2].startswith("это тест")

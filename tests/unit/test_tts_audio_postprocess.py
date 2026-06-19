import numpy as np

from modal_apps.sauti_tts import _apply_edge_fades, _iter_click_safe_chunks


def test_edge_fades_shape_only_requested_outer_edges() -> None:
    audio = np.ones(1_000, dtype=np.float32) * 0.5

    shaped = _apply_edge_fades(audio, 48_000, fade_in=True, fade_out=True)

    assert shaped[0] == 0.0
    assert shaped[-1] == 0.0
    assert shaped[500] == 0.5


def test_click_safe_chunks_hold_back_last_chunk_for_fade_out() -> None:
    chunks = iter(
        [
            np.ones(1_000, dtype=np.float32) * 0.5,
            np.ones(1_000, dtype=np.float32) * 0.25,
        ]
    )

    shaped = list(_iter_click_safe_chunks(chunks, 48_000))

    assert len(shaped) == 2
    assert shaped[0][0] == 0.0
    assert shaped[0][-1] == 0.5
    assert shaped[1][0] == 0.25
    assert shaped[1][-1] == 0.0

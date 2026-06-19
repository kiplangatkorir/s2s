"""Modal TTS app for the MsingiAI Sauti S2S pipeline.

This wraps the VoxCPM2 Swahili LoRA checkpoint selected from the v2 benchmark:

    volume: sauti-tts-v2-data
    mount:  /vol
    LoRA:   /vol/checkpoints/voxcpm2_sw_lora_waxal_s300/latest

Deploy:
    modal deploy modal_apps/sauti_tts.py
"""

from __future__ import annotations

import io
import json
import re
import time
from pathlib import Path
from typing import Iterator

import modal
import numpy as np


VOL = "/vol"
DATA_DIR = f"{VOL}/data/waxal_sw"
CHECKPOINT_DIR = f"{VOL}/checkpoints/voxcpm2_sw_lora_waxal_s300/latest"
VOXCPM_MODEL_DIR = f"{VOL}/models/VoxCPM2"
VOXCPM_REPO = "https://github.com/OpenBMB/VoxCPM"
VOXCPM_REF = "main"
VOXCPM_DIR = "/opt/VoxCPM"

SAMPLE_RATE = 48_000
CHANNELS = 1
SYNTHESIS_CHUNK_CHARS = 120
TTS_CFG_VALUE = 1.8
TTS_INFERENCE_TIMESTEPS = 10
EDGE_FADE_MS = 6.0
PCM_PEAK_LIMIT = 0.98


tts_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04",
        add_python="3.11",
    )
    .env({"CUDA_HOME": "/usr/local/cuda", "PYTHONUTF8": "1"})
    .apt_install("git", "ffmpeg", "libsndfile1", "build-essential")
    .run_commands(
        f"git clone {VOXCPM_REPO} {VOXCPM_DIR}",
        f"cd {VOXCPM_DIR} && git checkout {VOXCPM_REF} && pip install -e .",
    )
    .pip_install("huggingface_hub", "safetensors", "soundfile", "numpy<2")
)

app = modal.App("msingiai-sauti-tts", image=tts_image)

tts_volume = modal.Volume.from_name("sauti-tts-v2-data", create_if_missing=False)
hf_secret = modal.Secret.from_name("hf-secret", required_keys=["HF_TOKEN"])


@app.cls(
    gpu="L4",
    min_containers=1,
    volumes={VOL: tts_volume},
    secrets=[hf_secret],
    timeout=300,
    startup_timeout=900,
)
class SautiTTS:
    """Persistent GPU TTS worker backed by VoxCPM2 plus the WAXAL Swahili LoRA."""

    @modal.enter()
    def load_model(self) -> None:
        import os
        from huggingface_hub import snapshot_download

        model_dir = Path(VOXCPM_MODEL_DIR)
        if not (model_dir / "config.json").exists():
            print(f"[SautiTTS] Caching VoxCPM2 base model to {model_dir}")
            model_dir.mkdir(parents=True, exist_ok=True)
            snapshot_download(
                "openbmb/VoxCPM2",
                local_dir=str(model_dir),
                token=os.environ.get("HF_TOKEN"),
            )
            tts_volume.commit()

        lora_dir = Path(CHECKPOINT_DIR)
        if not (lora_dir / "lora_weights.safetensors").exists():
            raise FileNotFoundError(f"{lora_dir}/lora_weights.safetensors missing")

        from voxcpm import VoxCPM

        lora_config = _load_lora_config(lora_dir)
        print(f"[SautiTTS] Loading VoxCPM2 from {model_dir}")
        print(f"[SautiTTS] Loading Swahili LoRA from {lora_dir}")
        self.model = VoxCPM.from_pretrained(
            str(model_dir),
            load_denoiser=False,
            optimize=False,
            lora_config=lora_config,
            lora_weights_path=str(lora_dir),
        )
        self.sample_rate = int(getattr(self.model.tts_model, "sample_rate", SAMPLE_RATE))
        self.voices = _load_voice_prompts()
        print(f"[SautiTTS] Ready at {self.sample_rate} Hz. Voices: {list(self.voices)}")

    @modal.method()
    def synthesise_stream(
        self,
        text: str,
        language: str = "sw",
        voice: str | None = None,
        output_format: str = "pcm",
    ) -> Iterator[bytes]:
        """Synthesize text and yield raw int16 PCM or Opus chunks."""
        del language
        text = normalize_for_tts(text)
        if not text:
            return

        voice_name = (voice or "female").lower()
        voice_cfg = self.voices.get(voice_name, self.voices["female"])
        t0 = time.perf_counter()

        first_audio_logged = False
        for i, phrase in enumerate(_split_for_synthesis(text, SYNTHESIS_CHUNK_CHARS)):
            audio_chunks = self._synthesise_phrase_chunks(phrase, voice_cfg, seed_offset=i)
            for audio_float32 in _iter_click_safe_chunks(audio_chunks, self.sample_rate):
                chunks = (
                    _encode_opus(audio_float32, self.sample_rate)
                    if output_format == "opus"
                    else _encode_pcm(audio_float32)
                )
                for chunk in chunks:
                    if not first_audio_logged:
                        elapsed = (time.perf_counter() - t0) * 1000
                        print(
                            f"[SautiTTS] First audio chunk in {elapsed:.1f}ms: "
                            f"{phrase[:60]!r}"
                        )
                        first_audio_logged = True
                    yield chunk

        for i, phrase in enumerate(_split_for_synthesis(text, SYNTHESIS_CHUNK_CHARS)):
            torch.manual_seed(42 + i)

            # VoxCPM's streaming API yields partial waveforms as it decodes
            if hasattr(self.model, "generate_streaming"):
                audio_iter = self.model.generate_streaming(
                    text=phrase,
                    prompt_wav_path=voice_cfg["wav"],
                    prompt_text=voice_cfg["text"],
                    reference_wav_path=voice_cfg["wav"],
                    cfg_value=2.0,
                    inference_timesteps=10,
                    normalize=True,
                    denoise=False,
                    retry_badcase=True,
                )
            else:
                # Fallback to full phrase generation if streaming isn't available
                audio_iter = [self._synthesise_phrase(phrase, voice_cfg, seed_offset=i)]

            prev_chunk = None
            is_first_chunk = True

            for audio_float32 in audio_iter:
                if isinstance(audio_float32, torch.Tensor):
                    audio_float32 = audio_float32.detach().cpu().numpy()
                audio_float32 = np.asarray(audio_float32, dtype=np.float32)
                if audio_float32.size == 0:
                    continue

                audio_float32 = np.clip(audio_float32, -1.0, 1.0)

                # Shape the start edge of the phrase
                if is_first_chunk:
                    audio_float32 = _fade_in(audio_float32, fade_ms=10, sample_rate=self.sample_rate)
                    is_first_chunk = False

                if prev_chunk is not None:
                    chunks = (
                        _encode_opus(prev_chunk, self.sample_rate)
                        if output_format == "opus"
                        else _encode_pcm(prev_chunk)
                    )
                    for chunk in chunks:
                        yield chunk

                    if i == 0 and prev_chunk is not None and not hasattr(self, '_logged_first'):
                        self._logged_first = True
                        elapsed = (time.perf_counter() - t0) * 1000
                        print(f"[SautiTTS] First audio chunk in {elapsed:.1f}ms: {phrase[:60]!r}")

                prev_chunk = audio_float32

            # The very last chunk of the phrase needs fade out
            if prev_chunk is not None:
                prev_chunk = _fade_out(prev_chunk, fade_ms=10, sample_rate=self.sample_rate)
                chunks = (
                    _encode_opus(prev_chunk, self.sample_rate)
                    if output_format == "opus"
                    else _encode_pcm(prev_chunk)
                )
                for chunk in chunks:
                    yield chunk

        if hasattr(self, '_logged_first'):
            del self._logged_first
        total = (time.perf_counter() - t0) * 1000
        print(f"[SautiTTS] Synthesis complete in {total:.1f}ms: {text[:80]!r}")

    def _synthesise_phrase_chunks(
        self,
        text: str,
        voice_cfg: dict,
        seed_offset: int = 0,
    ) -> Iterator[np.ndarray]:
        import torch

        torch.manual_seed(42 + seed_offset)
        kwargs = dict(
            text=normalize_for_tts(text),
            prompt_wav_path=voice_cfg["wav"],
            prompt_text=voice_cfg["text"],
            reference_wav_path=voice_cfg["wav"],
            cfg_value=TTS_CFG_VALUE,
            inference_timesteps=TTS_INFERENCE_TIMESTEPS,
            normalize=False,
            denoise=False,
            retry_badcase=True,
        )

        if hasattr(self.model, "generate_streaming"):
            for chunk in self.model.generate_streaming(**kwargs):
                yield np.asarray(chunk, dtype=np.float32).reshape(-1)
            return

        audio = np.asarray(self.model.generate(**kwargs), dtype=np.float32).reshape(-1)
        if audio.size == 0:
            audio = np.zeros(self.sample_rate // 4, dtype=np.float32)
        yield audio

    @modal.method()
    def synthesise_full(self, text: str, language: str = "sw", voice: str | None = None) -> bytes:
        chunks = list(self.synthesise_stream.local(text, language=language, voice=voice))
        return _pcm_to_wav(b"".join(chunks), self.sample_rate)


@app.function(secrets=[hf_secret], volumes={VOL: tts_volume})
@modal.fastapi_endpoint(method="POST")
async def synthesise_endpoint(item: dict) -> dict:
    import base64

    text = item.get("text", "")
    language = item.get("language", "sw")
    voice = item.get("voice")

    tts = SautiTTS()
    wav_bytes = tts.synthesise_full.remote(text, language=language, voice=voice)
    return {"audio_b64": base64.b64encode(wav_bytes).decode(), "sample_rate": SAMPLE_RATE}


def _load_lora_config(lora_dir: Path):
    cfg_path = lora_dir / "lora_config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"{cfg_path} missing")
    info = json.loads(cfg_path.read_text(encoding="utf-8"))
    from voxcpm.model.voxcpm2 import LoRAConfig

    return LoRAConfig(**info.get("lora_config", {}))


def _load_voice_prompts() -> dict[str, dict[str, str]]:
    male_id, male_text, female_id, female_text = _pick_balanced_prompts()
    return {
        "male": {
            "wav": f"{DATA_DIR}/wavs/{male_id}.wav",
            "text": normalize_for_tts(male_text),
        },
        "female": {
            "wav": f"{DATA_DIR}/wavs/{female_id}.wav",
            "text": normalize_for_tts(female_text),
        },
        "default": {
            "wav": f"{DATA_DIR}/wavs/{female_id}.wav",
            "text": normalize_for_tts(female_text),
        },
    }


def _pick_balanced_prompts(male_spk: str = "8", female_spk: str = "1") -> tuple[str, str, str, str]:
    import soundfile as sf

    speaker_map = json.loads((Path(DATA_DIR) / "speaker_map.json").read_text(encoding="utf-8"))
    rows: dict[str, str] = {}
    for line in (Path(DATA_DIR) / "metadata_filtered.csv").read_text(encoding="utf-8").splitlines():
        if line:
            clip_id, _raw, norm = line.split("|", 2)
            rows[clip_id] = norm

    def speech_rate(text: str, duration: float) -> float:
        return len([word for word in text.split() if word]) / max(duration, 0.001)

    def pick_prompt(speaker: str) -> tuple[str, str]:
        preferred: list[tuple[float, float, str, str, str]] = []
        fallback: list[tuple[float, float, str, str, str]] = []
        for clip_id, norm in rows.items():
            if speaker_map.get(clip_id, {}).get("speaker") != speaker:
                continue
            wav = Path(DATA_DIR) / "wavs" / f"{clip_id}.wav"
            duration = sf.info(str(wav)).duration
            rate = speech_rate(norm, duration)
            score = (abs(rate - 1.45), abs(duration - 4.8), clip_id, clip_id, norm)
            if 4.0 <= duration <= 5.4:
                preferred.append(score)
            elif 2.5 <= duration <= 6.0:
                fallback.append(score)
        pool = preferred or fallback
        if not pool:
            raise RuntimeError(f"No 2.5-6s prompt clip for speaker {speaker}")
        _rate_score, _duration_score, _sort_id, clip_id, norm = sorted(pool)[0]
        print(f"[SautiTTS] Speaker {speaker} prompt: {clip_id}")
        return clip_id, norm

    male_id, male_text = pick_prompt(male_spk)
    female_id, female_text = pick_prompt(female_spk)
    return male_id, male_text, female_id, female_text


UNITS = [
    "sifuri",
    "moja",
    "mbili",
    "tatu",
    "nne",
    "tano",
    "sita",
    "saba",
    "nane",
    "tisa",
]
TENS = {
    1: "kumi",
    2: "ishirini",
    3: "thelathini",
    4: "arobaini",
    5: "hamsini",
    6: "sitini",
    7: "sabini",
    8: "themanini",
    9: "tisini",
}
ABBREVIATIONS = {
    "Dkt.": "Daktari",
    "Bw.": "Bwana",
    "Bi.": "Bibi",
    "Prof.": "Profesa",
    "n.k.": "na kadhalika",
    "k.m.": "kwa mfano",
    "k.v.": "kama vile",
}


def normalize_for_tts(text: str) -> str:
    for abbr, full in ABBREVIATIONS.items():
        text = text.replace(abbr, full)
    text = re.sub(r"\d[\d,]*(?:\.\d+)?", _verbalize_number_match, text)
    return re.sub(r"\s+", " ", text).strip()


def _verbalize_number_match(match: re.Match) -> str:
    token = match.group(0).replace(",", "")
    if "." in token:
        whole, frac = token.split(".", 1)
        frac_words = " ".join(UNITS[int(d)] for d in frac if d.isdigit())
        return f"{cardinal(int(whole))} nukta {frac_words}"
    return cardinal(int(token))


def cardinal(n: int) -> str:
    if n < 0:
        return "hasi " + cardinal(-n)
    if n < 10:
        return UNITS[n]
    if n < 100:
        tens, unit = divmod(n, 10)
        word = TENS[tens]
        return word if unit == 0 else f"{word} na {UNITS[unit]}"
    if n < 1_000:
        head, rest = divmod(n, 100)
        word = f"mia {UNITS[head]}"
    elif n < 1_000_000:
        head, rest = divmod(n, 1_000)
        word = f"elfu {cardinal(head)}"
    elif n < 1_000_000_000:
        head, rest = divmod(n, 1_000_000)
        word = f"milioni {cardinal(head)}"
    else:
        head, rest = divmod(n, 1_000_000_000)
        word = f"bilioni {cardinal(head)}"
    if rest == 0:
        return word
    if rest < 10 or (rest < 100 and rest % 10 == 0):
        return f"{word} na {cardinal(rest)}"
    return f"{word} {cardinal(rest)}"


def _split_for_synthesis(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    words = text.split()
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > max_chars:
            chunks.append(current.strip())
            current = word
        else:
            current = f"{current} {word}".strip() if current else word
    if current:
        chunks.append(current.strip())
    return chunks


def _iter_click_safe_chunks(
    chunks: Iterator[np.ndarray],
    sample_rate: int,
) -> Iterator[np.ndarray]:
    previous: np.ndarray | None = None
    first = True

    for chunk in chunks:
        audio = np.asarray(chunk, dtype=np.float32).reshape(-1)
        if audio.size == 0:
            continue
        if previous is not None:
            yield _apply_edge_fades(
                previous,
                sample_rate,
                fade_in=first,
                fade_out=False,
            )
            first = False
        previous = audio

    if previous is not None:
        yield _apply_edge_fades(
            previous,
            sample_rate,
            fade_in=first,
            fade_out=True,
        )


def _apply_edge_fades(
    audio: np.ndarray,
    sample_rate: int,
    *,
    fade_in: bool,
    fade_out: bool,
) -> np.ndarray:
    shaped = np.nan_to_num(np.asarray(audio, dtype=np.float32).reshape(-1)).copy()
    if shaped.size == 0:
        return shaped

    np.clip(shaped, -PCM_PEAK_LIMIT, PCM_PEAK_LIMIT, out=shaped)
    fade_samples = min(int(sample_rate * EDGE_FADE_MS / 1000), shaped.size // 2)
    if fade_samples <= 1:
        return shaped

    curve = np.sin(np.linspace(0.0, np.pi / 2.0, fade_samples, dtype=np.float32)) ** 2
    if fade_in:
        shaped[:fade_samples] *= curve
    if fade_out:
        shaped[-fade_samples:] *= curve[::-1]
    return shaped


def _encode_pcm(audio: np.ndarray, chunk_samples: int = 4096) -> Iterator[bytes]:
    audio_int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
    raw = audio_int16.tobytes()
    for i in range(0, len(raw), chunk_samples * 2):
        yield raw[i : i + chunk_samples * 2]


def _encode_opus(audio: np.ndarray, sample_rate: int) -> Iterator[bytes]:
    try:
        import opuslib
    except ImportError:
        yield from _encode_pcm(audio)
        return

    encoder = opuslib.Encoder(sample_rate, 1, opuslib.APPLICATION_VOIP)
    frame_size = 960 if sample_rate == 48_000 else int(sample_rate * 0.02)
    audio_int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)

    for i in range(0, len(audio_int16), frame_size):
        frame = audio_int16[i : i + frame_size]
        if len(frame) < frame_size:
            frame = np.pad(frame, (0, frame_size - len(frame)))
        yield encoder.encode(frame.tobytes(), frame_size)


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


@app.local_entrypoint()
def main(
    text: str = "Habari yako! Mimi ni msaidizi wa sauti.",
    language: str = "sw",
    voice: str = "female",
    output: str = "test_output.wav",
) -> None:
    tts = SautiTTS()
    t0 = time.perf_counter()
    pcm_chunks = []
    for i, chunk in enumerate(tts.synthesise_stream.remote_gen(text, language=language, voice=voice)):
        pcm_chunks.append(chunk)
        if i == 0:
            print(f"[local] First audio chunk in {(time.perf_counter() - t0) * 1000:.1f}ms")

    wav = _pcm_to_wav(b"".join(pcm_chunks), SAMPLE_RATE)
    with open(output, "wb") as handle:
        handle.write(wav)
    print(f"[local] Saved {output}")


def _fade_in(audio: np.ndarray, fade_ms: int = 10, sample_rate: int = 48000) -> np.ndarray:
    fade_samples = int(sample_rate * fade_ms / 1000)
    if fade_samples == 0 or len(audio) == 0:
        return audio
    fade_samples = min(fade_samples, len(audio))
    fade = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
    out = audio.copy()
    out[:fade_samples] *= fade
    return out

def _fade_out(audio: np.ndarray, fade_ms: int = 10, sample_rate: int = 48000) -> np.ndarray:
    fade_samples = int(sample_rate * fade_ms / 1000)
    if fade_samples == 0 or len(audio) == 0:
        return audio
    fade_samples = min(fade_samples, len(audio))
    fade = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
    out = audio.copy()
    out[-fade_samples:] *= fade
    return out

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import threading
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
DEFAULT_MELOTTS_MODEL = "melotts/KR"
DEFAULT_PIPER_MODEL = "piper/default"
DEFAULT_PIPER_MODEL_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
    "en/en_US/lessac/medium/en_US-lessac-medium.onnx"
)
DEFAULT_PIPER_CONFIG_URL = f"{DEFAULT_PIPER_MODEL_URL}.json"
DEFAULT_MODELS = (
    DEFAULT_MODEL,
    DEFAULT_MELOTTS_MODEL,
    DEFAULT_PIPER_MODEL,
    "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
)
DEFAULT_KOREAN_SPEAKER = "Sohee"
DEFAULT_LANGUAGE = "Korean"


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice: str = Field(default="default", max_length=120)
    model: str = Field(default=DEFAULT_MODEL, max_length=4096)
    sample_rate: int = Field(default=24000, ge=8000, le=48000)
    channels: Literal[1, 2] = 1
    sample_width: Literal[2] = 2
    format: Literal["pcm_s16le"] = "pcm_s16le"
    chunk_id: str | None = Field(default=None, max_length=80)
    language: str | None = Field(default=None, max_length=80)
    instruct: str | None = Field(default=None, max_length=1200)
    ref_audio: str | None = Field(default=None, max_length=4096)
    ref_text: str | None = Field(default=None, max_length=4000)


@dataclass(slots=True)
class LoadedModel:
    model_id: str
    model: object


app = FastAPI(title="Jarvis TTS Runtime")
_model_lock = threading.Lock()
_loaded_model: LoadedModel | None = None
_loaded_melo_models: dict[str, object] = {}
_loaded_piper_models: dict[str, object] = {}
_preload_status = "disabled"
_preload_error: str | None = None
_preloaded_models: list[str] = []


@app.on_event("startup")
async def preload_default_model() -> None:
    global _preload_error, _preload_status, _preloaded_models
    if not _env_flag("JARVIS_TTS_RUNTIME_PRELOAD_MODEL", default=True):
        _preload_status = "disabled"
        return

    model_ids = _preload_models()
    _preload_status = "loading"
    _preload_error = None
    _preloaded_models = []
    try:
        for model_id in model_ids:
            await asyncio.to_thread(_warm_model_sync, model_id)
            _preloaded_models.append(model_id)
    except Exception as exc:
        _preload_status = "failed"
        _preload_error = str(exc)
        if _env_flag("JARVIS_TTS_RUNTIME_PRELOAD_REQUIRED", default=True):
            raise
    else:
        _preload_status = "ready"


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "default_model": _default_model(),
        "models": _configured_models(),
        "loaded_model": _loaded_model.model_id if _loaded_model is not None else None,
        "loaded_melotts_models": list(_loaded_melo_models),
        "loaded_piper_models": list(_loaded_piper_models),
        "preload": {
            "enabled": _env_flag("JARVIS_TTS_RUNTIME_PRELOAD_MODEL", default=True),
            "required": _env_flag("JARVIS_TTS_RUNTIME_PRELOAD_REQUIRED", default=True),
            "status": _preload_status,
            "error": _preload_error,
            "models": _preload_models(),
            "loaded": _preloaded_models,
        },
    }


@app.get("/tts/models")
def list_models() -> dict[str, object]:
    default_model = _default_model()
    return {
        "models": [
            {
                "id": model,
                "label": _model_label(model),
                "provider": _provider_for_model(model),
                "is_default": model == default_model,
            }
            for model in _configured_models()
        ]
    }


@app.post("/tts/pcm")
async def synthesize_pcm(request: TTSRequest) -> Response:
    if request.format != "pcm_s16le" or request.sample_width != 2:
        raise HTTPException(status_code=400, detail="only pcm_s16le 16-bit output is supported")

    model_id = request.model.strip() or _default_model()
    try:
        wav, source_rate = await asyncio.to_thread(_generate_audio, model_id, request)
        pcm = _to_pcm_s16le(
            wav,
            source_rate=source_rate,
            target_rate=request.sample_rate,
            channels=request.channels,
        )
    except HTTPException:
        raise
    except Exception as exc:
        provider = _provider_for_model(model_id)
        raise HTTPException(status_code=503, detail=f"{provider} tts inference failed: {exc}") from exc

    return Response(
        content=pcm,
        media_type="audio/pcm",
        headers={
            "X-TTS-Provider": _provider_for_model(model_id),
            "X-TTS-Model": model_id,
            "X-TTS-Voice": _effective_voice(request),
            "X-TTS-Format": request.format,
            "X-TTS-Sample-Rate": str(request.sample_rate),
            "X-TTS-Channels": str(request.channels),
            "X-TTS-Sample-Width": str(request.sample_width),
            "X-AI-Generated-Voice": "true",
        },
    )


def _generate_audio(model_id: str, request: TTSRequest) -> tuple[np.ndarray, int]:
    provider = _provider_for_model(model_id)
    if provider == "melotts":
        return _generate_melotts_audio(model_id, request)
    if provider == "piper":
        return _generate_piper_audio(model_id, request)

    model = _load_model_sync(model_id)
    language = request.language or os.getenv("JARVIS_TTS_RUNTIME_LANGUAGE", DEFAULT_LANGUAGE)

    if "CustomVoice" in model_id:
        wavs, sample_rate = model.generate_custom_voice(
            text=request.text,
            language=language,
            speaker=_effective_voice(request),
            instruct=request.instruct or None,
        )
    elif "VoiceDesign" in model_id:
        wavs, sample_rate = model.generate_voice_design(
            text=request.text,
            language=language,
            instruct=request.instruct or _voice_design_prompt(request.voice),
        )
    elif model_id.endswith("-Base"):
        if not request.ref_audio or not request.ref_text:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Qwen3-TTS Base models require ref_audio and ref_text. "
                    "Use a CustomVoice model for built-in Korean speakers such as Sohee."
                ),
            )
        wavs, sample_rate = model.generate_voice_clone(
            text=request.text,
            language=language,
            ref_audio=request.ref_audio,
            ref_text=request.ref_text,
        )
    else:
        raise HTTPException(status_code=400, detail=f"unsupported Qwen TTS model: {model_id}")

    if not wavs:
        raise HTTPException(status_code=503, detail="qwen tts produced no audio")
    return np.asarray(wavs[0]), int(sample_rate)


def _warm_model_sync(model_id: str) -> None:
    provider = _provider_for_model(model_id)
    if provider == "melotts":
        _load_melotts_sync(model_id)
        return
    if provider == "piper":
        _load_piper_sync(model_id)
        return
    _load_model_sync(model_id)


def _generate_melotts_audio(model_id: str, request: TTSRequest) -> tuple[np.ndarray, int]:
    model = _load_melotts_sync(model_id)
    speaker_id = _melotts_speaker_id(model, request.voice)
    speed = _float_env("JARVIS_TTS_RUNTIME_MELO_SPEED", 1.0)
    with tempfile.TemporaryDirectory(prefix="jarvis-melotts-") as tmp:
        output = Path(tmp) / "speech.wav"
        model.tts_to_file(request.text, speaker_id, str(output), speed=speed)
        return _read_audio_file(output)


def _load_melotts_sync(model_id: str) -> object:
    with _model_lock:
        cached = _loaded_melo_models.get(model_id)
        if cached is not None:
            return cached
        try:
            from melo.api import TTS
        except ImportError as exc:
            raise RuntimeError(
                "MeloTTS dependencies are not installed; install the optional melotts runtime packages"
            ) from exc

        language = _melotts_language(model_id)
        device = os.getenv("JARVIS_TTS_RUNTIME_MELO_DEVICE", "").strip() or _default_melo_device()
        model = TTS(language=language, device=device)
        _loaded_melo_models[model_id] = model
        return model


def _generate_piper_audio(model_id: str, request: TTSRequest) -> tuple[np.ndarray, int]:
    voice = _load_piper_sync(model_id)
    with tempfile.TemporaryDirectory(prefix="jarvis-piper-") as tmp:
        output = Path(tmp) / "speech.wav"
        with wave.open(str(output), "wb") as wav_file:
            voice.synthesize_wav(request.text, wav_file)
        return _read_audio_file(output)


def _load_piper_sync(model_id: str) -> object:
    with _model_lock:
        cached = _loaded_piper_models.get(model_id)
        if cached is not None:
            return cached
        try:
            from piper.voice import PiperVoice
        except ImportError as exc:
            raise RuntimeError(
                "Piper dependencies are not installed; install piper-tts or provide a Piper runtime image"
            ) from exc

        model_path = _piper_model_path(model_id)
        voice = PiperVoice.load(model_path)
        _loaded_piper_models[model_id] = voice
        return voice


def _load_model_sync(model_id: str) -> object:
    global _loaded_model
    with _model_lock:
        if _loaded_model is not None and _loaded_model.model_id == model_id:
            return _loaded_model.model

        try:
            import torch
            from huggingface_hub import snapshot_download
            from qwen_tts import Qwen3TTSModel
        except ImportError as exc:
            raise RuntimeError("qwen-tts runtime dependencies are not installed") from exc

        device_map = _device_map(torch)
        kwargs: dict[str, object] = {"device_map": device_map}
        dtype = _torch_dtype(torch, device_map)
        if dtype is not None:
            kwargs["dtype"] = dtype
        attn = os.getenv("JARVIS_TTS_RUNTIME_ATTN", "").strip()
        if attn:
            kwargs["attn_implementation"] = attn

        model_path = _prepare_model_path(model_id, snapshot_download)
        _loaded_model = LoadedModel(model_id=model_id, model=Qwen3TTSModel.from_pretrained(model_path, **kwargs))
        return _loaded_model.model


def _prepare_model_path(model_id: str, snapshot_download: object) -> str:
    path = Path(model_id)
    if path.exists():
        model_path = path
    else:
        model_path = Path(
            snapshot_download(
                repo_id=model_id,
                revision=os.getenv("JARVIS_TTS_RUNTIME_REVISION", "main"),
                allow_patterns=[
                    "*.json",
                    "*.txt",
                    "*.safetensors",
                    "speech_tokenizer/*",
                ],
            )
        )
    _ensure_speech_tokenizer_preprocessor(model_path)
    return str(model_path)


def _ensure_speech_tokenizer_preprocessor(model_path: Path) -> None:
    tokenizer_dir = model_path / "speech_tokenizer"
    if not tokenizer_dir.exists():
        return
    preprocessor_config = tokenizer_dir / "preprocessor_config.json"
    if preprocessor_config.exists():
        return
    preprocessor_config.write_text(
        json.dumps(
            {
                "chunk_length_s": None,
                "feature_extractor_type": "EncodecFeatureExtractor",
                "feature_size": 1,
                "overlap": None,
                "padding_side": "right",
                "padding_value": 0.0,
                "return_attention_mask": True,
                "sampling_rate": 24000,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _device_map(torch: object) -> str:
    configured = os.getenv("JARVIS_TTS_RUNTIME_DEVICE", "auto").strip()
    if configured and configured != "auto":
        return configured
    cuda = getattr(torch, "cuda", None)
    if cuda is not None and cuda.is_available():
        return "cuda:0"
    return "cpu"


def _torch_dtype(torch: object, device_map: str) -> object | None:
    configured = os.getenv("JARVIS_TTS_RUNTIME_DTYPE", "auto").strip()
    if configured and configured != "auto":
        return getattr(torch, configured)
    if device_map.startswith("cuda"):
        return getattr(torch, "bfloat16")
    return getattr(torch, "float32")


def _effective_voice(request: TTSRequest) -> str:
    selected = (request.voice or "").strip()
    if selected.lower() in {"", "default", "marin", "korean", "ko", "sohee"}:
        return os.getenv("JARVIS_TTS_RUNTIME_DEFAULT_SPEAKER", DEFAULT_KOREAN_SPEAKER)
    return selected


def _voice_design_prompt(voice: str) -> str:
    selected = (voice or "").strip()
    if selected and selected.lower() not in {"default", "marin"}:
        return selected
    return os.getenv(
        "JARVIS_TTS_RUNTIME_VOICE_DESIGN_PROMPT",
        "Warm, natural Korean female voice with clear pronunciation and calm emotion.",
    )


def _provider_for_model(model_id: str) -> str:
    normalized = model_id.strip().lower()
    if normalized.startswith(("melotts", "melo/")) or "melotts" in normalized:
        return "melotts"
    if normalized.startswith("piper"):
        return "piper"
    return "qwen"


def _melotts_language(model_id: str) -> str:
    configured = os.getenv("JARVIS_TTS_RUNTIME_MELO_LANGUAGE", "").strip()
    if configured:
        return configured
    if "/" in model_id:
        candidate = model_id.rsplit("/", 1)[-1].strip()
        if candidate:
            return candidate.upper()
    return "KR"


def _melotts_speaker_id(model: object, voice: str) -> int:
    hps = getattr(model, "hps", None)
    data = getattr(hps, "data", None)
    speaker_ids = getattr(data, "spk2id", None)
    if not isinstance(speaker_ids, dict) or not speaker_ids:
        return 0
    selected = (voice or "").strip()
    configured = os.getenv("JARVIS_TTS_RUNTIME_MELO_SPEAKER", "").strip()
    for candidate in (selected, configured, "KR", "Korean"):
        if candidate and candidate.lower() not in {"default", "marin", "ko", "korean"}:
            if candidate in speaker_ids:
                return int(speaker_ids[candidate])
    return int(next(iter(speaker_ids.values())))


def _default_melo_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    backends = getattr(torch, "backends", None)
    mps = getattr(backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    cuda = getattr(torch, "cuda", None)
    if cuda is not None and cuda.is_available():
        return "cuda:0"
    return "cpu"


def _piper_model_path(model_id: str) -> str:
    configured = os.getenv("JARVIS_TTS_RUNTIME_PIPER_MODEL_PATH", "").strip()
    if configured and model_id in {DEFAULT_PIPER_MODEL, "piper", "piper/default"}:
        return configured
    if model_id.startswith("piper/"):
        candidate = model_id.removeprefix("piper/")
        if candidate and candidate != "default":
            return candidate
    if Path(model_id).exists():
        return model_id
    if model_id in {DEFAULT_PIPER_MODEL, "piper", "piper/default"}:
        return _ensure_default_piper_model()
    raise RuntimeError(f"Piper model path does not exist: {model_id}")


def _ensure_default_piper_model() -> str:
    model_dir = Path(os.getenv("JARVIS_TTS_RUNTIME_PIPER_MODEL_DIR", "/models/piper"))
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "en_US-lessac-medium.onnx"
    config_path = model_dir / "en_US-lessac-medium.onnx.json"
    if not model_path.exists():
        _download_file(
            os.getenv("JARVIS_TTS_RUNTIME_PIPER_MODEL_URL", DEFAULT_PIPER_MODEL_URL),
            model_path,
        )
    if not config_path.exists():
        _download_file(
            os.getenv("JARVIS_TTS_RUNTIME_PIPER_CONFIG_URL", DEFAULT_PIPER_CONFIG_URL),
            config_path,
        )
    return str(model_path)


def _download_file(url: str, destination: Path) -> None:
    temp_path = destination.with_suffix(destination.suffix + ".tmp")
    try:
        urllib.request.urlretrieve(url, temp_path)
        temp_path.replace(destination)
    finally:
        temp_path.unlink(missing_ok=True)


def _read_audio_file(path: Path) -> tuple[np.ndarray, int]:
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"TTS provider produced no audio at {path}")
    audio, sample_rate = sf.read(str(path), dtype="float32", always_2d=False)
    return np.asarray(audio), int(sample_rate)


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _to_pcm_s16le(
    audio: np.ndarray,
    *,
    source_rate: int,
    target_rate: int,
    channels: int,
) -> bytes:
    mono = _as_mono_float(audio)
    if source_rate != target_rate:
        mono = _resample_linear(mono, source_rate=source_rate, target_rate=target_rate)
    mono = np.clip(mono, -1.0, 1.0)
    pcm = (mono * 32767.0).astype("<i2")
    if channels == 2:
        stereo = np.column_stack([pcm, pcm]).reshape(-1)
        return stereo.astype("<i2").tobytes()
    return pcm.tobytes()


def _as_mono_float(audio: np.ndarray) -> np.ndarray:
    data = np.asarray(audio)
    if data.ndim == 2:
        data = data.mean(axis=1)
    data = data.astype(np.float32, copy=False)
    if np.issubdtype(audio.dtype, np.integer):
        max_value = float(np.iinfo(audio.dtype).max)
        if max_value > 0:
            data = data / max_value
    return data


def _resample_linear(audio: np.ndarray, *, source_rate: int, target_rate: int) -> np.ndarray:
    if len(audio) == 0:
        return audio
    duration = len(audio) / float(source_rate)
    target_len = max(1, int(round(duration * target_rate)))
    source_x = np.linspace(0.0, duration, num=len(audio), endpoint=False)
    target_x = np.linspace(0.0, duration, num=target_len, endpoint=False)
    return np.interp(target_x, source_x, audio).astype(np.float32)


def _configured_models() -> list[str]:
    raw = os.getenv("JARVIS_TTS_RUNTIME_MODELS", "")
    models = [part.strip() for part in raw.split(",") if part.strip()]
    if not models:
        models = list(DEFAULT_MODELS)
    default = _default_model()
    return _dedupe([default, *models])


def _preload_models() -> list[str]:
    raw = os.getenv("JARVIS_TTS_RUNTIME_PRELOAD_MODELS", "").strip()
    if raw:
        return _dedupe([part.strip() for part in raw.split(",") if part.strip()])
    return [_default_model()]


def _default_model() -> str:
    return os.getenv("JARVIS_TTS_RUNTIME_DEFAULT_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _model_label(model: str) -> str:
    provider = _provider_for_model(model)
    if provider == "melotts":
        return f"MeloTTS ({_melotts_language(model)})"
    if provider == "piper":
        return "Piper" if model == DEFAULT_PIPER_MODEL else f"Piper ({model})"
    if model.endswith("CustomVoice"):
        return f"{model} ({DEFAULT_KOREAN_SPEAKER})"
    return model


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}

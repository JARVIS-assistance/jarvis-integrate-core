# Jarvis TTS Runtime

FastAPI adapter for local TTS inference. It supports Qwen3-TTS, MeloTTS, and Piper
behind the same PCM endpoint.

The service exposes the contract expected by `jarvis_core`:

- `GET /health`
- `GET /tts/models`
- `POST /tts/pcm`

`POST /tts/pcm` returns raw `pcm_s16le` bytes, mono/stereo, at the requested sample rate.

## Default Korean Setup

The compose defaults use:

- model: `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`
- language: `Korean`
- speaker: `Sohee`

The initial test set is:

- `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`
- `melotts/KR`
- `piper/default`
- `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`
- `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`

`Base` models are not in the default list because they need `ref_audio` and `ref_text`
for voice cloning. Add them later only after the frontend/backend contract carries those
reference fields.

## Provider Selection

Select the provider with the `model` field:

- Qwen: `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`
- MeloTTS Korean: `melotts/KR`
- Piper: `piper/default` or `piper/<path-to-model.onnx>`

MeloTTS keeps its model object in memory after the first request. On Apple Silicon
outside Docker, `JARVIS_TTS_RUNTIME_MELO_DEVICE=mps` can use Metal. The compose default
uses `cpu` because Docker on macOS does not expose MPS into the Linux container.

Piper needs a voice model file. Set:

```bash
JARVIS_TTS_RUNTIME_PIPER_MODEL_PATH=/models/piper/voice.onnx
```

The matching `.onnx.json` config should be next to the `.onnx` file.

## Run

From the repository root:

```bash
docker compose up -d --build jarvis-tts-runtime jarvis-core jarvis-controller
```

Then check:

```bash
curl http://localhost:3031/health
curl http://localhost:3010/internal/audio/speech/models -H 'X-User-ID: smoke'
```

The first real synthesis request downloads and loads the model, so it can take much
longer than later requests. In compose, `JARVIS_TTS_RUNTIME_PRELOAD_MODEL=1` is enabled
by default, so the default model is loaded during container startup and kept in memory.
`/health` includes `loaded_model` and `preload.status` so you can confirm it is ready.

Set `JARVIS_TTS_RUNTIME_PRELOAD_REQUIRED=0` if you want the runtime container to start
even when the preload fails.

## Hardware Notes

For realtime-feeling Korean TTS, use a GPU runtime if possible:

```bash
JARVIS_TTS_RUNTIME_DEVICE=cuda:0
JARVIS_TTS_RUNTIME_DTYPE=bfloat16
JARVIS_TTS_RUNTIME_ATTN=flash_attention_2
```

CPU mode works as a functional fallback for testing, but it is unlikely to feel realtime.
For a Mac mini M4 on-prem setup, benchmark `melotts/KR` first. It is the most practical
local Korean realtime candidate in this runtime. Piper can be faster, but only after you
provide a usable Korean voice model.

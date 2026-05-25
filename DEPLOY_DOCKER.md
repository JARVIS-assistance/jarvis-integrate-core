# Docker Deployment

이 저장소는 `docker compose` 기준으로 다음 4개 서비스를 함께 올릴 수 있습니다.

- `jarvis-core` on `3010`
- `jarvis-controller` on `3011`
- `jarvis-gateway` on `3012`
- `jarvis-ai-workbench` on `3013`

## 1. 환경변수 준비

```bash
cp .env.docker.example .env.docker
```

기본값은 `jarvis-core`, `jarvis-gateway` 모두 컨테이너 내부 SQLite 볼륨을 사용합니다.

`jarvis-core`를 외부 PostgreSQL에 붙이려면 `.env.docker`에 아래 값 중 하나를 채우면 됩니다.

- `JARVIS_CORE_DB_URL`
- 또는 `JARVIS_CORE_DB_HOST`, `JARVIS_CORE_DB_USER`, `JARVIS_CORE_DB_PASSWORD`, `JARVIS_CORE_DB_NAME`

운영 배포에서는 반드시 `JARVIS_AUTH_SECRET`을 실제 비밀값으로 바꾸십시오.

### Ollama 모델 상시 로드

`docker-compose.yml`은 Ollama 요청에 `keep_alive=-1`을 사용하고, controller 시작 시
`gemma4:e2b`를 preload합니다. TTS는 Ollama 모델이 아니라 서버 TTS 런타임에서
PCM 스트림으로 제공합니다.

명시적으로 preload할 모델 목록을 고정하려면 쉼표로 구분합니다.

```bash
JARVIS_OLLAMA_PRELOAD_MODELS=gemma4:e2b,another-model:tag docker compose up -d --build
```

### 서버 TTS PCM 런타임

TTS는 core가 서버 TTS 런타임에 요청하고, controller가 raw PCM 스트림을 프론트에
전달합니다. `docker-compose.yml`은 기본으로 `jarvis-tts-runtime` 서비스를 함께 띄우고,
core가 `http://jarvis-tts-runtime:8031/tts/pcm`으로 요청하도록 구성합니다.

```bash
docker compose up -d --build jarvis-tts-runtime jarvis-core jarvis-controller
```

호스트에서 런타임만 직접 확인하려면 아래를 호출합니다.

```bash
curl http://localhost:3031/health
```

기본 한국어 테스트 구성은 `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` + `Sohee` speaker입니다.
모델 비교 후보는 아래 환경 변수로 바꿀 수 있습니다.

```bash
JARVIS_TTS_RUNTIME_MODELS=Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice,Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice,Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
```

외부 전용 런타임 URL을 직접 쓰려면 아래 둘 중 하나로 지정합니다.

```bash
JARVIS_TTS_SERVER_URL=http://host.docker.internal:3031 docker compose up -d --build
# 또는
JARVIS_TTS_SERVER_PCM_ENDPOINT=http://host.docker.internal:3031/tts/pcm docker compose up -d --build
```

전용 런타임 URL이 비어 있으면 core는 로컬 TTS 엔진을 사용합니다. 기본 감지 대상은
`espeak-ng`/`espeak` 또는 macOS `say`이며, 별도 런타임은 `JARVIS_LOCAL_TTS_COMMAND`로
지정할 수 있습니다. 로컬 엔진은 WAV 또는 `pcm_s16le` 스트림을 반환하며 OpenAI TTS는
호출하지 않습니다. 로컬 voice는 기본적으로 시스템 기본값을 쓰고, 필요하면
`JARVIS_LOCAL_TTS_VOICE`로 고정합니다.

모델 선택 UI는 반드시 `GET /audio/speech/models` 응답을 사용해야 합니다. Qwen TTS
런타임(`JARVIS_TTS_SERVER_URL`/`JARVIS_TTS_SERVER_PCM_ENDPOINT`)이나 `{model}` placeholder를
포함한 `JARVIS_LOCAL_TTS_COMMAND`가 있을 때만 Qwen 모델 목록을 반환합니다. 이 경우
프론트가 `model: "gpt-4o-mini-tts"`를 보내면 레거시 기본 alias로 보고 기본 TTS 모델
`Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`로 해석하며, 사용자가 선택한 다른 Qwen TTS 모델명은
그대로 런타임에 전달합니다. 모델 목록은 `JARVIS_TTS_MODELS`로 재정의할 수 있습니다.
CPU 환경의 첫 요청과 긴 문장은 느릴 수 있으므로 core의 서버 TTS 호출 제한은
`JARVIS_TTS_TIMEOUT_SECONDS`로 조정합니다. compose 기본값은 `300`초입니다.
bundled `jarvis-tts-runtime`은 기본값 `JARVIS_TTS_RUNTIME_PRELOAD_MODEL=1`로 시작 시
기본 모델 하나를 먼저 로드하고 메모리에 유지합니다. preload 실패 시 컨테이너를 실패로
처리하지 않으려면 `JARVIS_TTS_RUNTIME_PRELOAD_REQUIRED=0`으로 낮춥니다.

Qwen 런타임이 없고 내장 로컬 fallback만 가능한 경우 모델 목록에는 `local/espeak-ng`
같은 실제 로컬 엔진만 반환합니다. 이 상태에서 Qwen 모델을 직접 요청하면 core는
Qwen 선택을 조용히 `espeak-ng`로 대체하지 않고 `503`을 반환합니다.

Docker core 이미지에는 503 방지를 위한 로컬 fallback으로 `espeak-ng`가 포함됩니다.
실제 Qwen3-TTS 런타임으로 합성하려면 `JARVIS_TTS_SERVER_URL`/`JARVIS_TTS_SERVER_PCM_ENDPOINT`
또는 `{model}`, `{text}`, `{voice}`, `{sample_rate}`, `{output}` placeholder를 받는
`JARVIS_LOCAL_TTS_COMMAND`를 지정하십시오.

Qwen3-TTS `Base` 모델은 voice clone 용도라 `ref_audio`/`ref_text`가 필요합니다. 현재
프론트 PCM 계약은 이 reference 필드를 보내지 않으므로 기본 테스트 목록에서는
`CustomVoice`와 `VoiceDesign` 모델을 우선 사용합니다.

## 2. 빌드 및 실행

```bash
docker compose up -d --build
```

GitHub 저장소를 먼저 받아온 뒤 바로 올리려면:

```bash
./deploy_remote_services.sh
```

기본 원격 주소는 `https://github.com/JARVIS-assistance/<service>.git` 형식입니다.
다른 조직이나 미러를 쓰려면:

```bash
GITHUB_BASE=https://github.com/your-org ./deploy_remote_services.sh
```

로그 확인:

```bash
docker compose logs -f
```

중지:

```bash
docker compose down
```

볼륨까지 제거:

```bash
docker compose down -v
```

## 3. 헬스체크

```bash
curl http://localhost:3010/health
curl http://localhost:3011/health
curl http://localhost:3012/health
curl http://localhost:3013/health
```

## 4. 데이터 저장 위치

- `jarvis-core`: Docker named volume `jarvis_core_data`
- `jarvis-gateway`: Docker named volume `jarvis_gateway_data`
- `jarvis-ai-workbench`: 호스트 디렉토리 `./jarvis-ai-workbench/config`

## 5. 참고

- 이미지에는 로컬 `jarvis_core/.env`를 포함하지 않도록 `.dockerignore`에 제외 처리했습니다.
- `jarvis-controller`, `jarvis-gateway`, `jarvis-core`는 공용 로컬 패키지 `jarvis_contracts`를 함께 복사해 빌드합니다.

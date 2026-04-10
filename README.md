# jarvis-integrate-core

JARVIS 서비스를 하나의 상위 저장소에서 배포하기 위한 통합 레포입니다.  
각 서비스는 독립 저장소이며, 이 레포에서는 Git submodule로 관리합니다.

## 구성 서비스

- `jarvis_contracts`: 공통 계약/스키마
- `jarvis_core`: Core FastAPI
- `jarvis_controller`: Controller FastAPI
- `jarvis_gateway`: Gateway FastAPI
- `jarvis_ai_workbench`: AI Workbench FastAPI

## 배포 PC 빠른 시작

### 1) 클론 + 서브모듈 초기화

```bash
git clone --recurse-submodules https://github.com/JARVIS-assistance/jarvis-integrate-core.git
cd jarvis-integrate-core
git submodule sync --recursive
git submodule update --init --recursive
```

이미 클론한 저장소라면:

```bash
git submodule sync --recursive
git submodule update --init --recursive
```

### 2) 환경 변수 파일 준비

```bash
cp .env.docker.example .env.docker
```

운영에서는 `.env.docker`의 `JARVIS_AUTH_SECRET`을 반드시 변경하세요.

### 3) 경로 호환성 체크 (필수)

현재 Dockerfile/compose는 `jarvis-ai-workbench` 경로를 참조합니다.  
서브모듈 기본 경로는 `jarvis_ai_workbench`이므로, 아래 링크를 1회 생성하세요.

```bash
[ -e jarvis-ai-workbench ] || ln -s jarvis_ai_workbench jarvis-ai-workbench
```

### 4) 빌드 및 실행

```bash
docker compose up -d --build
```

### 5) 상태 확인

```bash
docker compose ps
docker compose logs -f
```

헬스체크:

```bash
curl http://localhost:3010/health
curl http://localhost:3011/health
curl http://localhost:3012/health
curl http://localhost:3013/health
```

## 포트

- `jarvis-core`: `3010`
- `jarvis-controller`: `3011`
- `jarvis-gateway`: `3012`
- `jarvis-ai-workbench`: `3013`

포트 변경은 `.env.docker`에서 `JARVIS_*_PORT` 값을 수정하세요.

## 업데이트 절차

모든 서브모듈을 `main` 최신으로 맞추려면:

```bash
git submodule foreach --recursive 'git switch main && git pull --ff-only origin main'
```

특정 커밋으로 다시 고정하려면 상위 레포에서 원하는 submodule 포인터를 커밋하세요.

## 중지/정리

```bash
docker compose down
```

볼륨까지 제거:

```bash
docker compose down -v
```

## 참고 문서

- [DEPLOY_DOCKER.md](/Users/chawonje/Desktop/Workspace/project/JARVIS/core/DEPLOY_DOCKER.md)
- [SYSTEM_STRUCTURE.md](/Users/chawonje/Desktop/Workspace/project/JARVIS/core/SYSTEM_STRUCTURE.md)

# jarvis-integrate-core

JARVIS 서비스들을 하나의 상위 저장소에서 관리하기 위한 통합 레포입니다.  
각 서비스는 독립 저장소를 유지하고, 이 레포에서는 Git submodule로 연결해 함께 배포합니다.

## 구성

- `jarvis_contracts`: 공통 계약 모델
- `jarvis_core`: 사고/플래닝 FastAPI 서비스
- `jarvis_controller`: 실행/검증 FastAPI 서비스
- `jarvis_gateway`: 인증/세션/감사 FastAPI 게이트웨이
- `jarvis-ai-workbench`: AI 설정 관리 UI

## 저장소 구조

이 레포의 하위 서비스들은 모두 submodule 입니다.

```bash
git clone --recurse-submodules https://github.com/JARVIS-assistance/jarvis-integrate-core.git
cd jarvis-integrate-core
```

이미 clone 했다면:

```bash
git submodule update --init --recursive
```

submodule 최신 반영:

```bash
git submodule update --remote --recursive
```

## Docker 실행

배포용 기본 환경파일 생성:

```bash
cp .env.docker.example .env.docker
```

컨테이너 빌드 및 실행:

```bash
docker compose up -d --build
```

실행되는 서비스:

- `jarvis-core`: `3010`
- `jarvis-controller`: `3011`
- `jarvis-gateway`: `3012`
- `jarvis-ai-workbench`: `3013`

로그 확인:

```bash
docker compose logs -f
```

중지:

```bash
docker compose down
```

## 원격 저장소 기준 자동 배포

각 서비스 저장소를 GitHub에서 받아오거나 갱신한 뒤 바로 도커를 띄우려면:

```bash
./deploy_remote_services.sh
```

기본 원격 주소 규칙:

```text
https://github.com/JARVIS-assistance/<service>.git
```

다른 org 또는 미러 사용:

```bash
GITHUB_BASE=https://github.com/your-org ./deploy_remote_services.sh
```

## 환경변수

주요 배포 변수는 `.env.docker`에서 관리합니다.

- `JARVIS_AUTH_SECRET`: 운영에서는 반드시 변경
- `JARVIS_CORE_DB_URL`: `jarvis-core` 외부 PostgreSQL 연결 시 사용
- `JARVIS_GATEWAY_RATE_LIMIT`: gateway rate limit
- `JARVIS_GATEWAY_RATE_WINDOW`: gateway rate limit window

기본값은 `jarvis-core`, `jarvis-gateway` 모두 Docker volume 기반 SQLite를 사용합니다.

## 헬스체크

```bash
curl http://localhost:3010/health
curl http://localhost:3011/health
curl http://localhost:3012/health
curl http://localhost:3013/health
```

## 참고

- 루트 저장소 원격: [jarvis-integrate-core](https://github.com/JARVIS-assistance/jarvis-integrate-core.git)
- 구조 정리 문서: [SYSTEM_STRUCTURE.md](/Users/chawonje/Desktop/Workspace/project/JARVIS/core/SYSTEM_STRUCTURE.md)
- 상세 배포 문서: [DEPLOY_DOCKER.md](/Users/chawonje/Desktop/Workspace/project/JARVIS/core/DEPLOY_DOCKER.md)
- 로컬 비밀값이 들어갈 수 있는 `jarvis_core/.env`는 Docker build context에서 제외됩니다.

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

- 이미지에는 로컬 `jarvis-core/.env`를 포함하지 않도록 `.dockerignore`에 제외 처리했습니다.
- `jarvis-controller`, `jarvis-gateway`, `jarvis-core`는 공용 로컬 패키지 `jarvis-contracts`를 함께 복사해 빌드합니다.

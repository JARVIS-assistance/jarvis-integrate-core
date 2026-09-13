> **보관됨 (ARCHIVED)** — 이 문서는 특정 시점(auth/signup 정리, 토큰 서명 전환,
> PostgreSQL 데드락 수정, model-config API 추가 작업 당시)의 작업 기록입니다.
> 여기 적힌 내용은 모두 반영되어 현재 코드베이스에 존재합니다. "Current State"라는
> 제목과 달리 지금은 히스토리 자료입니다 — 현재 상태는 저장소 루트의
> `DEV_READINESS_REVIEW.md`를 보세요. `jarvis_core/docs/architecture.md` /
> `jarvis_core/docs/runbook.md`도 이 문서보다 최신입니다.

# JARVIS Current State (작업 기록, 완료됨)

## Architecture

- `jarvis_controller` exposes external endpoints.
- `jarvis_core` owns the real chat/model-config service logic.
- `jarvis_gateway` owns auth and gateway-side business logic.
- Controller talks to core via `CoreClient`.
- Controller talks to gateway via `GatewayClient`.

## Auth / Signup Changes

- Signup response was failing because controller expected `role`, but gateway signup payload did not include it.
- Fixed controller signup response model to stop requiring `role`.
- Controller signup test was updated to assert that `role` and `tenant_id` are not present.
- Login and `/auth/me` contracts were also aligned to stop exposing `tenant_id` and `role` on the controller side.

## Token Behavior

- Gateway originally used an in-memory `TokenStore`.
- That caused `invalid or expired token` after reload/restart because tokens were lost.
- Gateway token handling was changed to signed tokens using `JARVIS_AUTH_SECRET`.
- Old tokens issued before that change should be considered invalid.

## DB / Env Findings

- Gateway DB access is intentionally delegated through `jarvis_core` DB modules.
- `jarvis_gateway/src/jarvis_gateway/db.py` imports core DB connection and user functions.
- `jarvis_core/src/core/db/db_connection.py` is the single place deciding SQLite vs PostgreSQL.
- `jarvis_core/.env` is explicitly loaded from repo-root execution now.
- Startup logs were improved to print the actual DB target:
  - PostgreSQL: `user@host:port/db`
  - SQLite: file path

## PostgreSQL Deadlock Fix

- Startup deadlock happened in PostgreSQL when schema init/migration ran concurrently.
- `jarvis_core/src/core/db/db_schema.py` now uses `pg_advisory_xact_lock(...)` in postgres `init_db()`.
- This serializes schema initialization across core and gateway startup.

## Model Config Storage

- Model configs are stored in `ai_model_configs`.
- Model selection is stored in `user_ai_model_selection`.
- Both tables live in the DB used by `jarvis_core`.
- If `users` and `ai_model_configs` are both empty in a DB session, that DB is not the one the app is actively using.

## Docker Model Runner Findings

- Docker Model Runner endpoint worked at:
  - `https://qwen.breakpack.cc/engines/v1/chat/completions`
- `/engines/v1/models` returned:
  - `docker.io/ai/gemma3-qat:4B`
  - `docker.io/ai/qwen3.5:4B-UD-Q4_K_XL`
- The working model name for Gemma was:
  - `docker.io/gemma3-Qat:4B` in manual curl
- Recommended stable config value to try in app:
  - `docker.io/ai/gemma3-qat:4B`
- The previous `4B-Q4_K_M` value was not found by the model runner.

## Model Config API Status

- Existing structure before work:
  - Controller exposed create/list/select endpoints.
  - Core exposed internal create/list/select endpoints.
  - No update endpoint existed.

- Added update flow preserving the same architecture:
  - Controller: `PUT /chat/model-config/{model_config_id}`
  - Core: `PUT /internal/chat/model-config/{model_config_id}`
  - DB op: update existing model config for the owning user only

## Files Changed For Model Config Update

- `jarvis_contracts/endpoints.py`
- `jarvis_core/src/core/db/db_operations/model_config.py`
- `jarvis_core/src/core/db/db_operations/__init__.py`
- `jarvis_core/src/core/db/db.py`
- `jarvis_core/src/application/chat/service.py`
- `jarvis_core/src/app.py`
- `jarvis_controller/src/middleware/core_client.py`
- `jarvis_controller/src/router/router.py`
- `jarvis_controller/tests/test_app.py`

## Model Config Update Semantics

- Update is owner-scoped by `user_id`.
- If `model_config_id` is missing for that user, core returns 404.
- If updated config is marked `is_default=true`, other configs for that user are unset from default.
- `is_active` is preserved from the existing row and not explicitly toggled by the new update API.

## Verification Performed

- `py_compile` succeeded for the updated Python files.
- Full pytest suite could not be run because the venv is missing `pytest`.
- Some FastAPI `TestClient` paths were also blocked earlier because `httpx` was missing in the venv.

## Important Runtime Facts

- If `/auth/me` returns auth failure right after restart, use a freshly issued token.
- If model config queries show zero rows, first confirm the app startup log DB target and compare it with the DB session you are querying.
- To verify app DB target, rely on the startup log line added in `db_connection.py`.

## Useful SQL

```sql
select current_user, current_database(), current_schema(), inet_server_addr(), inet_server_port();
```

```sql
select id, email, created_at from users order by created_at desc;
```

```sql
select
  mc.id,
  u.email,
  mc.provider_name,
  mc.model_name,
  mc.endpoint,
  mc.is_default,
  mc.supports_stream,
  mc.supports_realtime,
  mc.updated_at
from ai_model_configs mc
join users u on u.id = mc.user_id
order by mc.updated_at desc nulls last;
```

## Immediate Next Steps

- Restart services and confirm the startup DB log line.
- Create a model config through controller `POST /chat/model-config`.
- Verify the inserted row in the same PostgreSQL target shown in startup logs.
- Then use `PUT /chat/model-config/{id}` to confirm update behavior.

## Model Selection Bug Fix (Task 3)

- Runtime evidence from `jarvis-core` Docker logs showed core chat requests selecting `gemma4:e2b` for realtime after ignoring selected `gemma4:e4b` because `supports_realtime=false`.
- Runtime evidence from `jarvis-controller` Docker logs showed separate action compiler requests using `docker.io/ai/gemma4:E4B`; these are not the core chat response model-selection path.
- PostgreSQL state (`breakpack@host.docker.internal:3015/jarvis`) showed `user_ai_model_selection.realtime_model_config_id` pointed at the default `gemma4:e4b` row even though that row had `supports_stream=false` and `supports_realtime=false`; the realtime-capable `gemma4:e2b` row existed separately.
- Root cause fixed in `jarvis_core/src/application/chat/service.py`: creating/updating an `is_default=true` config no longer blindly overwrites existing realtime/deep selections. Realtime selection is only auto-populated from a default config when it supports realtime and no realtime lane is already selected; deep selection is only auto-populated when no deep lane is selected.
- `POST /internal/chat/model-selection` now preserves omitted lanes as partial updates and rejects a `realtime_model_config_id` that does not reference a realtime-capable model.
- Regression coverage was added in `jarvis_core/tests/test_app.py` for default create/update preserving selected realtime config, partial lane update preservation, and invalid realtime-lane selection rejection.

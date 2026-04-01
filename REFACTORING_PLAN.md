# JARVIS 리팩토링 계획

## 현재 문제 진단

### 1. contracts: 모델 중복
- `conversation_models.py`와 `router_models.py`에 동일한 모델이 중복 (차이: `contract_version` 유무만)
- `models.py`의 `ExecuteRequest`, `ErrorResponse` 등이 `__init__.py`에서 export 안 됨
- gateway도 자체 `models.py`에 중복 모델 보유

### 2. core: 역할 초과
- `src/application/auth/` — 410 반환하는 죽은 auth 라우터 + gateway_client + schemas + dependencies
- `src/application/chat/router.py` — `/chat/*` 엔드포인트를 core가 직접 노출 (controller 역할)
- core의 `app.py`는 internal API만 제공하는데, chat/auth 라우터는 별도로 존재 → 이중 구조

### 3. controller: 불완전한 오케스트레이션
- `core_bridge.py` — `sys.path` 조작으로 core를 직접 import (안티패턴)
- chat 관련 엔드포인트(`/chat/*`, 스트리밍, WebSocket)가 controller에 없음
- 사용자가 chat을 사용하려면 core에 직접 접근해야 하는 구조

### 4. gateway: 경미한 중복
- `models.py`에 contracts와 중복되는 모델 존재

---

## 리팩토링 Phase 구성

### Phase 1: contracts 정리
**목표**: 단일 소스(single source of truth) 확립

| 작업 | 상세 |
|------|------|
| `router_models.py` 제거 | `conversation_models.py`로 통합. `contract_version`은 응답에만 포함, 요청에서 제거하는 방식으로 통일 |
| `models.py` export 추가 | `__init__.py`에 `ErrorResponse`, `ExecuteRequest`, `ExecuteResult`, `VerifyRequest`, `VerifyResult`, `PlanStep`, `PlanRequest` 추가 |
| gateway용 endpoint 추가 | `endpoints.py`에 `JarvisGatewayEndpoints` 클래스 추가 (login, logout, validate 등) |

**변경 파일**:
- `jarvis_contracts/conversation_models.py` — 요청 모델에서 `contract_version` 제거, 응답에만 유지
- `jarvis_contracts/router_models.py` — 삭제
- `jarvis_contracts/__init__.py` — 전체 export 정리
- `jarvis_contracts/endpoints.py` — gateway endpoints 추가

### Phase 2: core 정리
**목표**: core는 DB + AI 프로바이더 관리만 담당

| 작업 | 상세 |
|------|------|
| auth 디렉토리 제거 | `src/application/auth/` 전체 삭제 (410 스텁 + gateway_client + schemas + dependencies + security) |
| chat router 제거 | `src/application/chat/router.py` 삭제 — 엔드포인트는 controller로 이동 |
| ChatService를 internal API로 노출 | `app.py`에 내부용 엔드포인트 추가: `/internal/chat/request`, `/internal/chat/stream`, `/internal/chat/model-config` 등 |
| chat schemas 정리 | core 내부용으로만 남기거나 contracts로 이동 |

**core의 최종 구조**:
```
src/
├── app.py                    # /health + /internal/* 엔드포인트만
├── jarvis_core.py            # public exports
├── router.py                 # route 결정 로직 (내부용)
├── safety.py                 # safety gate
├── ai/                       # AI 프로바이더 (유지)
├── core/
│   ├── config/engine.py      # realtime/deep 모드 (유지)
│   └── db/                   # DB 전체 (유지)
└── application/
    └── chat/
        ├── service.py        # ChatService (유지 — 핵심 비즈니스 로직)
        └── schemas.py        # 내부 스키마 (유지 또는 contracts 이동)
```

### Phase 3: controller 강화
**목표**: 모든 사용자 대면 엔드포인트를 controller로 집중

| 작업 | 상세 |
|------|------|
| `core_bridge.py` 삭제 | sys.path 해킹 제거 |
| core HTTP client 확장 | `core_client.py`에 chat 관련 메서드 추가 (request_once, stream, model-config 등) |
| chat 엔드포인트 추가 | controller router에 `/chat/*` 엔드포인트 추가 → core internal API 호출 |
| 스트리밍 프록시 | SSE/WebSocket 엔드포인트를 controller에 추가, core의 스트리밍을 프록시 |

**controller의 최종 구조**:
```
src/
├── app.py
├── router/
│   └── router.py             # /health, /auth/*, /conversation/*, /chat/*, /execute, /verify
├── middleware/
│   ├── auth_middleware.py     # (유지)
│   ├── gateway_client.py     # (유지)
│   └── core_client.py        # 확장: chat/stream/model-config 메서드 추가
└── planner/                  # (유지)
```

### Phase 4: gateway 정리
**목표**: contracts 모델 사용으로 통일

| 작업 | 상세 |
|------|------|
| 중복 모델 제거 | gateway `models.py`에서 contracts와 겹치는 모델 제거, contracts에서 import |
| endpoint 상수 사용 | contracts의 `JarvisGatewayEndpoints`를 gateway/controller에서 활용 |

---

## 최종 데이터 플로우 (리팩토링 후)

```
사용자 요청
    │
    ▼
[controller] /chat/common_request, /chat/realtime/stream, /conversation/respond
    │
    ├─ 인증 ──→ [gateway] /auth/validate (middleware에서 자동)
    │
    ├─ 라우팅 결정 (realtime/deep/planning)
    │
    ├─ planning ──→ controller 자체 처리
    │
    └─ realtime/deep ──→ [core] /internal/chat/request (HTTP)
                              │
                              ├─ DB 조회/저장
                              ├─ AI 프로바이더 호출
                              └─ 응답 반환
```

---

## 작업 순서 & 의존성

```
Phase 1 (contracts) ─┐
                     ├──→ Phase 2 (core) ──→ Phase 3 (controller) ──→ Phase 4 (gateway)
                     │
                     └──→ Phase 4 (gateway)는 Phase 1 직후 병렬 가능
```

Phase 1 → 2 → 3은 순차 필수 (의존성). Phase 4는 Phase 1 이후 언제든 가능.

---

## 리스크 & 주의사항

- **core의 ChatService 이동이 아님**: ChatService는 core에 남음 (DB+AI 로직). controller는 HTTP로 호출만 함
- **스트리밍 프록시 복잡도**: SSE는 비교적 단순하지만, WebSocket 프록시는 controller↔core 간 양방향 연결 필요
- **테스트 업데이트**: 각 Phase마다 기존 테스트 수정 필요
- **하위 호환성**: 기존 core 직접 호출 클라이언트가 있다면 전환 기간 필요

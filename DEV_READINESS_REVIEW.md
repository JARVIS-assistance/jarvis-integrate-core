# 개발 준비 상태 점검 (2026-08-24)

브랜치 `feature/action-runtime-routing` 기준 점검. 대상: `jarvis_gateway`(인증) →
`jarvis_controller`(오케스트레이션/액션 라우팅) → `jarvis_core`(추론/DB) 구조의
SaaS형 개인 어시스턴트. 목표: 노트북에서는 가벼운 에이전트로, 맥미니 같은 홈
서버의 소형 로컬 모델로 비서 기능을 지원.

## 1. Git 상태

| 저장소 | 브랜치 | 상태 |
|---|---|---|
| jarvis-integrate-core (상위) | feature/action-runtime-routing | 업스트림 트래킹 미설정, controller/core 서브모듈 포인터 미커밋 |
| jarvis_controller | 동일 | 미푸시 커밋 1개 + 미커밋 변경 (`action_pipeline.py`, `router.py`, `tests/test_app.py`) |
| jarvis_core | 동일 | 미푸시 커밋 1개 + 미커밋 변경 (`service.py`, `tests/test_app.py`) |
| jarvis_ai_workbench | 동일 | 클린, origin과 동기화됨 (untracked `uv.lock`만 존재) |
| jarvis_contracts | 동일 | 미푸시 커밋 1개, 나머지 클린 |
| jarvis_gateway | detached HEAD | `main` 최신 커밋과 동일 (서브모듈 핀 고정 시 정상 동작) |

origin보다 뒤처진 것은 없음. 다만 controller/core/contracts에 **미푸시 커밋 3개**,
controller·core에 **미커밋 WIP**가 있어 지금 상태로는 바로 넘길 수 없음.

## 2. 로컬 개발 환경 셋업 기록

- pyenv로 Python **3.12.0** 설치 (`.python-version`이 요구하나 기존엔 3.12.12만 있었음).
- `jarvis_controller`, `jarvis_core`에 `.venv` 생성 및 의존성 설치.
- `jarvis_contracts`는 `pyproject.toml`/`setup.py`가 없어 `pip install` 불가.
  Docker는 requirements에서 해당 줄(`../jarvis_contracts`)을 제거하고
  `PYTHONPATH`로 대체하는 방식 → 로컬에서도 동일하게 처리함
  (`PYTHONPATH=<repo_root>:<service>/src`).
- `jarvis_gateway`, `jarvis_ai_workbench`는 미커밋 작업이 없어 venv 셋업 생략.
- README의 "`jarvis-ai-workbench` 심볼릭 링크 생성" 단계는 **오래된 내용**
  (Dockerfile/compose가 이미 언더스코어 경로를 직접 사용).

## 3. 테스트 결과 (uncommitted diff를 stash로 격리해 비교)

**jarvis_controller**: 213개 중 197개 통과.
- 실패 16개 중 15개는 클린 HEAD에서도 동일하게 실패 (대부분 `error=offline`,
  로컬 Ollama 미실행 / 네트워크 검색 테스트 — 환경 의존적, 코드 문제 아님).
- 나머지 1개는 **WIP에서 생긴 실제 회귀** (§4-A 참고).

**jarvis_core**: 47개 중 41개 통과 (`test_engine.py` 제외, §4-D 참고).
- 실패 6개 전부 클린 HEAD에서도 동일 (workbench 프롬프트 설정 경로 없음,
  로컬 Postgres 없음 — 환경 의존적).

## 4. 발견 사항 (우선순위순)

### 🔴 긴급

**A. `todo.list` 회귀 (jarvis_controller, WIP)**
`_todo_due_at_suffix`로 사람이 읽는 텍스트는 "오늘 09:54"로 포맷했지만, 같은
SSE payload의 raw `todos` 배열에는 원본 ISO 타임스탬프가 그대로 남아 있음.
`test_todo_today_list_filters_server_results` 실패 원인.
파일: `jarvis_controller/src/planner/action_pipeline.py`

**B. 하드코딩 관리자 계정 (jarvis_gateway)**
서버 시작마다 `admin@jarvis.local` / `admin123` 계정 자동 시딩.
SaaS로 외부 노출 시 사실상 백도어.
파일: `jarvis_gateway/src/jarvis_gateway/db.py:275-287` (`seed_admin()`)

**C. `JARVIS_AUTH_SECRET` 미설정 시 fail-open (jarvis_gateway)**
시크릿이 비어 있어도 토큰 발급(`issue()`)은 성공하고 검증(`get()`)만 거부함 →
로그인은 되는데 이후 모든 인증 호출이 401 나는 조용한 장애 가능.
배포 체크리스트에 시크릿 필수 검증 추가 필요.

**D. `jarvis_ai_workbench`의 `/api/config`, `/api/prompts` PUT에 인증 없음**
다른 서비스가 읽어가는 시스템 프롬프트를 누구나 덮어쓸 수 있음. 로컬 개발툴
용도면 무방하나, 외부 노출 시 반드시 인증/내부망 바인딩 필요.

### 🟠 목표(리소스 최소화 + 로컬 소형모델)와 직결

**E. realtime/deep 라우팅이 사실상 스텁 (jarvis_core)**
`src/core/config/engine.py`의 라우팅이 키워드 매칭 수준
(`"traceback"`, `"분석"` 포함 여부 등). "가벼운 로컬 모델로 최대한 처리하고
필요할 때만 무거운 처리로 넘긴다"는 목표의 핵심 로직이 아직 미완성.

**F. TTS 런타임 전역 락 (jarvis_tts_runtime)**
`app.py`가 전역 `threading.Lock` 하나로 모델 로딩/합성을 전부 직렬화.
맥미니 한 대로 다중 세션을 동시에 서빙하는 SaaS 시나리오에서 동시성 병목.

**G. execute/verify 엔드포인트가 아직 mock 기반 (jarvis_controller)**
README 자체 TODO에 명시. "에이전트가 실제로 컴퓨터를 조작한다"는 핵심 기능이
완성 전 단계.

**H. 토큰스토어/rate limiter가 메모리 전용 (jarvis_gateway)**
재시작 시 세션·revocation·rate limit 전부 소실. 단일 인스턴스 홈서버에선
당장 치명적은 아니나, 재배포마다 로그인 세션이 끊기는 문제.

### 🟡 유지보수성

**I. `jarvis_controller/src/router/router.py` 5,484줄**
라우트 핸들러 + 한/영 휴리스틱 NLU 로직이 한 파일에 혼재. git 로그상 이 파일에
좁은 범위 땜질 패치가 반복되는 패턴. 도메인별(브라우저/터미널/할일 등) 분리 검토.

**J. `jarvis_core/tests/test_engine.py` collection 자체가 깨짐**
`jarvis_core.engine`을 import하나 실제로는 `core.config.engine`으로
리팩터링됨(커밋 `7227a96`). CI 부재의 방증.

**K. `jarvis_core/=3.9.0` 스트레이 파일**
`pip install "pkg>=3.9.0"` 따옴표 누락으로 생성된 파일이 그대로 커밋됨. 삭제 대상.

### ⚪ 프로세스/위생

**L. 로컬 테스트 없이 커밋되어 온 흐름**
오늘 처음으로 로컬 개발환경을 셋업함 — 즉 이전 커밋들은 로컬 테스트 검증 없이
쌓였을 가능성. CI(GitHub Actions 등)로 `pytest` 자동 실행 추가 권장.

**M. README/runbook 문서 간 실행 명령 불일치**
`uvicorn jarvis_core.app:app` (runbook) vs `uvicorn app:app --app-dir src` (README).

## 5. 다음 액션 제안

1. A(todo 회귀) 수정 후 WIP 커밋
2. B, C, D 보안 이슈 처리 (특히 SaaS 외부 노출 전 필수)
3. E, F, G — 아키텍처 개선 로드맵으로 별도 논의
4. K 스트레이 파일 삭제, J 테스트 정리는 가벼운 정리 커밋으로 처리
5. CI 파이프라인 도입 검토 (L)

## 6. 조치 결과 (2026-08-24 진행분, 미커밋)

| 항목 | 상태 | 내용 |
|---|---|---|
| A. todo 회귀 | ✅ 완료 | `server_actions.py`에서 raw `due_at`도 마이크로초를 잘라 정규화. 회귀 테스트 통과 |
| B. 관리자 계정 하드코딩 | ✅ 완화 | `JARVIS_GATEWAY_SEED_ADMIN`(기본 true), `JARVIS_GATEWAY_ADMIN_PASSWORD` env로 분리 + 기본값 사용 시 startup 경고 로그. 완전 제거는 아님 — 기존 dev/test 로그인 흐름 보존 |
| C. AUTH_SECRET fail-open | ✅ 완료 | `JARVIS_AUTH_SECRET` 미설정 시 `TokenStore` 생성 자체가 실패하도록 변경 (fail-fast). 이전에 401로 깨져 있던 gateway 테스트 4개 전부 통과로 전환 |
| D. workbench 인증 없음 | ✅ 완료 | `JARVIS_WORKBENCH_TOKEN` 설정 시 PUT 엔드포인트에 Bearer 토큰 요구. 미설정 시 기존처럼 오픈(순수 로컬 dev 편의 유지). UI에 토큰 입력란 추가 |
| F. TTS 전역 락 | ✅ 완료 | 모델 단위 락(`_lock_for_model`)으로 교체 — 같은 모델 동시요청은 직렬화, 다른 모델은 병렬 처리 가능 |
| G. execute/verify mock | ⏸ 보류 | 코드 확인 결과, 기존 테스트(`test_execute_mock_success`)가 "mock" 동작을 명시적으로 기대하고 있고, 실제 액션 실행은 이미 `/conversation/stream` + `ActionDispatcher` 경로로 별도 존재. `/execute`·`/verify`를 그 경로에 연결하려면 동기 응답 → 클라이언트 대기/타임아웃 방식으로 계약 자체가 바뀜 — 코드 몇 줄로 해결할 문제가 아니라 **이 두 엔드포인트를 유지할지, deprecate하고 ActionDispatcher로 통합할지 제품 결정이 먼저 필요** |
| H. 토큰/rate-limit 메모리 전용 | ✅ 부분 완료 | 로그아웃(토큰 revoke)은 DB에 영속화해 재시작에도 유지되도록 수정 + 회귀 테스트 추가. rate limiter 카운터는 재시작 시 리셋되는 낮은 리스크로 판단해 그대로 둠 (필요시 후속 작업) |
| I. router.py 5,484줄 | ✅ 부분 완료 | todo 의도탐지 휴리스틱(~14개 함수)을 `src/router/intent_todo.py` + `src/router/text_match.py`로 분리 → 5,484줄 → 5,090줄. 브라우저/터미널 클러스터도 같은 패턴으로 분리 가능하나 결합도가 높아 이번 작업 범위에서는 보류 |
| J. test_engine.py 깨짐 | ✅ 완료 | import 경로를 `jarvis_core.engine` → `core.config.engine`으로 수정, 통과 확인 |
| K. 스트레이 파일 | ✅ 완료 | `jarvis_core/=3.9.0` 삭제 |
| L. CI 부재 | ⏸ 보류 | 이번 작업 범위 밖 — GitHub Actions 워크플로 추가는 별도 논의 필요 |
| M. README/runbook 불일치 | ✅ 완료 | `runbook.md`의 uvicorn 커맨드를 README와 일치시킴 |
| E. realtime/deep 라우팅 스텁 | ⏸ 보류 | README 자체가 "library-first placeholder"로 명시한 의도적 미완성 상태. 어떤 기준으로 "실시간 vs deep"을 가를지(모델 기반 분류? 더 정교한 휴리스틱?)는 제품 설계 결정 — 임의로 구현하면 스펙 없는 추측성 로직이 됨 |

전 항목 수정 후 controller(198 pass / 15 fail, 전부 기존 환경 의존 실패), core(43 pass / 6 fail, 전부 기존 환경 의존 실패), gateway(8/8), workbench(6/6) 전부 재확인 — **새로 생긴 회귀 없음**. 아직 커밋은 하지 않음.

## 7. 이후 진행 사항 (같은 세션, 6번 이후)

6번 이후 모든 변경사항은 각 레포 `main`에 커밋 + push 완료됨 (커밋 목록은 각
레포 `git log` 참고).

### 7.1 클라이언트(userspace) 액션 커버리지 감사 및 게임 컨트롤 확장
- `browser_control`에 빠져있던 6개 커맨드 구현: `scroll`, `new_tab`, `new_window`,
  `close_tab`, `focus_address_bar`, `search`
- `mouse_move`, `mouse_scroll` 신규 액션 타입 추가, `mouse_click`/`mouse_drag`에
  `button`(좌/우/중) 지원 추가 — 기존엔 AppleScript 한계로 우클릭이 아예 안 됐음
- `hotkey`에 `duration_seconds`(홀드) 지원 — WASD 같은 이동키 홀드 조작용
- `file_manage`(mkdir/move/delete), `system_info`(프로세스/앱 목록), `key_press`,
  `mouse.position` — userspace(클라이언트)엔 이미 구현돼 있었지만
  `jarvis_contracts`에 등록이 안 돼 있어서 AI가 대화 중에 못 쓰던 "숨겨진 기능"들을
  등록해서 실제로 쓸 수 있게 함
- 위 작업 중 userspace 쪽 upstream(다른 세션의 동시 작업)과 충돌 발생 —
  `dispatcher.py`/`physical_input.py`/`setup.py`/`config.py` 4개 파일 수동 병합

### 7.2 실시간 화면 스트리밍 + 로컬 vision 모델 연동
- `screen_stream` 액션(`start`/`stop`/`describe`) — 클라이언트가 화면을 주기적으로
  캡처해 `POST /client/vision/frame`으로 전송, 컨트롤러가 유저별 최신 프레임 1장을
  캐싱
- `describe`는 서버에서 바로 처리(클라이언트 왕복 없음) — 캐싱된 프레임을
  `jarvis_core`의 로컬 vision 모델(`ai/vision.py`, Ollama `qwen2.5vl:3b` 기본값,
  클라우드 API 미사용)에 넣어 텍스트 설명을 받아옴
- deepthink 실행 프롬프트가 원래 "스크린샷 찍으면 다음 단계에서 좌표 분석에 씀"이라고
  되어 있었는데, 실제 모델은 텍스트 전용이라 이미지를 볼 수 없었음 — `screen_stream
  describe`(텍스트 결과)로 바꿔서 실제로 "보고 판단"이 가능해짐

### 7.3 자율 관찰-행동 루프 (자율 루프)
- `POST /deepthink/watch` — 목표 하나를 주면 "관찰(describe) → 다음 액션 결정 →
  실행 → 결과를 컨텍스트에 누적 → 반복"을 SSE로 스트리밍. 더 할 게 없거나(`notify`
  액션으로 결과 보고), 최대 반복/시간 초과, 취소 시 종료
- `POST /deepthink/watch/start` — 같은 루프를 백그라운드 스레드에서 돌려서 HTTP
  연결을 안 붙잡아둠. 액션은 기존 `ActionDispatcher` 큐로, "다 됐다" 신호는 기존
  `notify` 액션으로 — 새 전송 구조나 새 액션 타입 없이 기존 인프라 재사용
- `autonomous_intent.py` — "계속 지켜보면서", "watch and keep playing until" 같은
  좁은 문구만 감지해서 대화 중 자동으로 백그라운드 루프 트리거. `router.py`의 기존
  5,000줄 로직은 건드리지 않고 진입점 한 곳에만 연결
- 조사 중 발견: `jarvis_core`의 웹소켓 기반 `run_realtime`은 실제로 **어디서도
  호출되지 않는 죽은 코드**였음 — 실제 대화 경로는 전부 HTTP 요청/응답 + SSE.
  덕분에 웹소켓 루프를 안 건드리고도 백그라운드 실행이 가능했음
- 구현 중 버그 하나 발견·수정: 백그라운드 루프 취소를 기존
  `TurnCancellationStore`(유저당 활성 턴 1개, barge-in용)에 등록했더니 자기를
  트리거한 대화 턴 자체를 취소시키는 부작용이 있었음 — 독립된 취소 플래그로 분리

### 7.4 router.py 유지보수성 (부분 진행)
- `browser_control` 관련 헬퍼는 그대로 두고, todo 의도탐지 로직 분리(6번에서 이미
  진행)에 이어 `autonomous_intent.py`처럼 새 기능은 처음부터 별도 파일로 분리하는
  패턴을 유지 중

### 7.5 `.gitignore` 정리
- `jarvis_contracts/.gitignore`를 다른 서비스들과 같은 수준으로 보강(`.venv/`,
  캐시, `*.egg-info/` 등 누락돼 있었음)
- `jarvis_gateway/.gitignore`에 `.env` 추가
- `jarvis_ai_workbench/uv.lock` 트래킹 시작 (controller/core는 이미 트래킹 중이던
  것과 통일)
- 루트 `.gitignore`에 `*.egg-info/`, 캐시 디렉토리들, `graphify-out/`(재생성 가능한
  산출물) 추가

### 7.6 문서 정리 (이번 항목)
- `CODEx.md`, `jarvis_core/CORE_INTEGRATION_TASK.md` → `docs/archive/`로 이동 (전부
  완료된 작업의 기록, "현재 상태"라는 제목이 오해를 줘서 보관 배너 추가)
- `REFACTORING_PLAN.md` — Phase 1·2 완료 확인, Phase 3은 `core_bridge.py` 삭제
  1건만 남음(죽은 코드, 어디서도 import 안 됨 — 삭제 안전), Phase 4(gateway
  `LoginRequest`/`LoginResponse` 중복 제거)는 미착수 확인. 각 표에 상태 표시

### 남은 것 (다음에 볼 것)
- `jarvis_controller/src/middleware/core_bridge.py` 삭제 (죽은 코드 확인됨)
- `jarvis_gateway/src/jarvis_gateway/models.py`의 `LoginRequest`/`LoginResponse`를
  `jarvis_contracts`에서 import하도록 변경 (REFACTORING_PLAN Phase 4)
- 캘린더 일정 생성/수정/삭제 — provider 미연동 (Google Calendar API? Apple
  EventKit?) 상태로 여전히 남아있음
- 대화창 말풍선+TTS로 말하는 `assistant_message` 액션 — 선제적 상호작용을 OS
  알림(`notify`)이 아니라 실제 음성으로 하려면 필요. Electron/React UI 쪽이라 직접
  실행 검증 불가능해서 보류 중

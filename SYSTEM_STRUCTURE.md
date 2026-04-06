# JARVIS 구조 정리

현재 통합 레포는 역할을 분리한 4개 핵심 모듈을 중심으로 구성한다.

- `jarvis_contracts`: 모듈 간에 공통으로 사용하는 계약 모델과 구조체 정의
- `jarvis_gateway`: 사용자 인증/인가와 세션, 감사 로그를 담당하는 진입 보안 계층
- `jarvis_core`: AI provider 연동과 코어 추론, DB 작업을 담당하는 도메인 계층
- `jarvis_controller`: 외부 엔드포인트 관리와 대화 흐름 제어, 플래닝 오케스트레이션을 담당하는 조정 계층

## 1. 역할 분리 원칙

각 모듈은 아래 원칙으로 분리한다.

- 계약은 `jarvis_contracts`에 둔다.
- 인증과 권한 판정은 `jarvis_gateway`에서 처리한다.
- 실제 AI 호출, 코어 판단, 데이터 저장은 `jarvis_core`가 맡는다.
- 사용자가 직접 호출하는 API와 흐름 제어는 `jarvis_controller`가 맡는다.

즉, 전체 구조는 `입구(gateway) -> 조정(controller) -> 판단/처리(core)` 흐름으로 이해하면 된다.

## 2. 모듈별 책임

### `jarvis_contracts`

공통 DTO와 계약 버전을 관리하는 공유 패키지다.

- 요청/응답 모델 표준화
- planning, execute, verify 관련 구조 정의
- conversation/auth 관련 payload 정의
- 서비스 간 인터페이스 안정성 확보

대표 파일:

- `jarvis_contracts/models.py`
- `jarvis_contracts/conversation_models.py`
- `jarvis_contracts/router_models.py`

이 레이어에는 비즈니스 로직을 넣지 않고, "어떤 형태로 데이터를 주고받는가"만 둔다.

### `jarvis_gateway`

보안과 사용자 컨텍스트를 책임지는 FastAPI 게이트웨이다.

- 로그인/로그아웃
- Bearer token 발급 및 검증
- 사용자/테넌트/역할 기반 접근 제어
- 세션 생성 및 종료
- rate limit
- audit log 기록

핵심 의미는 다음과 같다.

- 외부 요청은 먼저 `jarvis_gateway`의 정책을 통과해야 한다.
- `jarvis_controller`는 직접 인증을 구현하기보다 `jarvis_gateway` 결과를 신뢰하고 사용한다.
- 보안 정책과 비즈니스 추론 로직을 분리해 책임 경계를 명확히 한다.

### `jarvis_core`

실제 AI 처리와 데이터 계층의 중심이다.

- AI provider 연동
- realtime/deep 같은 코어 추론 실행
- DB 연결 및 저장소 처리
- 코어 도메인 로직 제공

현재 관점에서 `jarvis_core`는 "직접 엔드포인트를 많이 노출하는 서비스"보다는, `jarvis_controller`가 호출하는 코어 라이브러리/도메인 계층에 가깝다.

정리하면:

- `jarvis_core`는 무엇을 판단하고 어떤 결과를 만들지에 집중한다.
- `jarvis_controller`는 그 판단 결과를 언제 호출하고 어떤 흐름에 태울지를 결정한다.

플랜 생성에 대해서는 현재 설계 의도를 다음처럼 보는 것이 가장 자연스럽다.

- 플래닝 제어와 사용자 응답 조립은 `jarvis_controller`
- 직접적인 코어 판단 로직과 향후 확장 가능한 플랜 생성 능력은 `jarvis_core`

즉 "플랜을 어디서 노출하고 관리하느냐"는 `controller`, "플랜의 실질적 지능을 어디에 축적하느냐"는 `core`로 가져가는 방향이다.

### `jarvis_controller`

사용자 요청을 받아 실제 처리 흐름으로 연결하는 조정 레이어다.

- 외부 엔드포인트 제공
- gateway 인증 결과를 받아 사용자 컨텍스트 연결
- 대화 모드 분기
- planning/realtime/deep 흐름 선택
- execute/verify 같은 실행 단위 제어
- core 호출 결과를 사용자 응답 포맷으로 정리

이 레이어는 "오케스트레이터"에 가깝다.

- 요청을 받는다.
- 어떤 모드로 처리할지 판단한다.
- 필요하면 core를 호출한다.
- 필요하면 planning 결과를 조립한다.
- 최종 응답 계약에 맞게 내려준다.

따라서 `jarvis_controller`는 직접 무거운 AI 연산을 오래 들고 있기보다, 흐름 제어와 API 관리에 집중하는 것이 맞다.

## 3. 권장 호출 흐름

### 인증이 필요한 일반 대화

1. 클라이언트가 `jarvis_controller` 엔드포인트를 호출한다.
2. `jarvis_controller`는 `jarvis_gateway`를 통해 인증/인가를 확인한다.
3. `jarvis_controller`는 요청 성격을 보고 realtime/deep/planning 중 하나를 선택한다.
4. realtime/deep이면 `jarvis_core`를 호출해 결과를 받는다.
5. planning이면 controller가 플래닝 흐름을 관리하고, 필요 시 core의 판단 능력과 결합한다.
6. 최종 응답은 `jarvis_contracts` 규격에 맞춰 반환한다.

### 실행/검증 흐름

1. 계획 또는 액션 요청이 들어온다.
2. `jarvis_controller`가 execute/verify 엔드포인트를 관리한다.
3. 필요한 계약 모델은 `jarvis_contracts`를 사용한다.
4. 실행 결과와 검증 결과는 표준 응답으로 반환한다.

## 4. 레이어 경계

아래 경계는 유지하는 편이 좋다.

### `jarvis_contracts`에 넣을 것

- Pydantic 모델
- 공통 enum
- 서비스 간 요청/응답 포맷
- contract version

### `jarvis_gateway`에 넣을 것

- 로그인 정책
- 토큰 처리
- role/tenant 권한 검사
- 세션 및 감사 로그
- rate limit

### `jarvis_core`에 넣을 것

- provider adapter
- prompt/추론 로직
- memory 및 DB access
- 코어 판단 엔진
- 플랜 생성 로직이 고도화될 경우 그 핵심 알고리즘

### `jarvis_controller`에 넣을 것

- API router
- 요청별 orchestration
- 모드 분기
- 실행 순서 제어
- core/gateway 연결 어댑터
- 사용자 응답 조립

## 5. 지금 구조를 한 문장으로 요약하면

`jarvis_gateway`가 사용자를 확인하고, `jarvis_controller`가 요청 흐름을 조정하고, `jarvis_core`가 실제 AI/DB 작업을 수행하며, 그 사이에서 `jarvis_contracts`가 공통 언어를 제공하는 구조다.

## 6. 권장 방향

현재 설계를 계속 밀고 가려면 아래 기준으로 정리하는 것이 좋다.

- `controller`는 얇고 명확한 orchestration 계층으로 유지
- `core`는 provider, memory, planning intelligence가 쌓이는 중심 계층으로 강화
- `gateway`는 인증/인가와 감사 책임만 확실하게 고정
- `contracts`는 모든 서비스가 공유하는 단일 계약 원천으로 유지

이렇게 가면 각 모듈의 책임이 겹치지 않고, 이후에도 독립 배포나 교체가 쉬워진다.

# jarvis_contracts

`jarvis_contracts`는 JARVIS 전체 모듈이 공통으로 사용하는 계약 모델과 구조체를 정의하는 공유 패키지다.

이 디렉토리의 목적은 "서비스 간에 어떤 데이터를 어떤 형식으로 주고받는가"를 단일 기준으로 관리하는 것이다.  
비즈니스 로직, 인증 정책, AI 호출 로직은 여기 넣지 않는다.

## 역할

- 공통 request/response 모델 정의
- conversation, planning, execute, verify 계약 표준화
- contract version 관리
- 서비스 간 인터페이스 안정성 확보

## 현재 포함하는 모델

- `conversation_models.py`
  - 로그인 응답
  - 사용자 principal 응답
  - 대화 요청/응답
  - planning payload
- `models.py`
  - plan / execute / verify 관련 기본 계약
  - 공통 `ErrorResponse`
- `router_models.py`
  - controller 라우터 계층에서 쓰는 conversation/auth 모델

## 다른 모듈과의 관계

- `jarvis_gateway`는 인증/인가 결과를 이 계약에 맞춰 외부로 전달한다.
- `jarvis_controller`는 사용자 엔드포인트 응답을 이 계약에 맞춰 조립한다.
- `jarvis_core`는 코어 처리 결과를 직접 또는 간접적으로 이 계약에 매핑할 수 있어야 한다.

즉, `jarvis_contracts`는 각 서비스가 공유하는 공통 언어다.

## 관리 원칙

- 중복 모델을 최소화한다.
- 필드 이름과 의미는 한 번 정하면 쉽게 바꾸지 않는다.
- 서비스 내부 전용 모델과 외부 계약 모델을 섞지 않는다.
- 버전 호환성이 깨지는 변경은 명시적으로 관리한다.

## 참고 파일

- `jarvis_contracts/conversation_models.py`
- `jarvis_contracts/models.py`
- `jarvis_contracts/router_models.py`

## 할 일

- `conversation_models.py`와 `router_models.py`의 중복 모델을 정리해 단일 계약 원천으로 합치기
- contract version 증가 정책과 하위 호환 규칙 문서화
- 필드별 의미와 필수/선택 여부를 표로 정리
- 에러 코드 체계를 공통 enum 또는 상수로 분리
- 서비스별 예시 payload를 추가해 연동 기준 명확화

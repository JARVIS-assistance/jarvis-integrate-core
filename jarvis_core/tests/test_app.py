from fastapi.testclient import TestClient
from jarvis_contracts import JarvisCoreEndpoints

from app import create_app


def test_health() -> None:
    client = TestClient(create_app())
    response = client.get(JarvisCoreEndpoints.HEALTH.path)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mode"] == "library-first"
    assert payload["capabilities"] == ["realtime", "deep"]


def test_internal_conversation_realtime_endpoint() -> None:
    client = TestClient(create_app())
    response = client.post(
        JarvisCoreEndpoints.INTERNAL_CONVERSATION_RESPOND.path,
        json={"mode": "realtime", "message": "배포 상태 알려줘"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "realtime"
    assert "실시간 응답" in payload["content"]


def test_internal_conversation_deep_endpoint() -> None:
    client = TestClient(create_app())
    response = client.post(
        JarvisCoreEndpoints.INTERNAL_CONVERSATION_RESPOND.path,
        json={"mode": "deep", "message": "Traceback: bad state"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "deep"
    assert "Deep thinking result" in payload["content"]

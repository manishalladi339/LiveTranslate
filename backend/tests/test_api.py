from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app, get_translator


def setup_module() -> None:
    get_settings.cache_clear()
    get_translator.cache_clear()


client = TestClient(app)


def test_health_and_languages() -> None:
    assert client.get("/health").json()["status"] == "healthy"
    response = client.get("/api/v1/languages")
    assert response.status_code == 200
    assert len(response.json()["languages"]) == 8


def test_demo_translation() -> None:
    response = client.post(
        "/api/v1/translate",
        json={"text": "Thank you", "source_language": "en", "target_language": "hi"},
    )
    assert response.status_code == 200
    assert response.json()["translated"] == "धन्यवाद"
    assert response.json()["is_demo"] is True


def test_rejects_invalid_pair() -> None:
    response = client.post(
        "/api/v1/translate",
        json={"text": "Hello", "source_language": "en", "target_language": "en"},
    )
    assert response.status_code == 400


def test_live_websocket() -> None:
    with client.websocket_connect("/api/v1/live/test-session") as websocket:
        assert websocket.receive_json()["type"] == "ready"
        websocket.send_json(
            {
                "type": "translate",
                "turn_id": "turn-1",
                "text": "Hello",
                "source_language": "en",
                "target_language": "es",
                "is_final": True,
            }
        )
        result = websocket.receive_json()
        assert result["type"] == "translation"
        assert result["translated"] == "Hola"
        assert result["turn_id"] == "turn-1"


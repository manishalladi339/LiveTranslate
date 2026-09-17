from fastapi.testclient import TestClient
import pytest
import asyncio
import httpx
from starlette.websockets import WebSocketDisconnect

from app.config import get_settings
from app.main import app, get_translator
from app.config import Settings
from app.translator import Translator, TranslationBusyError


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


def test_unknown_demo_phrase_is_not_a_fake_translation():
    response = client.post('/api/v1/translate', json={
        'text': 'An unsupported sentence', 'source_language': 'en', 'target_language': 'es',
    })
    assert response.status_code == 400
    assert 'demo mode' in response.json()['detail']


def test_websocket_recovers_after_invalid_messages():
    with client.websocket_connect('/api/v1/live/validation') as socket:
        socket.receive_json()
        for message in ['not json', '[]', '{"type":"translate","text":123}']:
            socket.send_text(message)
            assert socket.receive_json()['type'] == 'error'
        socket.send_json({'type': 'ping'})
        assert socket.receive_json()['type'] == 'pong'


def test_websocket_rejects_untrusted_origin():
    with pytest.raises(WebSocketDisconnect) as failure:
        with client.websocket_connect('/api/v1/live/origin', headers={'origin': 'https://untrusted.example'}):
            pass
    assert failure.value.code == 1008


def test_provider_failure_is_recoverable(monkeypatch):
    async def failed(*args):
        raise RuntimeError('invalid provider response')
    monkeypatch.setattr(get_translator(), 'translate', failed)
    response = client.post('/api/v1/translate', json={
        'text': 'Hello', 'source_language': 'en', 'target_language': 'es',
    })
    assert response.status_code == 502
    assert response.json()['detail'] == 'Translation provider unavailable'


@pytest.mark.parametrize('content,valid', [('{"translation":"Hola"}', True), ('not json', False), ('{"translation":123}', False)])
def test_openai_response_contract(monkeypatch, content, valid):
    real_client = httpx.AsyncClient
    def handle(request):
        import json
        payload = json.loads(request.content)
        assert 'temperature' not in payload
        return httpx.Response(200, json={'choices': [{'message': {'content': content}}]})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs))
    translator = Translator(Settings(translation_provider='openai', openai_api_key='test-only'))
    if valid:
        assert asyncio.run(translator.translate('Hello', 'en', 'es')).translated == 'Hola'
    else:
        with pytest.raises(RuntimeError, match='invalid response'):
            asyncio.run(translator.translate('Hello', 'en', 'es'))
    assert translator.inflight == 0


def test_paid_provider_request_limit(monkeypatch):
    from app.translator import TranslationResult
    translator = Translator(Settings(translation_provider='openai', openai_api_key='test-only'))
    async def translated(*args):
        return TranslationResult('Hola', 'test', False)
    monkeypatch.setattr(translator, '_openai', translated)
    async def run():
        for _ in range(30):
            await translator.translate('Hello', 'en', 'es')
        with pytest.raises(TranslationBusyError):
            await translator.translate('Hello', 'en', 'es')
    asyncio.run(run())

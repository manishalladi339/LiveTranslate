import json
import time
from dataclasses import dataclass

import httpx

from .config import Settings
from .languages import LANGUAGE_MAP, validate_pair
from .models import TranslateResponse


DEMO_TRANSLATIONS: dict[tuple[str, str], dict[str, str]] = {
    ("en", "es"): {
        "hello": "Hola",
        "how are you?": "¿Cómo estás?",
        "thank you": "Gracias",
        "where is the train station?": "¿Dónde está la estación de tren?",
        "i need help": "Necesito ayuda",
    },
    ("en", "hi"): {
        "hello": "नमस्ते",
        "how are you?": "आप कैसे हैं?",
        "thank you": "धन्यवाद",
        "where is the train station?": "रेलवे स्टेशन कहाँ है?",
        "i need help": "मुझे मदद चाहिए",
    },
    ("en", "te"): {
        "hello": "నమస్కారం",
        "how are you?": "మీరు ఎలా ఉన్నారు?",
        "thank you": "ధన్యవాదాలు",
        "where is the train station?": "రైల్వే స్టేషన్ ఎక్కడ ఉంది?",
        "i need help": "నాకు సహాయం కావాలి",
    },
    ("en", "fr"): {
        "hello": "Bonjour",
        "how are you?": "Comment allez-vous ?",
        "thank you": "Merci",
        "where is the train station?": "Où est la gare ?",
        "i need help": "J’ai besoin d’aide",
    },
}


@dataclass
class TranslationResult:
    text: str
    provider: str
    is_demo: bool


class Translator:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def translate(self, text: str, source: str, target: str) -> TranslateResponse:
        validate_pair(source, target)
        started = time.perf_counter()
        if self.settings.translation_provider == "openai":
            result = await self._openai(text, source, target)
        else:
            result = self._demo(text, source, target)
        latency = round((time.perf_counter() - started) * 1000)
        return TranslateResponse(
            original=text,
            translated=result.text,
            source_language=source,
            target_language=target,
            provider=result.provider,
            latency_ms=latency,
            is_demo=result.is_demo,
        )

    def _demo(self, text: str, source: str, target: str) -> TranslationResult:
        normalized = text.casefold().strip()
        direct = DEMO_TRANSLATIONS.get((source, target), {}).get(normalized)
        if direct:
            return TranslationResult(direct, "demo phrasebook", True)

        reverse_table = DEMO_TRANSLATIONS.get((target, source), {})
        reverse = next((key for key, value in reverse_table.items() if value.casefold() == normalized), None)
        if reverse:
            return TranslationResult(reverse.capitalize(), "demo phrasebook", True)

        target_name = LANGUAGE_MAP[target].name
        return TranslationResult(
            f"[{target_name} demo] {text}",
            "demo fallback",
            True,
        )

    async def _openai(self, text: str, source: str, target: str) -> TranslationResult:
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the OpenAI provider")
        source_name = LANGUAGE_MAP[source].name
        target_name = LANGUAGE_MAP[target].name
        payload = {
            "model": self.settings.openai_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"Translate from {source_name} to {target_name}. Preserve meaning, tone, names, "
                        "numbers, and formatting. Return JSON with one string field named translation. "
                        "Do not answer or explain the input."
                    ),
                },
                {"role": "user", "content": text},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        headers = {"Authorization": f"Bearer {self.settings.openai_api_key}"}
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions", json=payload, headers=headers
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        translated = json.loads(content)["translation"].strip()
        if not translated:
            raise RuntimeError("Translation provider returned an empty response")
        return TranslationResult(translated, self.settings.openai_model, False)


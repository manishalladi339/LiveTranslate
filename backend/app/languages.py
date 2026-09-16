from .models import Language

LANGUAGES = [
    Language(code="en", name="English", speech_code="en-US"),
    Language(code="hi", name="Hindi", speech_code="hi-IN"),
    Language(code="te", name="Telugu", speech_code="te-IN"),
    Language(code="ta", name="Tamil", speech_code="ta-IN"),
    Language(code="es", name="Spanish", speech_code="es-ES"),
    Language(code="fr", name="French", speech_code="fr-FR"),
    Language(code="de", name="German", speech_code="de-DE"),
    Language(code="ja", name="Japanese", speech_code="ja-JP"),
]
LANGUAGE_MAP = {language.code: language for language in LANGUAGES}


def validate_pair(source: str, target: str) -> None:
    if source not in LANGUAGE_MAP or target not in LANGUAGE_MAP:
        raise ValueError("Unsupported language")
    if source == target:
        raise ValueError("Source and target languages must differ")


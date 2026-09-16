from pydantic import BaseModel, Field, field_validator


class Language(BaseModel):
    code: str
    name: str
    speech_code: str


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    source_language: str
    target_language: str

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Text cannot be blank")
        return cleaned


class TranslateResponse(BaseModel):
    original: str
    translated: str
    source_language: str
    target_language: str
    provider: str
    latency_ms: int
    is_demo: bool


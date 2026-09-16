export type Language = { code: string; name: string; speech_code: string }

export type Translation = {
  id: string
  original: string
  translated: string
  source_language: string
  target_language: string
  provider: string
  latency_ms: number
  is_demo: boolean
  createdAt: string
}

export interface SpeechRecognitionEventLike extends Event {
  results: {
    length: number
    [index: number]: { 0: { transcript: string }; isFinal: boolean }
  }
  resultIndex: number
}

export interface SpeechRecognitionLike {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onend: (() => void) | null
  onerror: ((event: Event) => void) | null
  start: () => void
  stop: () => void
}

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionLike
    webkitSpeechRecognition?: new () => SpeechRecognitionLike
  }
}


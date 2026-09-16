import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowRightLeft,
  CircleStop,
  Copy,
  Download,
  Languages,
  MessageCircleMore,
  Mic,
  Play,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  Volume2,
  Wifi,
  WifiOff,
} from 'lucide-react'
import type { Language, SpeechRecognitionEventLike, SpeechRecognitionLike, Translation } from './types'

const fallbackLanguages: Language[] = [
  { code: 'en', name: 'English', speech_code: 'en-US' },
  { code: 'hi', name: 'Hindi', speech_code: 'hi-IN' },
  { code: 'te', name: 'Telugu', speech_code: 'te-IN' },
  { code: 'ta', name: 'Tamil', speech_code: 'ta-IN' },
  { code: 'es', name: 'Spanish', speech_code: 'es-ES' },
  { code: 'fr', name: 'French', speech_code: 'fr-FR' },
  { code: 'de', name: 'German', speech_code: 'de-DE' },
  { code: 'ja', name: 'Japanese', speech_code: 'ja-JP' },
]

const API_URL = import.meta.env.VITE_API_URL ?? ''

function App() {
  const [languages, setLanguages] = useState(fallbackLanguages)
  const [source, setSource] = useState('en')
  const [target, setTarget] = useState('es')
  const [text, setText] = useState('')
  const [interim, setInterim] = useState('')
  const [history, setHistory] = useState<Translation[]>([])
  const [isListening, setIsListening] = useState(false)
  const [isTranslating, setIsTranslating] = useState(false)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState('')
  const [provider, setProvider] = useState('connecting')
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const historyRef = useRef<HTMLDivElement | null>(null)

  const sourceLanguage = useMemo(() => languages.find((item) => item.code === source), [languages, source])
  const speechSupported = Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)

  useEffect(() => {
    fetch(`${API_URL}/api/v1/languages`)
      .then((response) => {
        if (!response.ok) throw new Error('Language service unavailable')
        return response.json()
      })
      .then((data) => {
        setLanguages(data.languages)
        setProvider(data.provider)
      })
      .catch(() => setProvider('offline'))
  }, [])

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const apiHost = API_URL ? API_URL.replace(/^http/, 'ws') : `${protocol}//${window.location.host}`
    const socket = new WebSocket(`${apiHost}/api/v1/live/${crypto.randomUUID()}`)
    socketRef.current = socket
    socket.onopen = () => setConnected(true)
    socket.onclose = () => setConnected(false)
    socket.onerror = () => setError('Live connection unavailable. Text translation still works.')
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data)
      if (message.type === 'translation') {
        setHistory((items) => [
          ...items,
          { ...message, id: message.turn_id ?? crypto.randomUUID(), createdAt: new Date().toISOString() },
        ])
        setIsTranslating(false)
      } else if (message.type === 'error') {
        setError(message.message)
        setIsTranslating(false)
      }
    }
    return () => socket.close()
  }, [])

  useEffect(() => {
    historyRef.current?.scrollTo({ top: historyRef.current.scrollHeight, behavior: 'smooth' })
  }, [history])

  async function translate(value: string) {
    const cleaned = value.trim()
    if (!cleaned || isTranslating) return
    setError('')
    setText('')
    setInterim('')
    setIsTranslating(true)
    const turnId = crypto.randomUUID()
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(
        JSON.stringify({
          type: 'translate',
          turn_id: turnId,
          text: cleaned,
          source_language: source,
          target_language: target,
          is_final: true,
        }),
      )
      return
    }
    try {
      const response = await fetch(`${API_URL}/api/v1/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: cleaned, source_language: source, target_language: target }),
      })
      if (!response.ok) throw new Error('Translation failed')
      const result = await response.json()
      setHistory((items) => [...items, { ...result, id: turnId, createdAt: new Date().toISOString() }])
    } catch {
      setError('Could not translate. Check that the API is running and try again.')
    } finally {
      setIsTranslating(false)
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    void translate(text)
  }

  function toggleListening() {
    if (isListening) {
      recognitionRef.current?.stop()
      setIsListening(false)
      return
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      setError('Live microphone transcription is not supported in this browser. Use Chrome or type below.')
      return
    }
    const recognition = new SpeechRecognition()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = sourceLanguage?.speech_code ?? 'en-US'
    recognition.onresult = (event: SpeechRecognitionEventLike) => {
      let partial = ''
      let finalText = ''
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index]
        if (result.isFinal) finalText += result[0].transcript
        else partial += result[0].transcript
      }
      setInterim(partial)
      if (finalText.trim()) void translate(finalText)
    }
    recognition.onerror = () => {
      setError('The microphone could not capture speech. Check browser permission and try again.')
      setIsListening(false)
    }
    recognition.onend = () => setIsListening(false)
    recognitionRef.current = recognition
    recognition.start()
    setIsListening(true)
    setError('')
  }

  function swapLanguages() {
    setSource(target)
    setTarget(source)
  }

  function speak(item: Translation) {
    if (!('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(item.translated)
    utterance.lang = languages.find((language) => language.code === item.target_language)?.speech_code ?? item.target_language
    window.speechSynthesis.speak(utterance)
  }

  function exportTranscript() {
    const lines = history.flatMap((item) => [
      `[${new Date(item.createdAt).toLocaleTimeString()}] ${languages.find((l) => l.code === item.source_language)?.name}: ${item.original}`,
      `${languages.find((l) => l.code === item.target_language)?.name}: ${item.translated}`,
      '',
    ])
    const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `livetranslate-${new Date().toISOString().slice(0, 10)}.txt`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="LiveTranslate home">
          <span className="brand-mark"><Languages size={22} /></span>
          <span>LiveTranslate</span>
        </a>
        <div className="status-row">
          <span className={`status ${connected ? 'online' : ''}`}>
            {connected ? <Wifi size={14} /> : <WifiOff size={14} />}
            {connected ? 'Live' : 'REST fallback'}
          </span>
          <span className="provider"><Sparkles size={14} /> {provider === 'demo' ? 'Demo provider' : provider}</span>
        </div>
      </header>

      <main id="top">
        <section className="hero">
          <div className="eyebrow"><MessageCircleMore size={16} /> Real-time conversation workspace</div>
          <h1>Speak naturally.<br /><span>Be understood anywhere.</span></h1>
          <p>Instant speech-to-text translation with voice playback, built for fluid conversations across languages.</p>
          <div className="trust"><ShieldCheck size={17} /> Audio stays in your browser. Only transcribed text reaches the translation API.</div>
        </section>

        <section className="workspace" aria-label="Translation workspace">
          <div className="language-bar">
            <label>
              <span>You speak</span>
              <select value={source} onChange={(event) => setSource(event.target.value)}>
                {languages.filter((language) => language.code !== target).map((language) => (
                  <option key={language.code} value={language.code}>{language.name}</option>
                ))}
              </select>
            </label>
            <button className="swap" type="button" onClick={swapLanguages} aria-label="Swap languages"><ArrowRightLeft size={20} /></button>
            <label>
              <span>Translate to</span>
              <select value={target} onChange={(event) => setTarget(event.target.value)}>
                {languages.filter((language) => language.code !== source).map((language) => (
                  <option key={language.code} value={language.code}>{language.name}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="conversation" ref={historyRef} aria-live="polite">
            {history.length === 0 ? (
              <div className="empty-state">
                <div className="soundwave"><i /><i /><i /><i /><i /></div>
                <h2>Your conversation starts here</h2>
                <p>Tap the microphone and speak, or type a message below.</p>
                <div className="prompts">
                  {['Hello', 'How are you?', 'Where is the train station?'].map((prompt) => (
                    <button key={prompt} type="button" onClick={() => void translate(prompt)}>{prompt}</button>
                  ))}
                </div>
              </div>
            ) : history.map((item) => (
              <article className="turn" key={item.id}>
                <div className="original">
                  <span>{languages.find((l) => l.code === item.source_language)?.name}</span>
                  <p>{item.original}</p>
                </div>
                <ArrowRightLeft className="turn-arrow" size={17} />
                <div className="translated">
                  <span>{languages.find((l) => l.code === item.target_language)?.name} · {item.latency_ms} ms</span>
                  <p>{item.translated}</p>
                  <div className="turn-actions">
                    <button type="button" onClick={() => speak(item)} aria-label="Listen"><Volume2 size={16} /> Listen</button>
                    <button type="button" onClick={() => void navigator.clipboard.writeText(item.translated)} aria-label="Copy"><Copy size={16} /> Copy</button>
                  </div>
                </div>
              </article>
            ))}
            {interim && <div className="interim"><span>Listening…</span>{interim}</div>}
          </div>

          {error && <div className="error" role="alert">{error}</div>}

          <div className="composer-wrap">
            <button className={`mic ${isListening ? 'listening' : ''}`} type="button" onClick={toggleListening} aria-label={isListening ? 'Stop listening' : 'Start listening'}>
              {isListening ? <CircleStop size={25} /> : <Mic size={25} />}
            </button>
            <form className="composer" onSubmit={submit}>
              <textarea value={text} onChange={(event) => setText(event.target.value)} placeholder={`Type in ${sourceLanguage?.name ?? 'your language'}…`} maxLength={2000} rows={1} />
              <button className="send" type="submit" disabled={!text.trim() || isTranslating} aria-label="Translate">
                {isTranslating ? <span className="spinner" /> : <Send size={20} />}
              </button>
            </form>
          </div>
          <div className="composer-note">
            <span>{speechSupported ? 'Microphone ready' : 'Text mode — microphone unsupported'}</span>
            <span>{text.length}/2000</span>
          </div>
        </section>

        <section className="session-tools">
          <div><Play size={18} /><span><strong>{history.length}</strong> translated turns this session</span></div>
          <div className="tool-actions">
            <button type="button" onClick={exportTranscript} disabled={!history.length}><Download size={17} /> Export</button>
            <button type="button" onClick={() => setHistory([])} disabled={!history.length}><Trash2 size={17} /> Clear</button>
          </div>
        </section>
      </main>

      <footer>Built as a privacy-aware portfolio MVP · Browser speech support varies by device</footer>
    </div>
  )
}

export default App

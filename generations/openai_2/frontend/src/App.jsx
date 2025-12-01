import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'

const STORAGE_KEYS = {
  conversations: 'claude-clone::conversations',
  activeId: 'claude-clone::activeConversationId',
  drafts: 'claude-clone::drafts'
}

const LEGACY_STORAGE_KEYS = {
  messages: 'claude-clone::messages',
  draft: 'claude-clone::draft'
}

const MAX_CHARACTERS = 1200
const STREAM_DELAY = 140

const SUGGESTED_PROMPTS = [
  'Summarize today\'s research notes into actionable tasks.',
  'Draft a product spec for a focus-enhancing notes app.',
  'Explain the difference between SSE and WebSockets in plain terms.',
  'Outline a plan to refactor a legacy Express API to TypeScript.',
  'Create a study guide for learning Rust with weekly milestones.'
]

const SANITIZE_CONFIG = {
  ADD_TAGS: ['button', 'span'],
  ADD_ATTR: ['target', 'rel', 'data-code', 'type'],
  ALLOW_DATA_ATTR: true
}

const renderer = new marked.Renderer()
renderer.link = (href, title, text) => {
  const safeHref = href ?? '#'
  const display = text ?? safeHref
  return `<a href="${safeHref}" target="_blank" rel="noreferrer noopener">${display}</a>`
}
renderer.code = (code, infostring = '') => {
  const lang = infostring.trim().split(/\s+/)[0]
  const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
  const highlighted = language === 'plaintext'
    ? hljs.highlightAuto(code).value
    : hljs.highlight(code, { language }).value
  const safeCode = encodeURIComponent(code)
  return `
    <div class="code-shell">
      <div class="code-shell__meta">
        <span>${language.toUpperCase()}</span>
        <button class="copy-code-btn" data-code="${safeCode}" type="button">Copy</button>
      </div>
      <pre><code class="hljs ${language}">${highlighted}</code></pre>
    </div>
  `
}

marked.setOptions({
  renderer,
  gfm: true,
  breaks: true,
  headerIds: false,
  mangle: false
})

const generateMessageId = (prefix) => `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
const generateConversationId = () => generateMessageId('conversation')

const createWelcomeMessage = () => ({
  id: generateMessageId('assistant'),
  role: 'assistant',
  content: '👋 Welcome to your Claude workspace. Draft prompts, iterate on ideas, and render artifacts with a calm, responsive interface.',
  createdAt: new Date().toISOString()
})

const createConversation = () => ({
  id: generateConversationId(),
  title: 'New conversation',
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  messages: [createWelcomeMessage()]
})

const cleanMessage = (msg) => ({
  id: msg.id ?? generateMessageId('msg'),
  role: msg.role === 'user' ? 'user' : 'assistant',
  content: typeof msg.content === 'string' ? msg.content : '',
  createdAt: msg.createdAt ?? new Date().toISOString()
})

const generateTitleFromContent = (text) => {
  if (!text) return 'New conversation'
  const trimmed = text.replace(/\s+/g, ' ').trim()
  if (!trimmed) return 'New conversation'
  return trimmed.length > 32 ? `${trimmed.slice(0, 32)}…` : trimmed
}

const loadLegacyMessages = () => {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(LEGACY_STORAGE_KEYS.messages)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.map(cleanMessage)
  } catch {
    return []
  }
}

const loadStoredConversations = () => {
  if (typeof window === 'undefined') return [createConversation()]
  try {
    const raw = window.localStorage.getItem(STORAGE_KEYS.conversations)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed.map((conversation) => ({
          id: conversation.id ?? generateConversationId(),
          title: conversation.title || 'New conversation',
          createdAt: conversation.createdAt ?? new Date().toISOString(),
          updatedAt: conversation.updatedAt ?? new Date().toISOString(),
          messages: Array.isArray(conversation.messages) && conversation.messages.length > 0
            ? conversation.messages.map(cleanMessage)
            : [createWelcomeMessage()]
        }))
      }
    }

    const legacyMessages = loadLegacyMessages()
    if (legacyMessages.length) {
      const conversation = {
        id: generateConversationId(),
        title: generateTitleFromContent(legacyMessages.find((m) => m.role === 'user')?.content),
        createdAt: legacyMessages[0]?.createdAt ?? new Date().toISOString(),
        updatedAt: legacyMessages[legacyMessages.length - 1]?.createdAt ?? new Date().toISOString(),
        messages: legacyMessages
      }
      window.localStorage.removeItem(LEGACY_STORAGE_KEYS.messages)
      window.localStorage.removeItem(LEGACY_STORAGE_KEYS.draft)
      return [conversation]
    }
  } catch {
    // ignore
  }
  return [createConversation()]
}

const loadStoredDrafts = () => {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(STORAGE_KEYS.drafts)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return typeof parsed === 'object' && parsed !== null ? parsed : {}
  } catch {
    return {}
  }
}

const formatTimestamp = (iso) => {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const formatConversationDate = (iso) => {
  if (!iso) return 'Previous'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return 'Previous'
  const now = new Date()
  if (date.toDateString() === now.toDateString()) return 'Today'
  const diff = now.getTime() - date.getTime()
  if (diff < 7 * 24 * 60 * 60 * 1000) return 'Last 7 days'
  return date.toLocaleString([], { month: 'long', year: 'numeric' })
}

const formatConversationPreview = (text = '') => {
  const normalized = text.replace(/\s+/g, ' ').trim()
  if (!normalized) return 'No messages yet'
  return normalized.length > 64 ? `${normalized.slice(0, 64)}…` : normalized
}

const buildAssistantReply = (prompt) => {
  const normalized = prompt.replace(/\s+/g, ' ').trim()
  const preview = normalized.length > 110 ? `${normalized.slice(0, 110)}…` : normalized
  return `Thanks for sharing **${preview || 'your idea'}**! Here\'s a structured way to move forward:\n\n1. **Clarify intent.** Capture the outcome you expect and success criteria.\n2. **Map the journey.** Break the work into measurable checkpoints with owners.\n3. **Ship iteratively.** Validate each checkpoint with feedback and adjust quickly.\n\n\`\`\`js\nconst nextSteps = [\n  'Outline constraints',\n  'Sketch an initial solution',\n  'Validate with a lightweight prototype'\n]\nconsole.log(nextSteps.join(' → '))\n\`\`\`\n\n> Tip: Pause or stop streaming anytime—your place in the conversation is saved locally.\n\nLet me know when you want me to dig deeper, create artifacts, or explore alternate approaches.`
}

const extractArtifacts = (messages = []) => {
  const artifacts = []
  messages.forEach((message) => {
    if (message.role !== 'assistant' || !message.content) return
    const blockMatches = [...message.content.matchAll(/```(\w+)?\n([\s\S]*?)```/g)]
    blockMatches.forEach((match, idx) => {
      const language = (match[1] || 'plaintext').trim()
      const content = match[2]?.trim() ?? ''
      artifacts.push({
        id: `${message.id}-${idx}`,
        language,
        content,
        sourceMessageId: message.id,
        title: `Artifact ${artifacts.length + 1}`
      })
    })
  })
  return artifacts
}

export default function App () { 
  // Theme support: light/dark toggle stored in localStorage
  const THEME_KEY = 'claude-clone::theme'
  const [theme, setTheme] = useState(() => {
    if (typeof window === 'undefined') return 'light'
    return window.localStorage.getItem(THEME_KEY) ?? 'light'
  })
  // apply theme on load and whenever it changes
  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', theme)
      window.localStorage.setItem(THEME_KEY, theme)
    }
  }, [theme])
  const toggleTheme = useCallback(() => {
    setTheme((t) => (t === 'light' ? 'dark' : 'light'))
  }, [])
  
  const [conversations, setConversations] = useState(() => loadStoredConversations())\n  \n  useEffect(() => {\n    const handler = (e) => {\n      if (e.key.toLowerCase() === 't') {\n        toggleTheme()\n      }\n    }\n    window.addEventListener('keydown', handler)\n    return () => window.removeEventListener('keydown', handler)\n  }, [toggleTheme])
  const [activeConversationId, setActiveConversationId] = useState(() => {
    if (typeof window === 'undefined') return null
    return window.localStorage.getItem(STORAGE_KEYS.activeId)
  })
  const [drafts, setDrafts] = useState(() => loadStoredDrafts())
  const [searchTerm, setSearchTerm] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [copyToast, setCopyToast] = useState('')
  const [activeArtifactId, setActiveArtifactId] = useState(null)

  const chatEndRef = useRef(null)
  const textareaRef = useRef(null)
  const streamTimerRef = useRef(null)
  const streamingMessageIdRef = useRef(null)
  const streamingConversationIdRef = useRef(null)
  const isPausedRef = useRef(false)

  const applyConversationChange = useCallback((updater) => {
    setConversations((prev) => {
      const next = updater(prev)
      return next.slice().sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    })
  }, [])

  const updateConversation = useCallback((conversationId, transformer) => {
    applyConversationChange((prev) => prev.map((conversation) => {
      if (conversation.id !== conversationId) return conversation
      return transformer(conversation)
    }))
  }, [applyConversationChange])

  useEffect(() => {
    if (!activeConversationId && conversations.length > 0) {
      setActiveConversationId(conversations[0].id)
    }
  }, [activeConversationId, conversations])

  const activeConversation = useMemo(() => {
    if (!conversations.length) return null
    return conversations.find((conv) => conv.id === activeConversationId) ?? conversations[0]
  }, [conversations, activeConversationId])

  const currentDraft = activeConversation ? drafts[activeConversation.id] ?? '' : ''
  const hasCharLimitError = currentDraft.length > MAX_CHARACTERS
  const tokenEstimate = currentDraft.trim().length === 0
    ? 0
    : Math.max(1, Math.ceil(currentDraft.trim().length / 4))

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(STORAGE_KEYS.conversations, JSON.stringify(conversations))
  }, [conversations])

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (activeConversation) {
      window.localStorage.setItem(STORAGE_KEYS.activeId, activeConversation.id)
    }
  }, [activeConversation])

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(STORAGE_KEYS.drafts, JSON.stringify(drafts))
  }, [drafts])

  const renderMarkdown = useCallback((text) => {
    const html = marked.parse(text || '')
    return DOMPurify.sanitize(html, SANITIZE_CONFIG)
  }, [])

  const clearStreamingTimer = useCallback(() => {
    if (streamTimerRef.current) {
      window.clearInterval(streamTimerRef.current)
      streamTimerRef.current = null
    }
  }, [])

  const finalizeStreaming = useCallback((conversationId, messageId) => {
    if (!conversationId || !messageId) return
    clearStreamingTimer()
    setIsStreaming(false)
    setIsPaused(false)
    isPausedRef.current = false
    streamingMessageIdRef.current = null
    streamingConversationIdRef.current = null
    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      messages: conversation.messages.map((message) => (
        message.id === messageId ? { ...message, streaming: false } : message
      )),
      updatedAt: new Date().toISOString()
    }))
  }, [clearStreamingTimer, updateConversation])

  const stopStreaming = useCallback(() => {
    if (!streamingMessageIdRef.current || !streamingConversationIdRef.current) return
    finalizeStreaming(streamingConversationIdRef.current, streamingMessageIdRef.current)
  }, [finalizeStreaming])

  const startStreaming = useCallback((conversationId, fullText) => {
    const trimmed = fullText.trim()
    if (!trimmed) return
    const messageId = generateMessageId('assistant')
    const words = trimmed.split(/\s+/)
    let index = 0

    streamingConversationIdRef.current = conversationId
    streamingMessageIdRef.current = messageId
    setIsStreaming(true)
    setIsPaused(false)
    isPausedRef.current = false

    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      messages: [
        ...conversation.messages,
        {
          id: messageId,
          role: 'assistant',
          content: '',
          createdAt: new Date().toISOString(),
          streaming: true
        }
      ],
      updatedAt: new Date().toISOString()
    }))

    streamTimerRef.current = window.setInterval(() => {
      if (isPausedRef.current) return
      index += 1
      const chunk = words.slice(0, index).join(' ')
      updateConversation(conversationId, (conversation) => ({
        ...conversation,
        messages: conversation.messages.map((message) => (
          message.id === messageId
            ? { ...message, content: chunk, streaming: index < words.length }
            : message
        )),
        updatedAt: new Date().toISOString()
      }))

      if (index >= words.length) {
        finalizeStreaming(conversationId, messageId)
      }
    }, STREAM_DELAY)
  }, [finalizeStreaming, updateConversation])

  const handleConversationSelect = useCallback((conversationId) => {
    if (conversationId === activeConversation?.id) return
    stopStreaming()
    setActiveConversationId(conversationId)
  }, [activeConversation, stopStreaming])

  const handleDraftChange = useCallback((text) => {
    if (!activeConversation) return
    setDrafts((prev) => ({ ...prev, [activeConversation.id]: text }))
  }, [activeConversation])

  const handlePromptSelect = useCallback((prompt) => {
    handleDraftChange(prompt)
    window.requestAnimationFrame(() => textareaRef.current?.focus())
  }, [handleDraftChange])

  const handleSend = useCallback(() => {
    if (!activeConversation) return
    const trimmed = currentDraft.trim()
    if (!trimmed || trimmed.length > MAX_CHARACTERS || isStreaming) return

    const userMessage = {
      id: generateMessageId('user'),
      role: 'user',
      content: trimmed,
      createdAt: new Date().toISOString()
    }

    updateConversation(activeConversation.id, (conversation) => {
      const title = conversation.messages.length <= 1
        ? generateTitleFromContent(trimmed)
        : conversation.title
      return {
        ...conversation,
        title,
        messages: [...conversation.messages, userMessage],
        updatedAt: new Date().toISOString()
      }
    })

    setDrafts((prev) => ({ ...prev, [activeConversation.id]: '' }))
    window.requestAnimationFrame(() => textareaRef.current?.focus())
    const assistantReply = buildAssistantReply(trimmed)
    startStreaming(activeConversation.id, assistantReply)
  }, [activeConversation, currentDraft, isStreaming, startStreaming, updateConversation])

  const handleSubmit = useCallback((event) => {
    event.preventDefault()
    handleSend()
  }, [handleSend])

  const handleComposerKeyDown = useCallback((event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }, [handleSend])

  const resetConversation = useCallback(() => {
    if (!activeConversation) return
    stopStreaming()
    updateConversation(activeConversation.id, (conversation) => ({
      ...conversation,
      messages: [createWelcomeMessage()],
      updatedAt: new Date().toISOString()
    }))
    setDrafts((prev) => ({ ...prev, [activeConversation.id]: '' }))
  }, [activeConversation, stopStreaming, updateConversation])

  const togglePause = useCallback(() => {
    if (!isStreaming) return
    setIsPaused((prev) => {
      const next = !prev
      isPausedRef.current = next
      return next
    })
  }, [isStreaming])

  const handleMarkdownAction = useCallback((event) => {
    const button = event.target.closest('.copy-code-btn')
    if (!button) return
    const encoded = button.getAttribute('data-code') || ''
    try {
      const text = decodeURIComponent(encoded)
      if (navigator?.clipboard) {
        navigator.clipboard.writeText(text)
      }
      setCopyToast('Code copied to clipboard')
    } catch {
      setCopyToast('Unable to copy code block')
    }
  }, [])

  const handleNewConversation = useCallback(() => {
    const conversation = createConversation()
    stopStreaming()
    applyConversationChange((prev) => [conversation, ...prev])
    setActiveConversationId(conversation.id)
    setDrafts((prev) => ({ ...prev, [conversation.id]: '' }))
    window.requestAnimationFrame(() => textareaRef.current?.focus())
  }, [applyConversationChange, stopStreaming])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [activeConversation?.messages])

  useEffect(() => {
    textareaRef.current?.focus()
  }, [activeConversationId])

  useEffect(() => {
    if (!copyToast) return
    const handle = window.setTimeout(() => setCopyToast(''), 2200)
    return () => window.clearTimeout(handle)
  }, [copyToast])

  useEffect(() => () => {
    clearStreamingTimer()
  }, [clearStreamingTimer])

  const filteredConversations = useMemo(() => {
    if (!searchTerm.trim()) return conversations
    const needle = searchTerm.trim().toLowerCase()
    return conversations.filter((conversation) => (
      conversation.title.toLowerCase().includes(needle) ||
      conversation.messages.some((message) => message.content.toLowerCase().includes(needle))
    ))
  }, [conversations, searchTerm])

  const groupedConversations = useMemo(() => {
    const groups = new Map()
    filteredConversations.forEach((conversation) => {
      const label = formatConversationDate(conversation.updatedAt)
      const bucket = groups.get(label) ?? []
      bucket.push(conversation)
      groups.set(label, bucket)
    })
    return Array.from(groups.entries())
  }, [filteredConversations])

  const artifacts = useMemo(() => extractArtifacts(activeConversation?.messages ?? []), [activeConversation?.messages])

  useEffect(() => {
    if (!artifacts.length) {
      setActiveArtifactId(null)
      return
    }
    if (!activeArtifactId || !artifacts.some((artifact) => artifact.id === activeArtifactId)) {
      setActiveArtifactId(artifacts[0].id)
    }
  }, [activeArtifactId, artifacts])

  const selectedArtifact = artifacts.find((artifact) => artifact.id === activeArtifactId)
  const showTypingIndicator = isStreaming && streamingConversationIdRef.current === activeConversation?.id
  const currentMessages = activeConversation?.messages ?? []

  return (
    <div className="app-shell">
      <div className="workspace">
        <aside className="sidebar" aria-label="Conversation history">
          <button type="button" className="btn btn-primary btn-new-chat" onClick={handleNewConversation}>
            + New conversation
          </button>
          <label className="search-field">
            <span className="sr-only">Search conversations</span>
            <input
              type="search"
              placeholder="Search conversations"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
            />
          </label>
          <div className="conversation-groups" role="presentation">
            {groupedConversations.map(([label, items]) => (
              <div key={label} className="conversation-group">
                <p className="conversation-group__label">{label}</p>
                <ul role="list">
                  {items.map((conversation) => {
                    const lastMessage = conversation.messages[conversation.messages.length - 1]
                    const isActive = conversation.id === activeConversation?.id
                    return (
                      <li key={conversation.id}>
                        <button
                          type="button"
                          className={`conversation-row ${isActive ? 'is-active' : ''}`}
                          onClick={() => handleConversationSelect(conversation.id)}
                          aria-pressed={isActive}
                        >
                          <div className="conversation-row__title">{conversation.title}</div>
                          <div className="conversation-row__meta">
                            <span>{formatConversationPreview(lastMessage?.content)}</span>
                            <span>{formatTimestamp(conversation.updatedAt)}</span>
                          </div>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </div>
            ))}
            {groupedConversations.length === 0 && (
              <div className="conversation-empty">
                <p>No conversations found. Try a different search.</p>
              </div>
            )}
          </div>
        </aside>
        <main className="main-pane">
          <div className="chat-container" aria-live="polite">
            <header className="chat-header">
              <div className="header-left">
                <h1 className="header-title">Claude workspace</h1>
                <p className="header-subtitle">Fast, focused writing &amp; building with streaming responses.</p>
              </div>
              <div className="header-right">
                <span className="status-pill" aria-live="polite">
                  <span className="status-dot" aria-hidden="true"></span>
                  Live · SSE mock
                </span>
                <div className="model-pill" role="group" aria-label="Active model">
                  <span>Claude Sonnet 4.5</span>
                  <span>200K context · default</span>
                </div>
              </div>
            </header>
            <section className="chat-body">
              <div
                className="chat-log"
                role="log"
                aria-live="polite"
                aria-label="Claude conversation history"
                onClick={handleMarkdownAction}
              >
                {currentMessages.length === 1 && currentMessages[0].role === 'assistant' && (
                  <div className="empty-state">
                    <strong>Start a conversation.</strong>
                    <p>Claude keeps context, artifacts, and instructions per thread.</p>
                    <div className="empty-prompts">
                      {SUGGESTED_PROMPTS.map((prompt) => (
                        <button
                          type="button"
                          key={prompt}
                          className="prompt-card"
                          onClick={() => handlePromptSelect(prompt)}
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {currentMessages.map((message) => (
                  <article
                    key={message.id}
                    className={`message-row message-row--${message.role === 'user' ? 'user' : 'assistant'}`}
                  >
                    <div className="message-avatar" aria-hidden="true">
                      {message.role === 'user' ? 'You' : 'C'}
                    </div>
                    <div className="message-body">
                      <div
                        className={`message-bubble message-bubble--${message.role === 'user' ? 'user' : 'assistant'}`}
                        dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
                      />
                      <span className="message-timestamp">
                        {message.streaming ? 'Streaming…' : formatTimestamp(message.createdAt)}
                      </span>
                    </div>
                  </article>
                ))}
                <div ref={chatEndRef} aria-hidden="true" />
              </div>

              {showTypingIndicator && (
                <div className="typing-indicator" role="status" aria-live="polite">
                  <span className="typing-indicator__dot" />
                  <span className="typing-indicator__dot" />
                  <span className="typing-indicator__dot" />
                  <span>Claude is responding {isPaused ? '(paused)' : '…'}</span>
                </div>
              )}

              <form className="composer" onSubmit={handleSubmit} aria-label="Message composer">
                <div className="input-wrapper">
                  <label htmlFor="chat-input" className="sr-only">Type a message for Claude</label>
                  <textarea
                    id="chat-input"
                    ref={textareaRef}
                    value={currentDraft}
                    onChange={(event) => handleDraftChange(event.target.value)}
                    placeholder="Ask Claude to research, plan, or build. Shift+Enter for newline."
                    rows={1}
                    onKeyDown={handleComposerKeyDown}
                    aria-label="Chat input"
                  />
                </div>
                <div className="input-footer">
                  <div className="composer-meta">
                    {currentDraft.trim().length > 0 && (
                      <span className={`counter ${hasCharLimitError ? 'counter--warning' : ''}`}>
                        {currentDraft.length} / {MAX_CHARACTERS} characters · ≈ {tokenEstimate} tokens
                      </span>
                    )}
                    <span className="counter">Enter to send · Shift+Enter for newline</span>
                    {hasCharLimitError && (
                      <span className="counter counter--warning">Please keep messages under {MAX_CHARACTERS} characters.</span>
                    )}
                    {copyToast && <span className="toast" role="status">{copyToast}</span>}
                  </div>
                  <div className="composer-actions">
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={resetConversation}
                      aria-label="Clear chat"
                    >
                      Clear chat
                    </button>
                    {isStreaming && (
                      <>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={togglePause}
                          aria-pressed={isPaused}
                        >
                          {isPaused ? 'Resume' : 'Pause'}
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={stopStreaming}
                          aria-label="Stop streaming"
                        >
                          Stop generating
                        </button>
                      </>
                    )}
                    <button
                      type="submit"
                      className="btn btn-primary"
                      disabled={currentDraft.trim().length === 0 || hasCharLimitError || isStreaming}
                    >
                      Send
                    </button>
                  </div>
                </div>
              </form>
            </section>
          </div>
        </main>
        <aside className="artifacts-pane" aria-label="Artifacts">
          <div className="artifact-header">
            <div>
              <p>Artifacts</p>
              <small>Claude surfaces structured outputs here.</small>
            </div>
            <span className="artifact-count">{artifacts.length}</span>
          </div>
          {artifacts.length === 0 ? (
            <div className="artifact-empty">
              <p>No artifacts yet</p>
              <span>Ask Claude to write code, plans, or outlines to see them here.</span>
            </div>
          ) : (
            <>
              <div className="artifact-tabs" role="tablist">
                {artifacts.map((artifact) => (
                  <button
                    key={artifact.id}
                    type="button"
                    className={`artifact-pill ${artifact.id === activeArtifactId ? 'is-active' : ''}`}
                    onClick={() => setActiveArtifactId(artifact.id)}
                    role="tab"
                    aria-selected={artifact.id === activeArtifactId}
                  >
                    {artifact.title}
                  </button>
                ))}
              </div>
              <div className="artifact-preview" role="tabpanel">
                <div className="artifact-meta">
                  <span>{selectedArtifact?.language ?? 'plaintext'}</span>
                  {selectedArtifact?.sourceMessageId && <span>Generated by Claude</span>}
                </div>
                <pre>
                  <code>{selectedArtifact?.content}</code>
                </pre>
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  )
}

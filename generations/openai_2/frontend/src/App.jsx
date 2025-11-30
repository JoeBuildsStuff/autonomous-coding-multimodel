import React, { useEffect, useRef, useState } from 'react'

export default function App(){
  const MAX_CHARS = 1000; // maximum characters allowed in the input
  const textAreaRef = useRef(null); // for manual height control
  const inputRef = useRef(null)
  const chatEndRef = useRef(null)
  const streamingInterval = useRef(null)

  const [messages, setMessages] = useState([
    { id: 1, from: 'bot', text: 'Welcome to Claude.ai Clone! Type something below to start a chat.' }
  ])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamText, setStreamText] = useState('')
  const [hasFocus, setHasFocus] = useState(false)
  const [isPaused, setIsPaused] = useState(false)

  // auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamText])

  // auto-resize
  useEffect(() => {
    const ta = textAreaRef.current
    if(!ta) return
    ta.style.height = 'auto'
    const max = 180
    ta.style.height = Math.min(ta.scrollHeight, max) + 'px'
  }, [input])

  // focus on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const sendMessage = () => {
    const trimmed = input.trim()
    if(!trimmed || isStreaming || input.length > MAX_CHARS) return
    const userMsg = { id: Date.now(), from: 'user', text: trimmed }
    setMessages(m => [...m, userMsg])
    setInput('')
    simulateStreaming("This is a streaming response simulated for testing.")
  };

  const onKeyDown = (e) => {
    if(e.key === 'Enter' && !e.shiftKey){
      e.preventDefault()
      sendMessage()
    }
  };

  const simulateStreaming = (fullText) => {
    setIsStreaming(true);
    setStreamText('');
    const words = fullText.split(' ');
    let i = 0;

    // ensure a bot message exists at the end
    setMessages(m => {
      const last = m[m.length-1]
      if(last && last.from === 'bot'){
        return m
      } else {
        return [...m, { id: Date.now(), from: 'bot', text: '' }]
      }
    })

    streamingInterval.current = setInterval(() => {
      if(i >= words.length){
        clearInterval(streamingInterval.current);
        setIsStreaming(false);
        // finalize
        setMessages(m => {
          const idx = m.length - 1;
          const last = m[idx];
          const final = (streamText && streamText.trim().length>0) ? streamText.trim() : (last ? last.text : '');
          const updated = m.slice(0, idx);
          updated.push({ id: last?.id ?? Date.now(), from: 'bot', text: final });
          return updated;
        });
        setStreamText('');
        return;
      }
      if(isPaused){
        // do not advance streaming while paused
        return;
      }
      const nextWord = words[i];
      const nextText = (streamText ? streamText + ' ' + nextWord : nextWord);
      setStreamText(nextText);
      setMessages(m => {
        const idx = m.length - 1;
        const last = m[idx];
        if(last && last.from === 'bot'){
          const updated = m.slice();
          updated[idx] = { id: last.id, from: 'bot', text: nextText };
          return updated;
        } else {
          return [...m, { id: Date.now(), from: 'bot', text: nextText }];
        }
      });
      i++;
    }, 260);
  };

  const stopStreaming = () => {
    if(!isStreaming) return;
    clearInterval(streamingInterval.current);
    setIsStreaming(false);
    setStreamText('');
    // Merge current streamed text into last bot message as final
    setMessages(m => {
      const idx = m.length - 1;
      const last = m[idx];
      const final = (streamText && streamText.trim().length>0) ? streamText.trim() : (last?.text ?? '');
      const updated = m.slice(0, idx);
      updated.push({ id: last?.id ?? Date.now(), from: 'bot', text: final });
      return updated;
    });
  };

  const renderMessage = (m) => {
    const align = m.from === 'user' ? 'right' : 'left';
    const bubbleBg = m.from === 'user' ? '#0b5ed7' : '#f4f4f4';
    const bubbleColor = m.from === 'user' ? '#fff' : '#111';
    return (
      <div key={m.id} style={{ textAlign: align, margin: '6px 0' }}>
        <span style={{ display:'inline-block', padding:'8px 12px', borderRadius:12, background: bubbleBg, color: bubbleColor, maxWidth:'70%', whiteSpace:'pre-wrap' }}>
          {m.text}
        </span>
      </div>
    )
  };

  const charCount = input.length;

  return (
    <div style={{padding:20, fontFamily:'Inter, system-ui', height:'100vh', display:'flex', flexDirection:'column', background:'#f7f7f7'}}>
      <div style={{textAlign:'center', marginBottom:12}}>
        <h1 style={{margin:0}}>Claude.ai Clone - Frontend Placeholder (Interactive Demo)</h1>
        <p style={{margin:0, color:'#666'}}>A minimal, self-contained chat UI with simulated streaming.</p>
      </div>
      <div style={{flex:1, display:'flex', flexDirection:'column', maxWidth:800, margin:'0 auto', background:'#fff', borderRadius:12, padding:12, boxShadow:'0 2px 12px rgba(0,0,0,0.08)'}}>
        <div style={{flex:1, overflowY:'auto', padding:12, border:'1px solid #eee', borderRadius:8, minHeight:240}}>
          {messages.map((m) => renderMessage(m))}
          <div ref={chatEndRef} />
        </div>
        <div style={{ marginTop:12, display:'flex', alignItems:'center', gap:8 }}>
          <textarea
            ref={(node)=>{ inputRef.current = node; textAreaRef.current = node; }} id="chat-input"
            value={input}
            onChange={(e)=>setInput(e.target.value)}
            onKeyDown={onKeyDown}
            onFocus={()=>setHasFocus(true)}
            onBlur={()=>setHasFocus(false)}
            placeholder={`Type a message... (Shift+Enter for newline) [0/${MAX_CHARS}]`}
            rows={2}
            style={{ flex:1, resize:'none', padding:10, borderRadius:8, border:'1px solid #ddd', fontFamily:'inherit' }}
          />
          <button onClick={sendMessage} style={{ padding:'12px 16px', borderRadius:8, border:'none', background:'#0b5ed7', color:'#fff', fontWeight:600, cursor:'pointer' }} disabled={input.trim().length===0 || isStreaming || input.length>MAX_CHARS}>
            Send
          </button>
          {/* Pause/Resume toggle for streaming */}
          {isStreaming && (
            <button
              id="pause-btn" onClick={() => setIsPaused(p => !p)}
              style={{ padding:'12px 16px', borderRadius:8, border:'1px solid #999', background:'#fff', color:'#333', fontWeight:600, cursor:'pointer' }}
              aria-label={isPaused ? "Resume streaming" : "Pause streaming"}
            >
              {isPaused ? 'Resume' : 'Pause'}
            </button>
          )}
          {/* Clear chat button to reset UI state and messages */}
          <button
            onClick={() => {
              // Stop any ongoing streaming first
              if (isStreaming) {
                stopStreaming()
              }
              // Reset messages to initial welcome state
              setMessages([
                { id: 1, from: 'bot', text: 'Welcome to Claude.ai Clone! Type something below to start a chat.' }
              ])
              setInput('')
              setStreamText('')
              setIsPaused(false)
            }}
            style={{ padding:'12px 16px', borderRadius:8, border:'1px solid #ccc', background:'#fff', color:'#333', fontWeight:600, cursor:'pointer' }}
            aria-label="Clear chat"
          >
            Clear chat
          </button>
          {isStreaming && (
            <button onClick={stopStreaming} style={{ padding:'12px 16px', borderRadius:8, border:'1px solid #999', background:'#fff', color:'#333', fontWeight:600, cursor:'pointer' }} aria-label="Stop streaming">
              Stop
            </button>
          )}
        </div>
        {isStreaming && (
          <div style={{ marginTop:8, color:'#555', display:'flex', alignItems:'center', gap:8 }}>
            <span className="dot" style={{ width:8, height:8, borderRadius:4, background:'#888', display:'inline-block', animation:'blink 1s infinite' }}></span>
            <span>Claude is typing{streamText ? ': ' + streamText : ''}{isPaused ? ' (paused)' : ''}</span>
          </div>
        )}
        <div style={{ alignSelf:'flex-end', marginTop:8, fontSize:12, color:'#555' }}>
          {input.trim().length > 0 && (
            <>
              Characters: {charCount} / {MAX_CHARS}  -  Est. tokens: {Math.ceil(charCount / 4)}
            </>
          )}
        </div>
      </div>
      <style>{`@keyframes blink { 0% { opacity: 0.2 } 50% { opacity: 1 } 100% { opacity: 0.2 } }`}</style>
    </div>
  )
}

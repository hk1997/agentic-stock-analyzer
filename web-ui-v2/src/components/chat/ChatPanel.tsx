import { useState, useRef, useEffect, type FormEvent } from 'react'
import { Send, Bot, User } from 'lucide-react'
import type { ChatMessage } from '../../types/api'

interface ChatPanelProps {
    messages: ChatMessage[]
    isStreaming: boolean
    onSend: (message: string) => void
}

export function ChatPanel({ messages, isStreaming, onSend }: ChatPanelProps) {
    const [input, setInput] = useState('')
    const messagesEndRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    const handleSubmit = (e: FormEvent) => {
        e.preventDefault()
        const trimmed = input.trim()
        if (!trimmed || isStreaming) return
        onSend(trimmed)
        setInput('')
    }

    return (
        <section className="chat-panel glass-panel">
            <div className="chat-panel__header">
                <div className="chat-panel__header-dot" />
                Agentic Chat
            </div>

            <div className="chat-messages">
                {messages.length === 0 && (
                    <div className="message message--agent">
                        <div className="message__avatar message__avatar--agent">
                            <Bot size={14} />
                        </div>
                        <div className="message__bubble">
                            Hello! I&apos;m your AI Stock Analyst. Ask me anything — try <em>&quot;Analyze AAPL&quot;</em>.
                        </div>
                    </div>
                )}

                {messages.map((msg) => {
                    if (msg.role === 'step') {
                        return (
                            <div key={msg.id} className="agent-step">
                                <div className="agent-step__spinner" />
                                {msg.agentName || 'Agent'} is analyzing...
                            </div>
                        )
                    }

                    return (
                        <div key={msg.id} className={`message message--${msg.role}`}>
                            <div className={`message__avatar message__avatar--${msg.role}`}>
                                {msg.role === 'agent' ? <Bot size={14} /> : <User size={14} />}
                            </div>
                            <div className="message__bubble">{msg.content}</div>
                        </div>
                    )
                })}

                {isStreaming && messages[messages.length - 1]?.role !== 'step' && (
                    <div className="agent-step">
                        <div className="agent-step__spinner" />
                        Processing...
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            <form className="chat-input" onSubmit={handleSubmit}>
                <input
                    className="chat-input__field"
                    type="text"
                    placeholder={isStreaming ? 'Agents are working...' : 'Ask about any stock...'}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    disabled={isStreaming}
                />
                <button className="chat-input__btn" type="submit" disabled={isStreaming || !input.trim()}>
                    <Send size={18} />
                </button>
            </form>
        </section>
    )
}

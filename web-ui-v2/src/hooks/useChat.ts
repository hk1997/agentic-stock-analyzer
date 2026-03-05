import React, { useState, useCallback, useRef } from 'react'
import type { ChatMessage, AgentStartPayload, AgentOutputPayload, ErrorPayload } from '../types/api'
import { v4 as uuidv4 } from 'uuid';

let messageId = 0
function nextId(): string {
    return `msg-${++messageId}-${Date.now()}`
}

export function useChat() {
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const [isStreaming, setIsStreaming] = useState(false)
    const [detectedTicker, setDetectedTicker] = useState<string | null>(null)
    const abortRef = useRef<AbortController | null>(null)

    const sendMessage = useCallback(async (text: string) => {
        // Add user message
        const userMsg: ChatMessage = {
            id: nextId(),
            role: 'user',
            content: text,
            timestamp: new Date(),
        }
        setMessages((prev: ChatMessage[]) => [...prev, userMsg])
        setIsStreaming(true)

        // Generate or retrieve a unqiue thread ID for this browser session
        let threadId = sessionStorage.getItem('finance_chat_thread_id')
        if (!threadId) {
            threadId = uuidv4()
            sessionStorage.setItem('finance_chat_thread_id', threadId)
        }

        try {
            abortRef.current = new AbortController()
            const response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, thread_id: threadId }),
                signal: abortRef.current.signal,
            })

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`)
            }

            const reader = response.body?.getReader()
            const decoder = new TextDecoder()
            let buffer = ''

            if (!reader) throw new Error('No response body')

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n')
                buffer = lines.pop() || ''

                for (const line of lines) {
                    if (line.startsWith('event: ')) {
                        const eventType = line.slice(7).trim()
                        // Next line should be data:
                        continue
                    }

                    if (line.startsWith('data: ')) {
                        const dataStr = line.slice(6).trim()
                        if (!dataStr) continue

                        try {
                            const parsed = JSON.parse(dataStr)

                            // Check the event type from the SSE format
                            if (parsed.node && !parsed.content) {
                                // agent_start
                                const payload = parsed as AgentStartPayload
                                setMessages((prev: ChatMessage[]) => [
                                    ...prev,
                                    {
                                        id: nextId(),
                                        role: 'step',
                                        content: `${payload.node} is analyzing...`,
                                        agentName: payload.node,
                                        timestamp: new Date(),
                                    },
                                ])
                            } else if (parsed.content) {
                                // We handle both agent_output and agent_output_chunk
                                // Note: SSE parsing might send `eventType` as custom but our current hack parses raw chunk. 
                                // To make this simple, if we get content, we will treat it as a streaming chunk 
                                // and either start an "agent" message or append to the existing one.

                                const payload = parsed as AgentOutputPayload

                                // Ensure content is a string
                                let contentString = typeof payload.content === 'string' ? payload.content : ''

                                if (typeof payload.content === 'object' && payload.content !== null) {
                                    if ('text' in payload.content && typeof (payload.content as any).text === 'string') {
                                        contentString = (payload.content as any).text
                                    } else {
                                        contentString = JSON.stringify(payload.content)
                                    }
                                }

                                setMessages((prev: ChatMessage[]) => {
                                    const prevMsgs = [...prev]

                                    // 1. Find if we already have an "agent" message for this node in the current turn
                                    // We'll look backwards for an agent message from this node that isn't a step.
                                    let activeMsgIndex = -1;
                                    for (let i = prevMsgs.length - 1; i >= 0; i--) {
                                        if (prevMsgs[i].role === 'user') break; // stop at last user message boundary
                                        if (prevMsgs[i].role === 'agent' && prevMsgs[i].agentName === payload.node) {
                                            activeMsgIndex = i;
                                            break;
                                        }
                                    }

                                    if (activeMsgIndex >= 0) {
                                        // Append to existing agent message
                                        prevMsgs[activeMsgIndex] = {
                                            ...prevMsgs[activeMsgIndex],
                                            content: prevMsgs[activeMsgIndex].content + contentString
                                        }
                                    } else {
                                        // Create a new agent message and remove any leftover 'step' loading messages
                                        const filtered = prevMsgs.filter(
                                            (m: ChatMessage) => !(m.role === 'step' && m.agentName === payload.node)
                                        )
                                        return [
                                            ...filtered,
                                            {
                                                id: nextId(),
                                                role: 'agent',
                                                content: contentString,
                                                agentName: payload.node,
                                                timestamp: new Date(),
                                            },
                                        ]
                                    }

                                    return prevMsgs
                                })
                            } else if (parsed.message) {
                                // error
                                const payload = parsed as ErrorPayload
                                setMessages((prev: ChatMessage[]) => [
                                    ...prev,
                                    {
                                        id: nextId(),
                                        role: 'agent',
                                        content: `⚠️ Error: ${payload.message}`,
                                        timestamp: new Date(),
                                    },
                                ])
                            }
                            // finish event — just stop streaming
                        } catch {
                            // ignore parse errors for incomplete chunks
                        }
                    }
                }
            }
        } catch (err) {
            if ((err as Error).name !== 'AbortError') {
                setMessages((prev: ChatMessage[]) => [
                    ...prev,
                    {
                        id: nextId(),
                        role: 'agent',
                        content: `⚠️ Connection error: ${(err as Error).message}`,
                        timestamp: new Date(),
                    },
                ])
            }
        } finally {
            setIsStreaming(false)
            abortRef.current = null
        }
    }, [])

    const cancel = useCallback(() => {
        abortRef.current?.abort()
    }, [])

    return { messages, isStreaming, sendMessage, cancel }
}

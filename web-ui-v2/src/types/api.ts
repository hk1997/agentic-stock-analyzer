/** TypeScript interfaces for API responses */

export interface StockData {
    ticker: string
    name: string
    price: number
    change: number
    changePct: number
    volume: number
    marketCap: number | null
    peRatio: number | null
    fiftyTwoWeekHigh: number | null
    fiftyTwoWeekLow: number | null
    sector: string | null
    industry: string | null
    history: PricePoint[]
    error?: string
}

export interface PricePoint {
    time: string
    open: number
    high: number
    low: number
    close: number
    volume: number
}

export interface ChatEvent {
    event: 'agent_start' | 'agent_output' | 'error' | 'finish'
    data: string // JSON-encoded payload
}

export interface AgentStartPayload {
    node: string
}

export interface AgentOutputPayload {
    node: string
    content: string
}

export interface ErrorPayload {
    message: string
}

export interface FinishPayload {
    summary: string
}

export type ChatMessage = {
    id: string
    role: 'user' | 'agent' | 'step'
    content: string
    agentName?: string
    timestamp: Date
}

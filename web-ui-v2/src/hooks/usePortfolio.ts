import { useState, useEffect, useCallback } from 'react'

const API = '/api/portfolio'

export interface Holding {
    id: number
    ticker: string
    name: string
    sector: string
    shares: number
    avg_cost_basis: number
    current_price: number
    current_value: number
    cost_basis_total: number
    unrealized_pnl: number
    unrealized_pnl_pct: number
    weight_pct: number
}

export interface PortfolioData {
    id: number
    name: string
    total_value: number
    total_cost: number
    total_pnl: number
    total_pnl_pct: number
    num_holdings: number
    holdings: Holding[]
}

export function usePortfolio() {
    const [portfolioId, setPortfolioId] = useState<number | null>(null)
    const [portfolio, setPortfolio] = useState<PortfolioData | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    // 1. On mount: list portfolios and get the first one's ID
    useEffect(() => {
        fetch(API)
            .then(r => r.json())
            .then((list: { id: number }[]) => {
                if (list.length > 0) setPortfolioId(list[0].id)
            })
            .catch(e => setError(e.message))
    }, [])

    // 2. Fetch full portfolio whenever portfolioId changes
    const refresh = useCallback(() => {
        if (!portfolioId) return
        setLoading(true)
        setError(null)
        fetch(`${API}/${portfolioId}`)
            .then(r => r.json())
            .then((data: PortfolioData) => {
                if ((data as any).error) {
                    setError((data as any).error)
                } else {
                    setPortfolio(data)
                }
            })
            .catch(e => setError(e.message))
            .finally(() => setLoading(false))
    }, [portfolioId])

    useEffect(() => { refresh() }, [refresh])

    // 3. CRUD operations
    const addHolding = async (ticker: string, shares: number, avgCostBasis: number) => {
        if (!portfolioId) return
        await fetch(`${API}/${portfolioId}/holdings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker, shares, avg_cost_basis: avgCostBasis }),
        })
        refresh()
    }

    const updateHolding = async (holdingId: number, ticker: string, shares: number, avgCostBasis: number) => {
        if (!portfolioId) return
        await fetch(`${API}/${portfolioId}/holdings/${holdingId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker, shares, avg_cost_basis: avgCostBasis }),
        })
        refresh()
    }

    const removeHolding = async (holdingId: number) => {
        if (!portfolioId) return
        await fetch(`${API}/${portfolioId}/holdings/${holdingId}`, { method: 'DELETE' })
        refresh()
    }

    const importCsv = async (file: File) => {
        if (!portfolioId) return null
        const formData = new FormData()
        formData.append('file', file)
        const res = await fetch(`${API}/${portfolioId}/import/csv`, {
            method: 'POST',
            body: formData,
        })
        if (!res.ok) {
            const text = await res.text()
            return { error: text || `Server error (${res.status})` }
        }
        const data = await res.json()
        if (!data.error) refresh()
        return data
    }

    return { portfolio, loading, error, addHolding, updateHolding, removeHolding, importCsv, refresh }
}

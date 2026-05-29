import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../utils/api'

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
    id: number | 'unified'
    name: string
    total_value: number
    total_cost: number
    total_pnl: number
    total_pnl_pct: number
    num_holdings: number
    holdings: Holding[]
    currency?: string
    last_updated?: string
    account_id?: number | null
    account_name?: string | null
}

export function usePortfolio() {
    const [viewMode, setViewMode] = useState<'personal' | 'unified'>('personal')
    const [portfoliosList, setPortfoliosList] = useState<any[]>([])
    const [selectedPortfolioId, setSelectedPortfolioId] = useState<number | null>(null)
    const [portfolio, setPortfolio] = useState<PortfolioData | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [accounts, setAccounts] = useState<any[]>([])

    const [realizedData, setRealizedData] = useState<any>(null)
    const [realizedLoading, setRealizedLoading] = useState(false)
    const [benchmarkData, setBenchmarkData] = useState<any>(null)
    const [benchmarkLoading, setBenchmarkLoading] = useState(false)

    // Load initial list and accounts
    const loadInitialData = useCallback(async () => {
        try {
            const accountsData = await apiFetch('/api/finance/accounts').catch(() => [])
            const portAccounts = accountsData.filter((a: any) => a.account_class === 'portfolio')
            setAccounts(portAccounts)

            if (viewMode === 'personal') {
                const list = await apiFetch('/api/portfolio')
                setPortfoliosList(list)
                if (list.length > 0) {
                    setSelectedPortfolioId((prev) => {
                        if (prev && list.some((p: any) => p.id === prev)) return prev
                        return list[0].id
                    })
                } else {
                    setPortfolio(null)
                }
            }
        } catch (e: any) {
            setError(e.message)
        }
    }, [viewMode])

    useEffect(() => {
        loadInitialData()
    }, [loadInitialData])

    // Load portfolio details
    const refresh = useCallback(async () => {
        if (viewMode === 'unified') {
            setLoading(true)
            setError(null)
            try {
                const data = await apiFetch('/api/finance/unified-portfolio')
                setPortfolio({
                    id: 'unified',
                    name: 'Unified Portfolio',
                    total_value: data.total_value,
                    total_cost: data.total_cost,
                    total_pnl: data.total_pnl,
                    total_pnl_pct: data.total_cost > 0 ? (data.total_pnl / data.total_cost) * 100 : 0,
                    num_holdings: data.holdings.length,
                    holdings: data.holdings,
                })
            } catch (e: any) {
                setError(e.message)
            } finally {
                setLoading(false)
            }
        } else if (selectedPortfolioId) {
            setLoading(true)
            setError(null)
            try {
                const data = await apiFetch(`/api/portfolio/${selectedPortfolioId}`)
                if (data.error) {
                    setError(data.error)
                } else {
                    setPortfolio(data)
                }
            } catch (e: any) {
                setError(e.message)
            } finally {
                setLoading(false)
            }
        } else {
            setPortfolio(null)
            setLoading(false)
        }
    }, [viewMode, selectedPortfolioId])

    useEffect(() => {
        refresh()
    }, [refresh])

    // Fetch realized data
    const fetchRealized = useCallback(async () => {
        const pid = portfolio?.id
        if (!pid || pid === 'unified') return
        setRealizedLoading(true)
        try {
            const data = await apiFetch(`/api/portfolio/${pid}/realized`)
            setRealizedData(data)
        } catch (e: any) {
            console.error(e)
        } finally {
            setRealizedLoading(false)
        }
    }, [portfolio?.id])

    // Fetch benchmark data
    const fetchBenchmarks = useCallback(async () => {
        const pid = portfolio?.id
        if (!pid || pid === 'unified') return
        setBenchmarkLoading(true)
        try {
            const data = await apiFetch(`/api/portfolio/${pid}/benchmarks`)
            if (!data.error) setBenchmarkData(data)
        } catch (e: any) {
            console.error(e)
        } finally {
            setBenchmarkLoading(false)
        }
    }, [portfolio?.id])

    // CRUD operations
    const createPortfolio = async (name: string) => {
        const newPort = await apiFetch('/api/portfolio', {
            method: 'POST',
            body: JSON.stringify({ name }),
        })
        const list = await apiFetch('/api/portfolio')
        setPortfoliosList(list)
        setSelectedPortfolioId(newPort.id)
        setViewMode('personal')
        return newPort
    }

    const linkPortfolioToAccount = async (portfolioId: number, accountId: number) => {
        await apiFetch(`/api/portfolio/${portfolioId}`, {
            method: 'PATCH',
            body: JSON.stringify({ account_id: accountId }),
        })
        loadInitialData()
        refresh()
    }

    const unlinkPortfolioFromAccount = async (portfolioId: number) => {
        await apiFetch(`/api/portfolio/${portfolioId}`, {
            method: 'PATCH',
            body: JSON.stringify({ account_id: -1 }),
        })
        loadInitialData()
        refresh()
    }

    const addHolding = async (ticker: string, shares: number, avgCostBasis: number) => {
        if (viewMode === 'unified' || !selectedPortfolioId) return
        await apiFetch(`/api/portfolio/${selectedPortfolioId}/holdings`, {
            method: 'POST',
            body: JSON.stringify({ ticker, shares, avg_cost_basis: avgCostBasis }),
        })
        refresh()
    }

    const updateHolding = async (holdingId: number, ticker: string, shares: number, avgCostBasis: number) => {
        if (viewMode === 'unified' || !selectedPortfolioId) return
        await apiFetch(`/api/portfolio/${selectedPortfolioId}/holdings/${holdingId}`, {
            method: 'PUT',
            body: JSON.stringify({ ticker, shares, avg_cost_basis: avgCostBasis }),
        })
        refresh()
    }

    const removeHolding = async (holdingId: number) => {
        if (viewMode === 'unified' || !selectedPortfolioId) return
        await apiFetch(`/api/portfolio/${selectedPortfolioId}/holdings/${holdingId}`, { method: 'DELETE' })
        refresh()
    }

    const importCsv = async (file: File) => {
        if (viewMode === 'unified' || !selectedPortfolioId) return null
        const formData = new FormData()
        formData.append('file', file)
        try {
            const data = await apiFetch(`/api/portfolio/${selectedPortfolioId}/import/csv`, {
                method: 'POST',
                body: formData,
            })
            if (!data.error) refresh()
            return data
        } catch (e: any) {
            return { error: e.message || 'Server error' }
        }
    }

    // Reset realized/benchmark when active portfolio changes
    useEffect(() => {
        setRealizedData(null)
        setBenchmarkData(null)
    }, [selectedPortfolioId, viewMode])

    return {
        viewMode,
        setViewMode,
        portfolio,
        loading,
        error,
        portfoliosList,
        selectedPortfolioId,
        setSelectedPortfolioId,
        accounts,
        realizedData,
        realizedLoading,
        benchmarkData,
        benchmarkLoading,
        addHolding,
        updateHolding,
        removeHolding,
        importCsv,
        createPortfolio,
        linkPortfolioToAccount,
        unlinkPortfolioFromAccount,
        fetchRealized,
        fetchBenchmarks,
        refresh
    }
}

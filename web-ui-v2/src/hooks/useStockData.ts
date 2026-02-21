import { useState, useEffect } from 'react'
import type { StockData } from '../types/api'

export function useStockData(ticker: string | null) {
    const [data, setData] = useState<StockData | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (!ticker) return

        let cancelled = false
        setLoading(true)
        setError(null)

        fetch(`/api/stock/${ticker}?period=6mo`)
            .then((res) => res.json())
            .then((json: StockData) => {
                if (cancelled) return
                if (json.error) {
                    setError(json.error)
                } else {
                    setData(json)
                }
            })
            .catch((err) => {
                if (!cancelled) setError(err.message)
            })
            .finally(() => {
                if (!cancelled) setLoading(false)
            })

        return () => { cancelled = true }
    }, [ticker])

    return { data, loading, error }
}

import { useState, useEffect } from 'react'
import type { StockData } from '../types/api'

export function useStockData(ticker: string | null, period: string = '1mo') {
    const [data, setData] = useState<StockData | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (!ticker) return

        let cancelled = false
        setLoading(true)
        setError(null)

        fetch(`/api/stock/${ticker}?period=${period}`)
            .then((res) => res.json())
            .then((json: StockData) => {
                if (cancelled) return
                if (json.error) {
                    setError(json.error)
                } else {
                    // Dynamically calculate the period return instead of relying on the backend's static daily return
                    if (json.history && json.history.length > 0) {
                        const startPrice = json.history[0].open || json.history[0].close;
                        const endPrice = json.history[json.history.length - 1].close;

                        json.change = Number((endPrice - startPrice).toFixed(2));
                        json.changePct = Number(((json.change / startPrice) * 100).toFixed(2));
                    }
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
    }, [ticker, period])

    return { data, loading, error }
}

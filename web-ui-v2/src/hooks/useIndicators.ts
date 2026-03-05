import { useState, useEffect } from 'react';

export interface IndicatorPoint {
    time: string;
    sma20: number | null;
    sma50: number | null;
    sma200: number | null;
    ema20: number | null;
    upper_band: number | null;
    lower_band: number | null;
    rsi: number | null;
    macd: number | null;
    macd_signal: number | null;
    macd_hist: number | null;
}

export function useIndicators(ticker: string | null, period: string = '1y') {
    const [indicators, setIndicators] = useState<IndicatorPoint[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!ticker) return;

        let cancelled = false;
        setLoading(true);

        fetch(`/api/indicators/${ticker}?period=${period}`)
            .then((res) => res.json())
            .then((json: { ticker: string, indicators: IndicatorPoint[] }) => {
                if (cancelled) return;
                if (json.indicators) {
                    setIndicators(json.indicators);
                }
            })
            .catch((err) => {
                console.error('Failed to fetch indicators', err);
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => { cancelled = true; };
    }, [ticker, period]);

    return { indicators, loading };
}

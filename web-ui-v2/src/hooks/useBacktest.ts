import { useState } from 'react';

export interface Trade {
    date: string;
    type: 'BUY' | 'SELL';
    price: number;
    shares: number;
}

export interface BacktestResult {
    strategy: string;
    ticker: string;
    period_days: number;
    initial_capital: number;
    final_value: number;
    total_return_pct: number;
    benchmark_return_pct: number;
    win_rate_pct: number;
    total_trades: number;
    final_position_shares: number;
    trades: Trade[];
}

export interface BacktestRequest {
    ticker: string;
    strategy: string;
    initial_capital: number;
    days: number;
}

export function useBacktest() {
    const [result, setResult] = useState<BacktestResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const runBacktest = async (params: BacktestRequest) => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch('http://localhost:8000/api/backtest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params),
            });
            const data = await response.json();
            if (data.error) {
                setError(data.error);
                setResult(null);
            } else {
                setResult({
                    strategy: data.strategy,
                    trades: data.trades || [],
                    ...(data.metrics || {})
                });
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
            setResult(null);
        } finally {
            setLoading(false);
        }
    };

    const clearBacktest = () => {
        setResult(null);
        setError(null);
    };

    return { result, loading, error, runBacktest, clearBacktest };
}

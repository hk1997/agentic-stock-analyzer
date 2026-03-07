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
    stop_loss_pct: number;
    final_value: number;
    total_return_pct: number;
    benchmark_return_pct: number;
    win_rate_pct: number;
    max_drawdown_pct: number;
    total_trades: number;
    final_position_shares: number;
    trades: Trade[];
    equity_curve: {
        date: string;
        equity: number;
        drawdown_pct: number;
    }[];
    error?: string;
}

export interface BacktestRequest {
    ticker: string;
    strategies: string[];
    initial_capital: number;
    days: number;
    stop_loss_pct: number;
}

export function useBacktest() {
    const [results, setResults] = useState<BacktestResult[] | null>(null);
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
                setResults(null);
            } else {
                // If the backend returns an array of objects
                setResults(Array.isArray(data) ? data : [data]);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
            setResults(null);
        } finally {
            setLoading(false);
        }
    };

    const clearBacktest = () => {
        setResults(null);
        setError(null);
    };

    return { results, loading, error, runBacktest, clearBacktest };
}

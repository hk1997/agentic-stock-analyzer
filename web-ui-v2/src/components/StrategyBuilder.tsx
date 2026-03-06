import React, { useState } from 'react';
import { Play, RotateCcw, TrendingUp, AlertTriangle } from 'lucide-react';
import { useBacktest, BacktestRequest } from '../hooks/useBacktest';
import type { BacktestResult } from '../hooks/useBacktest';

interface StrategyBuilderProps {
    ticker: string;
    onResult: (result: BacktestResult | null) => void;
}

const STRATEGIES = [
    { id: 'sma_crossover', name: 'SMA Crossover' },
    { id: 'rsi_mean_reversion', name: 'RSI Mean Reversion' },
    { id: 'macd_crossover', name: 'MACD Crossover' },
    { id: 'bollinger_reversion', name: 'Bollinger Band Reversion' },
];

export function StrategyBuilder({ ticker, onResult }: StrategyBuilderProps) {
    const { result, loading, error, runBacktest, clearBacktest } = useBacktest();

    const [strategy, setStrategy] = useState(STRATEGIES[0].id);
    const [capital, setCapital] = useState<number>(10000);
    const [days, setDays] = useState<number>(365);

    const handleRun = async () => {
        const req: BacktestRequest = { ticker, strategy, initial_capital: capital, days };
        await runBacktest(req);
    };

    // Pass up to parent whenever result changes so StockChart can plot markers
    React.useEffect(() => {
        onResult(result);
    }, [result, onResult]);

    const handleClear = () => {
        clearBacktest();
        onResult(null);
    };

    return (
        <section className="chart-card glass-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '400px' }}>
            <div className="chart-card__header" style={{ marginBottom: '16px' }}>
                <h3 style={{ margin: 0, fontSize: '16px', color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <TrendingUp size={18} color="#3b82f6" />
                    Strategy Simulation
                </h3>
                <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: '#a0a5b9' }}>Backtest algorithms on {ticker}</p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', flex: 1, overflowY: 'auto', paddingRight: '4px' }}>
                {/* Controls */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', background: 'rgba(20, 25, 40, 0.4)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <label style={{ fontSize: '12px', color: '#a0a5b9' }}>Strategy</label>
                        <select
                            value={strategy}
                            onChange={(e) => setStrategy(e.target.value)}
                            style={{ background: '#1c2132', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', padding: '8px', borderRadius: '6px', fontSize: '13px', outline: 'none' }}
                        >
                            {STRATEGIES.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                        </select>
                    </div>

                    <div style={{ display: 'flex', gap: '12px' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
                            <label style={{ fontSize: '12px', color: '#a0a5b9' }}>Initial Capital ($)</label>
                            <input
                                type="number"
                                value={capital}
                                onChange={(e) => setCapital(Number(e.target.value))}
                                style={{ background: '#1c2132', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', padding: '8px', borderRadius: '6px', fontSize: '13px', outline: 'none', width: '100%' }}
                            />
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
                            <label style={{ fontSize: '12px', color: '#a0a5b9' }}>Period (Days)</label>
                            <input
                                type="number"
                                value={days}
                                onChange={(e) => setDays(Number(e.target.value))}
                                style={{ background: '#1c2132', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', padding: '8px', borderRadius: '6px', fontSize: '13px', outline: 'none', width: '100%' }}
                            />
                        </div>
                    </div>

                    <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                        <button
                            onClick={handleRun}
                            disabled={loading}
                            style={{ flex: 1, background: '#3b82f6', color: '#fff', border: 'none', padding: '10px', borderRadius: '6px', fontSize: '13px', fontWeight: '600', cursor: loading ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', opacity: loading ? 0.7 : 1, transition: '0.2s' }}
                        >
                            {loading ? <div className="loading-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> : <Play size={14} />}
                            {loading ? 'Running...' : 'Run Backtest'}
                        </button>

                        {result && (
                            <button
                                onClick={handleClear}
                                style={{ background: 'rgba(255,255,255,0.1)', color: '#fff', border: 'none', padding: '10px', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                                title="Clear Results"
                            >
                                <RotateCcw size={16} />
                            </button>
                        )}
                    </div>
                </div>

                {/* Error */}
                {error && (
                    <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '12px', borderRadius: '8px', display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                        <AlertTriangle size={16} color="#ef4444" style={{ marginTop: 2 }} />
                        <p style={{ margin: 0, fontSize: '13px', color: '#ef4444' }}>{error}</p>
                    </div>
                )}

                {/* Results Section */}
                {result && !error && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                            <div style={{ background: 'rgba(20, 25, 40, 0.6)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                                <div style={{ fontSize: '11px', color: '#a0a5b9', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Return</div>
                                <div style={{ fontSize: '20px', fontWeight: 'bold', color: (result?.total_return_pct ?? 0) >= 0 ? '#00e676' : '#ff1744', marginTop: '4px' }}>
                                    {(result?.total_return_pct ?? 0) >= 0 ? '+' : ''}{(result?.total_return_pct ?? 0).toFixed(2)}%
                                </div>
                                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>vs Buy & Hold: {(result?.benchmark_return_pct ?? 0).toFixed(2)}%</div>
                            </div>

                            <div style={{ background: 'rgba(20, 25, 40, 0.6)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                                <div style={{ fontSize: '11px', color: '#a0a5b9', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Win Rate</div>
                                <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#fff', marginTop: '4px' }}>
                                    {(result?.win_rate_pct ?? 0).toFixed(1)}%
                                </div>
                                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>{result?.total_trades ?? 0} total trades</div>
                            </div>

                            <div style={{ background: 'rgba(20, 25, 40, 0.6)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', gridColumn: 'span 2' }}>
                                <div style={{ fontSize: '11px', color: '#a0a5b9', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Final Equity</div>
                                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#fff', marginTop: '4px' }}>
                                    ${(result?.final_value ?? capital).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </div>
                                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>Starting: ${(result?.initial_capital ?? capital).toLocaleString()}</div>
                            </div>
                        </div>

                        {/* Trade History */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <h4 style={{ margin: 0, fontSize: '14px', color: '#fff' }}>Trade History</h4>
                            {result.trades.length === 0 ? (
                                <p style={{ margin: 0, fontSize: '13px', color: '#a0a5b9', fontStyle: 'italic' }}>No trades executed during this period.</p>
                            ) : (
                                <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '8px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.05)' }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                                        <thead>
                                            <tr style={{ background: 'rgba(255,255,255,0.05)', textAlign: 'left' }}>
                                                <th style={{ padding: '8px', color: '#a0a5b9', fontWeight: 'normal', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>Date</th>
                                                <th style={{ padding: '8px', color: '#a0a5b9', fontWeight: 'normal', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>Type</th>
                                                <th style={{ padding: '8px', color: '#a0a5b9', fontWeight: 'normal', borderBottom: '1px solid rgba(255,255,255,0.05)', textAlign: 'right' }}>Price</th>
                                                <th style={{ padding: '8px', color: '#a0a5b9', fontWeight: 'normal', borderBottom: '1px solid rgba(255,255,255,0.05)', textAlign: 'right' }}>Shares</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {(result?.trades || []).slice().reverse().map((t, i) => (
                                                <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                                                    <td style={{ padding: '8px', color: '#fff' }}>{t.date}</td>
                                                    <td style={{ padding: '8px', color: t.type === 'BUY' ? '#00e676' : '#ff1744', fontWeight: 'bold' }}>{t.type}</td>
                                                    <td style={{ padding: '8px', color: '#fff', textAlign: 'right' }}>${(t.price || 0).toFixed(2)}</td>
                                                    <td style={{ padding: '8px', color: '#fff', textAlign: 'right' }}>{t.shares || 0}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </section>
    );
}

import React, { useState, useEffect, useRef } from 'react';
import { Play, RotateCcw, TrendingUp, AlertTriangle } from 'lucide-react';
import { createChart, ColorType, LineSeries, AreaSeries } from 'lightweight-charts';
import { useBacktest, BacktestRequest } from '../hooks/useBacktest';
import type { BacktestResult } from '../hooks/useBacktest';

interface StrategyBuilderProps {
    ticker: string;
    onResult: (results: BacktestResult[] | null) => void;
}

const STRATEGIES = [
    { id: 'sma_crossover', name: 'SMA Crossover' },
    { id: 'rsi_mean_reversion', name: 'RSI Mean Reversion' },
    { id: 'macd_crossover', name: 'MACD Crossover' },
    { id: 'bollinger_reversion', name: 'Bollinger Band Reversion' },
    { id: 'macd_triple_screen', name: 'MACD Triple Screen (Confluence)' },
    { id: 'turtle_breakout', name: 'Turtle Breakout (Donchian)' }
];

export function StrategyBuilder({ ticker, onResult }: StrategyBuilderProps) {
    const { results, loading, error, runBacktest, clearBacktest } = useBacktest();

    const [strategies, setStrategies] = useState<string[]>([STRATEGIES[0].id]);
    const [capital, setCapital] = useState<number>(10000);
    const [days, setDays] = useState<number>(365);
    const [stopLoss, setStopLoss] = useState<number>(5.0);

    const chartContainerRef = useRef<HTMLDivElement>(null);

    // Render Multi-Equity Chart when results change
    useEffect(() => {
        if (!results || results.length === 0 || !chartContainerRef.current) return;

        const chart = createChart(chartContainerRef.current, {
            layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: 'rgba(160, 165, 185, 0.8)' },
            grid: { vertLines: { color: 'rgba(255, 255, 255, 0.05)' }, horzLines: { color: 'rgba(255, 255, 255, 0.05)' } },
            rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.1, bottom: 0.1 } },
            timeScale: { borderVisible: false, fixLeftEdge: true, fixRightEdge: true },
            height: 200
        });

        const colors = ['#00e676', '#3b82f6', '#f59e0b', '#ec4899', '#8b5cf6', '#06b6d4'];

        results.forEach((res, idx) => {
            if (!res.error && res.equity_curve) {
                const equitySeries = chart.addSeries(LineSeries, {
                    color: colors[idx % colors.length],
                    lineWidth: 2,
                    title: STRATEGIES.find(s => s.id === res.strategy)?.name || res.strategy
                });
                equitySeries.setData(res.equity_curve.map(d => ({ time: d.date as any, value: d.equity })));

                // Only render drawdown area for the first strategy to avoid heavy visual clutter
                if (idx === 0) {
                    const drawdownSeries = chart.addSeries(AreaSeries, {
                        lineColor: 'transparent',
                        topColor: 'rgba(239, 68, 68, 0.0)',
                        bottomColor: 'rgba(239, 68, 68, 0.4)',
                        title: 'Drawdown %',
                        priceScaleId: 'left',
                    });
                    chart.priceScale('left').applyOptions({
                        autoScale: false,
                        scaleMargins: { top: 0.6, bottom: 0.0 },
                    });
                    drawdownSeries.setData(res.equity_curve.map(d => ({
                        time: d.date as any,
                        value: d.drawdown_pct
                    })));
                }
            }
        });

        chart.timeScale().fitContent();

        const handleResize = () => {
            if (chartContainerRef.current) chart.applyOptions({ width: chartContainerRef.current.clientWidth });
        };
        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        };
    }, [results]);

    const handleRun = async () => {
        if (strategies.length === 0) return;
        const req: BacktestRequest = {
            ticker,
            strategies,
            initial_capital: capital,
            days,
            stop_loss_pct: stopLoss
        };
        await runBacktest(req);
    };

    // Pass up to parent whenever result changes so StockChart can plot markers (for the first strat)
    React.useEffect(() => {
        onResult(results);
    }, [results, onResult]);

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
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <label style={{ fontSize: '12px', color: '#a0a5b9' }}>Select Strategies</label>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                            {STRATEGIES.map(s => (
                                <label key={s.id} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#fff', cursor: 'pointer' }}>
                                    <input
                                        type="checkbox"
                                        checked={strategies.includes(s.id)}
                                        onChange={(e) => {
                                            if (e.target.checked) setStrategies([...strategies, s.id]);
                                            else setStrategies(strategies.filter(x => x !== s.id));
                                        }}
                                    />
                                    {s.name}
                                </label>
                            ))}
                        </div>
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

                    <div style={{ display: 'flex', gap: '12px' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
                            <label style={{ fontSize: '12px', color: '#a0a5b9' }}>Stop Loss (%)</label>
                            <input
                                type="number"
                                step="0.5"
                                value={stopLoss}
                                onChange={(e) => setStopLoss(Number(e.target.value))}
                                title="0 to disable stop loss"
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

                        {results && (
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
                {results && !error && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

                        {/* Equity Curve Chart */}
                        <div style={{ background: 'rgba(0,0,0,0.2)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                            <h4 style={{ margin: '0 0 12px 0', fontSize: '13px', color: '#fff', display: 'flex', justifyContent: 'space-between' }}>
                                Comparative Strategy Performance
                            </h4>
                            <div ref={chartContainerRef} style={{ width: '100%' }} />
                        </div>

                        {/* KPI Cards for each Strategy */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            <h4 style={{ margin: 0, fontSize: '13px', color: '#a0a5b9', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Metrics by Strategy</h4>
                            {results.map((res, idx) => (
                                <div key={idx} style={{ background: 'rgba(20, 25, 40, 0.4)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', overflow: 'hidden' }}>
                                    <div style={{ background: 'rgba(255,255,255,0.03)', padding: '8px 12px', fontSize: '12px', fontWeight: 'bold', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between' }}>
                                        <span>{STRATEGIES.find(s => s.id === res.strategy)?.name || res.strategy}</span>
                                        <span style={{ color: (res.total_return_pct ?? 0) >= 0 ? '#00e676' : '#ff1744' }}>
                                            {(res.total_return_pct ?? 0) >= 0 ? '+' : ''}{(res.total_return_pct ?? 0).toFixed(2)}%
                                        </span>
                                    </div>
                                    <div style={{ padding: '10px 12px', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                                        <div>
                                            <div style={{ fontSize: '10px', color: '#64748b' }}>Final Equity</div>
                                            <div style={{ fontSize: '13px', color: '#fff', fontWeight: '600' }}>${(res.final_value ?? capital).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                                        </div>
                                        <div>
                                            <div style={{ fontSize: '10px', color: '#64748b' }}>Win Rate</div>
                                            <div style={{ fontSize: '13px', color: '#fff', fontWeight: '600' }}>{(res.win_rate_pct ?? 0).toFixed(1)}% ({res.total_trades} trades)</div>
                                        </div>
                                        <div>
                                            <div style={{ fontSize: '10px', color: '#64748b' }}>Max Drawdown</div>
                                            <div style={{ fontSize: '13px', color: '#ef4444', fontWeight: '600' }}>{(res.max_drawdown_pct ?? 0).toFixed(2)}%</div>
                                        </div>
                                        <div>
                                            <div style={{ fontSize: '10px', color: '#64748b' }}>vs Buy & Hold</div>
                                            <div style={{ fontSize: '13px', color: '#fff', fontWeight: '600' }}>{(res.benchmark_return_pct ?? 0).toFixed(2)}%</div>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </section>
    );
}

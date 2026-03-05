import React, { useEffect, useRef, useState } from 'react';
import { createChart, IChartApi, ISeriesApi, LineData, CandlestickData, ColorType, CrosshairMode, CandlestickSeries, AreaSeries } from 'lightweight-charts';
import type { PricePoint } from '../../types/api';
import { TrendingUp, TrendingDown, Maximize2 } from 'lucide-react';

interface StockChartProps {
    ticker: string;
    price: number;
    change: number;
    changePct: number;
    history: PricePoint[];
    loading?: boolean;
    period: string;
    onPeriodChange: (period: string) => void;
}

const PERIODS = [
    { label: '1D', value: '1d' },
    { label: '1W', value: '5d' },
    { label: '1M', value: '1mo' },
    { label: '3M', value: '3mo' },
    { label: '6M', value: '6mo' },
    { label: '1Y', value: '1y' },
    { label: '5Y', value: '5y' },
    { label: 'Max', value: 'max' },
];

export function StockChart({ ticker, price, change, changePct, history, loading, period, onPeriodChange }: StockChartProps) {
    const isPositive = change >= 0;
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRef = useRef<ISeriesApi<"Candlestick" | "Area"> | null>(null);
    const [chartType, setChartType] = useState<'candlestick' | 'line'>('candlestick');

    useEffect(() => {
        if (!chartContainerRef.current) return;

        const handleResize = () => {
            if (chartRef.current && chartContainerRef.current) {
                chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: 'transparent' },
                textColor: 'rgba(160, 165, 185, 0.8)',
            },
            grid: {
                vertLines: { color: 'rgba(42, 46, 57, 0.1)' },
                horzLines: { color: 'rgba(42, 46, 57, 0.1)' },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderVisible: false,
            },
            timeScale: {
                borderVisible: false,
                rightOffset: 5,
                barSpacing: 10,
                fixLeftEdge: true,
            },
        });

        chartRef.current = chart;

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        };
    }, []);

    useEffect(() => {
        if (!chartRef.current || !history || history.length === 0) return;

        if (seriesRef.current) {
            chartRef.current.removeSeries(seriesRef.current);
        }

        const validHistory = history.filter(d => Boolean(d.time) && d.close !== undefined);
        const sortedHistory = [...validHistory].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());

        try {
            if (chartType === 'candlestick') {
                const candlestickSeries = chartRef.current.addSeries(CandlestickSeries, {
                    upColor: '#00e676',
                    downColor: '#ff1744',
                    borderVisible: false,
                    wickUpColor: '#00e676',
                    wickDownColor: '#ff1744',
                });
                const data: CandlestickData[] = sortedHistory.map(d => ({
                    time: d.time as any,
                    open: d.open || d.close,
                    high: d.high || d.close,
                    low: d.low || d.close,
                    close: d.close
                }));
                candlestickSeries.setData(data);
                seriesRef.current = candlestickSeries as any;
            } else {
                const areaSeries = chartRef.current.addSeries(AreaSeries, {
                    lineColor: isPositive ? '#00e676' : '#ff1744',
                    topColor: isPositive ? 'rgba(0, 230, 118, 0.4)' : 'rgba(255, 23, 68, 0.4)',
                    bottomColor: isPositive ? 'rgba(0, 230, 118, 0.0)' : 'rgba(255, 23, 68, 0.0)',
                    lineWidth: 2,
                });
                const data: LineData[] = sortedHistory.map(d => ({
                    time: d.time as any,
                    value: d.close
                }));
                areaSeries.setData(data);
                seriesRef.current = areaSeries as any;
            }

            chartRef.current.timeScale().fitContent();
        } catch (e) {
            console.error("Error setting chart data:", e);
        }

    }, [history, chartType, isPositive]);

    return (
        <section className="chart-card glass-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '400px' }}>
            <div className="chart-card__header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                    <span className="chart-card__ticker">{ticker}</span>
                    {loading ? (
                        <div className="loading-skeleton" style={{ width: 120, height: 28, marginTop: 4, borderRadius: 4 }} />
                    ) : (
                        <div className="chart-card__price">
                            <span className="chart-card__value">${price.toFixed(2)}</span>
                            <span className={`chart-card__change ${isPositive ? 'chart-card__change--up' : 'chart-card__change--down'}`}>
                                {isPositive ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                                {' '}{isPositive ? '+' : ''}{change.toFixed(2)} ({changePct.toFixed(2)}%)
                            </span>
                        </div>
                    )}
                </div>

                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', background: 'rgba(20, 25, 40, 0.5)', padding: '6px 8px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                    <div style={{ display: 'flex', borderRight: '1px solid rgba(255,255,255,0.1)', paddingRight: '8px', marginRight: '4px', gap: '4px' }}>
                        <button
                            style={{
                                background: chartType === 'candlestick' ? 'rgba(255,255,255,0.1)' : 'transparent',
                                border: 'none', color: chartType === 'candlestick' ? '#fff' : '#a0a5b9',
                                padding: '4px 8px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', transition: '0.2s'
                            }}
                            onClick={() => setChartType('candlestick')}
                        >Candlestick</button>
                        <button
                            style={{
                                background: chartType === 'line' ? 'rgba(255,255,255,0.1)' : 'transparent',
                                border: 'none', color: chartType === 'line' ? '#fff' : '#a0a5b9',
                                padding: '4px 8px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', transition: '0.2s'
                            }}
                            onClick={() => setChartType('line')}
                        >Line</button>
                    </div>
                    {PERIODS.map(p => (
                        <button
                            key={p.value}
                            style={{
                                background: period === p.value ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                                border: '1px solid',
                                borderColor: period === p.value ? 'rgba(59, 130, 246, 0.5)' : 'transparent',
                                color: period === p.value ? '#60a5fa' : '#a0a5b9',
                                padding: '4px 8px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px',
                                fontWeight: period === p.value ? '600' : 'normal', transition: '0.2s'
                            }}
                            onClick={() => onPeriodChange(p.value)}
                        >
                            {p.label}
                        </button>
                    ))}
                </div>
            </div>

            <div className="chart-card__body" style={{ flex: 1, position: 'relative', marginTop: '16px', minHeight: '300px' }}>
                {loading && <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(10,10,20,0.5)', zIndex: 10, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div className="loading-spinner"></div>
                </div>}
                <div ref={chartContainerRef} style={{ width: '100%', height: '100%', position: 'absolute' }} />
            </div>
        </section>
    );
}

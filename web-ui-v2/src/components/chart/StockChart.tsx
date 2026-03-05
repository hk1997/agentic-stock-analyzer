import React, { useEffect, useRef, useState } from 'react';
import { createChart, IChartApi, ISeriesApi, LineData, CandlestickData, ColorType, CrosshairMode, CandlestickSeries, AreaSeries, LineSeries, HistogramSeries, HistogramData, SeriesMarker } from 'lightweight-charts';
import type { PricePoint } from '../../types/api';
import type { IndicatorPoint } from '../../hooks/useIndicators';
import type { BacktestResult } from '../../hooks/useBacktest';
import { TrendingUp, TrendingDown, Settings2 } from 'lucide-react';

interface StockChartProps {
    ticker: string;
    price: number;
    change: number;
    changePct: number;
    history: PricePoint[];
    indicators?: IndicatorPoint[];
    backtestResult?: BacktestResult | null;
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

export function StockChart({ ticker, price, change, changePct, history, indicators = [], backtestResult, loading, period, onPeriodChange }: StockChartProps) {
    const isPositive = change >= 0;
    const priceChartContainerRef = useRef<HTMLDivElement>(null);
    const rsiChartContainerRef = useRef<HTMLDivElement>(null);
    const macdChartContainerRef = useRef<HTMLDivElement>(null);

    const chartsRef = useRef<{ price: IChartApi | null, rsi: IChartApi | null, macd: IChartApi | null }>({ price: null, rsi: null, macd: null });
    const seriesRef = useRef<any>({});

    const [chartType, setChartType] = useState<'candlestick' | 'line'>('candlestick');

    // Indicator Management State
    const [showIndicatorMenu, setShowIndicatorMenu] = useState(false);
    const [activeIndicators, setActiveIndicators] = useState<string[]>(['sma50', 'rsi', 'macd']);

    const toggleIndicator = (id: string) => {
        setActiveIndicators(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);
    };

    const hasRSI = activeIndicators.includes('rsi');
    const hasMACD = activeIndicators.includes('macd');

    useEffect(() => {
        if (!priceChartContainerRef.current) return;

        const commonOptions = {
            layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: 'rgba(160, 165, 185, 0.8)' },
            grid: { vertLines: { color: 'rgba(42, 46, 57, 0.1)' }, horzLines: { color: 'rgba(42, 46, 57, 0.1)' } },
            crosshair: { mode: CrosshairMode.Normal },
            rightPriceScale: { borderVisible: false },
            timeScale: { borderVisible: false, rightOffset: 5, barSpacing: 10, fixLeftEdge: true },
        };

        const priceChart = createChart(priceChartContainerRef.current, { ...commonOptions });
        chartsRef.current.price = priceChart;
        chartsRef.current.rsi = null;
        chartsRef.current.macd = null;

        let rsiChart: IChartApi | null = null;
        let macdChart: IChartApi | null = null;

        if (rsiChartContainerRef.current && hasRSI) {
            rsiChart = createChart(rsiChartContainerRef.current, { ...commonOptions });
            chartsRef.current.rsi = rsiChart;
        }
        if (macdChartContainerRef.current && hasMACD) {
            macdChart = createChart(macdChartContainerRef.current, { ...commonOptions });
            chartsRef.current.macd = macdChart;
        }

        // Synchronize zooming and panning across active charts
        const activeCharts = [priceChart, rsiChart, macdChart].filter(Boolean) as IChartApi[];

        function syncHandler(source: IChartApi, targets: IChartApi[]) {
            source.timeScale().subscribeVisibleLogicalRangeChange((timeRange) => {
                if (timeRange) {
                    targets.forEach(t => t.timeScale().setVisibleLogicalRange(timeRange));
                }
            });
            source.subscribeCrosshairMove((param) => {
                if (param.time) {
                    targets.forEach(t => {
                        // Clear crosshair if out of bounds to avoid strict series requirement
                        t.clearCrosshairPosition();
                    });
                }
            });
        }

        activeCharts.forEach(source => {
            const targets = activeCharts.filter(c => c !== source);
            syncHandler(source, targets);
        });

        const handleResize = () => {
            if (chartsRef.current.price && priceChartContainerRef.current) chartsRef.current.price.applyOptions({ width: priceChartContainerRef.current.clientWidth });
            if (chartsRef.current.rsi && rsiChartContainerRef.current) chartsRef.current.rsi.applyOptions({ width: rsiChartContainerRef.current.clientWidth });
            if (chartsRef.current.macd && macdChartContainerRef.current) chartsRef.current.macd.applyOptions({ width: macdChartContainerRef.current.clientWidth });
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            if (chartsRef.current.price) { chartsRef.current.price.remove(); chartsRef.current.price = null; }
            if (chartsRef.current.rsi) { chartsRef.current.rsi.remove(); chartsRef.current.rsi = null; }
            if (chartsRef.current.macd) { chartsRef.current.macd.remove(); chartsRef.current.macd = null; }
        };
    }, [hasRSI, hasMACD]); // Re-init charts if panes change

    useEffect(() => {
        const { price: priceChart, rsi: rsiChart, macd: macdChart } = chartsRef.current;
        if (!priceChart || !history || history.length === 0) return;

        // Clean up previous series
        Object.values(seriesRef.current).forEach((series: any) => {
            try { if (series.chart) series.chart.removeSeries(series.handle); } catch (e) { }
        });
        seriesRef.current = {};

        const validHistory = history.filter(d => Boolean(d.time) && d.close !== undefined);
        const sortedHistory = [...validHistory].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());

        // PRICE CHART
        let mainSeries;
        if (chartType === 'candlestick') {
            mainSeries = priceChart.addSeries(CandlestickSeries, {
                upColor: '#00e676', downColor: '#ff1744', borderVisible: false, wickUpColor: '#00e676', wickDownColor: '#ff1744',
            });
            const data: CandlestickData[] = sortedHistory.map(d => ({
                time: d.time as any, open: d.open || d.close, high: d.high || d.close, low: d.low || d.close, close: d.close
            }));
            mainSeries.setData(data);
        } else {
            mainSeries = priceChart.addSeries(AreaSeries, {
                lineColor: isPositive ? '#00e676' : '#ff1744', topColor: isPositive ? 'rgba(0, 230, 118, 0.4)' : 'rgba(255, 23, 68, 0.4)', bottomColor: 'transparent', lineWidth: 2,
            });
            const data: LineData[] = sortedHistory.map(d => ({ time: d.time as any, value: d.close }));
            mainSeries.setData(data);
        }

        // Add Trade Markers if Backtesting
        if (backtestResult && backtestResult.trades.length > 0) {
            // Lightweight charts will crash if a marker is placed on a date that is not in the series data
            const validTimes = new Set(sortedHistory.map(d => d.time));

            const markers: SeriesMarker<any>[] = backtestResult.trades
                .filter(t => validTimes.has(t.date))
                .map(t => ({
                    time: t.date as any,
                    position: t.type === 'BUY' ? 'belowBar' : 'aboveBar',
                    color: t.type === 'BUY' ? '#00e676' : '#ff1744',
                    shape: t.type === 'BUY' ? 'arrowUp' : 'arrowDown',
                    text: t.type === 'BUY' ? 'Buy' : 'Sell',
                }));
            (mainSeries as any).setMarkers(markers);
        }

        seriesRef.current['main'] = { chart: priceChart, handle: mainSeries };

        // INDICATOR OVERLAYS & PANES
        if (indicators && indicators.length > 0) {
            const sortedInds = [...indicators].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());

            if (activeIndicators.includes('sma20')) {
                const sma20Series = priceChart.addSeries(LineSeries, { color: '#00B0FF', lineWidth: 2, title: 'SMA 20' });
                sma20Series.setData(sortedInds.filter(d => d.sma20 !== null).map(d => ({ time: d.time as any, value: d.sma20 as number })));
                seriesRef.current['sma20'] = { chart: priceChart, handle: sma20Series };
            }
            if (activeIndicators.includes('sma50')) {
                const sma50Series = priceChart.addSeries(LineSeries, { color: '#2962FF', lineWidth: 2, title: 'SMA 50' });
                sma50Series.setData(sortedInds.filter(d => d.sma50 !== null).map(d => ({ time: d.time as any, value: d.sma50 as number })));
                seriesRef.current['sma50'] = { chart: priceChart, handle: sma50Series };
            }
            if (activeIndicators.includes('sma200')) {
                const sma200Series = priceChart.addSeries(LineSeries, { color: '#AA00FF', lineWidth: 2, title: 'SMA 200' });
                sma200Series.setData(sortedInds.filter(d => d.sma200 !== null).map(d => ({ time: d.time as any, value: d.sma200 as number })));
                seriesRef.current['sma200'] = { chart: priceChart, handle: sma200Series };
            }
            if (activeIndicators.includes('ema20')) {
                const ema20Series = priceChart.addSeries(LineSeries, { color: '#FFD600', lineWidth: 2, title: 'EMA 20' });
                ema20Series.setData(sortedInds.filter(d => d.ema20 !== null).map(d => ({ time: d.time as any, value: d.ema20 as number })));
                seriesRef.current['ema20'] = { chart: priceChart, handle: ema20Series };
            }
            if (activeIndicators.includes('bbands')) {
                const upperBand = priceChart.addSeries(LineSeries, { color: 'rgba(255, 255, 255, 0.4)', lineWidth: 1, lineStyle: 2 });
                upperBand.setData(sortedInds.filter(d => d.upper_band !== null).map(d => ({ time: d.time as any, value: d.upper_band as number })));
                const lowerBand = priceChart.addSeries(LineSeries, { color: 'rgba(255, 255, 255, 0.4)', lineWidth: 1, lineStyle: 2 });
                lowerBand.setData(sortedInds.filter(d => d.lower_band !== null).map(d => ({ time: d.time as any, value: d.lower_band as number })));
                seriesRef.current['upperBB'] = { chart: priceChart, handle: upperBand };
                seriesRef.current['lowerBB'] = { chart: priceChart, handle: lowerBand };
            }

            if (hasRSI && rsiChart) {
                const rsiSeries = rsiChart.addSeries(LineSeries, { color: '#E040FB', lineWidth: 2, title: 'RSI(14)' });
                rsiSeries.setData(sortedInds.filter(d => d.rsi !== null).map(d => ({ time: d.time as any, value: d.rsi as number })));
                seriesRef.current['rsi'] = { chart: rsiChart, handle: rsiSeries };

                const overbought = rsiChart.addSeries(LineSeries, { color: 'rgba(255, 255, 255, 0.2)', lineWidth: 1, lineStyle: 2, lastValueVisible: false, priceLineVisible: false });
                overbought.setData(sortedInds.map(d => ({ time: d.time as any, value: 70 })));
                const oversold = rsiChart.addSeries(LineSeries, { color: 'rgba(255, 255, 255, 0.2)', lineWidth: 1, lineStyle: 2, lastValueVisible: false, priceLineVisible: false });
                oversold.setData(sortedInds.map(d => ({ time: d.time as any, value: 30 })));
                seriesRef.current['ob'] = { chart: rsiChart, handle: overbought };
                seriesRef.current['os'] = { chart: rsiChart, handle: oversold };
            }

            if (hasMACD && macdChart) {
                const macdHistSeries = macdChart.addSeries(HistogramSeries, { color: '#26a69a' });
                macdHistSeries.setData(sortedInds.filter(d => d.macd_hist !== null).map(d => ({ time: d.time as any, value: d.macd_hist as number, color: (d.macd_hist as number) >= 0 ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)' })));

                const macdSeries = macdChart.addSeries(LineSeries, { color: '#2962FF', lineWidth: 2, title: 'MACD' });
                macdSeries.setData(sortedInds.filter(d => d.macd !== null).map(d => ({ time: d.time as any, value: d.macd as number })));

                const signalSeries = macdChart.addSeries(LineSeries, { color: '#FF6D00', lineWidth: 2, title: 'Signal' });
                signalSeries.setData(sortedInds.filter(d => d.macd_signal !== null).map(d => ({ time: d.time as any, value: d.macd_signal as number })));

                seriesRef.current['macdhist'] = { chart: macdChart, handle: macdHistSeries };
                seriesRef.current['macd'] = { chart: macdChart, handle: macdSeries };
                seriesRef.current['macdsig'] = { chart: macdChart, handle: signalSeries };
            }
        }

        priceChart.timeScale().fitContent();

    }, [history, indicators, backtestResult, chartType, isPositive, activeIndicators, hasRSI, hasMACD]);

    const availableIndicators = [
        { id: 'sma20', label: 'SMA 20' },
        { id: 'sma50', label: 'SMA 50' },
        { id: 'sma200', label: 'SMA 200' },
        { id: 'ema20', label: 'EMA 20' },
        { id: 'bbands', label: 'Bollinger Bands' },
        { id: 'rsi', label: 'RSI (14)' },
        { id: 'macd', label: 'MACD' },
    ];

    return (
        <section className="chart-card glass-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '600px' }}>
            <div className="chart-card__header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px', flexShrink: 0 }}>
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

                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', background: 'rgba(20, 25, 40, 0.5)', padding: '6px 8px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', position: 'relative' }}>

                    <button
                        style={{ border: 'none', background: showIndicatorMenu ? 'rgba(59, 130, 246, 0.2)' : 'transparent', color: showIndicatorMenu ? '#60a5fa' : '#a0a5b9', padding: '4px 8px', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', borderRight: '1px solid rgba(255,255,255,0.1)' }}
                        onClick={() => setShowIndicatorMenu(!showIndicatorMenu)}
                    >
                        <Settings2 size={14} />
                        <span style={{ fontSize: '12px' }}>Indicators</span>
                    </button>

                    {showIndicatorMenu && (
                        <div style={{ position: 'absolute', top: '100%', left: 0, marginTop: '8px', background: '#1c2132', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '8px', zIndex: 50, display: 'flex', flexDirection: 'column', gap: '4px', minWidth: '160px', boxShadow: '0 4px 12px rgba(0,0,0,0.5)' }}>
                            {availableIndicators.map(ind => (
                                <label key={ind.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#fff', fontSize: '12px', cursor: 'pointer', padding: '4px' }}>
                                    <input
                                        type="checkbox"
                                        checked={activeIndicators.includes(ind.id)}
                                        onChange={() => toggleIndicator(ind.id)}
                                        style={{ accentColor: '#3b82f6' }}
                                    />
                                    {ind.label}
                                </label>
                            ))}
                        </div>
                    )}

                    <div style={{ display: 'flex', borderRight: '1px solid rgba(255,255,255,0.1)', paddingRight: '8px', marginRight: '4px', gap: '4px' }}>
                        <button
                            style={{ background: chartType === 'candlestick' ? 'rgba(255,255,255,0.1)' : 'transparent', border: 'none', color: chartType === 'candlestick' ? '#fff' : '#a0a5b9', padding: '4px 8px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', transition: '0.2s' }}
                            onClick={() => setChartType('candlestick')}
                        >Candlestick</button>
                        <button
                            style={{ background: chartType === 'line' ? 'rgba(255,255,255,0.1)' : 'transparent', border: 'none', color: chartType === 'line' ? '#fff' : '#a0a5b9', padding: '4px 8px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', transition: '0.2s' }}
                            onClick={() => setChartType('line')}
                        >Line</button>
                    </div>
                    {PERIODS.map(p => (
                        <button
                            key={p.value}
                            style={{ background: period === p.value ? 'rgba(59, 130, 246, 0.2)' : 'transparent', border: '1px solid', borderColor: period === p.value ? 'rgba(59, 130, 246, 0.5)' : 'transparent', color: period === p.value ? '#60a5fa' : '#a0a5b9', padding: '4px 8px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: period === p.value ? '600' : 'normal', transition: '0.2s' }}
                            onClick={() => onPeriodChange(p.value)}
                        >
                            {p.label}
                        </button>
                    ))}
                </div>
            </div>

            <div className="chart-card__body" style={{ display: 'flex', flexDirection: 'column', flex: 1, position: 'relative', marginTop: '16px', gap: '8px' }}>
                {loading && <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(10,10,20,0.5)', zIndex: 10, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><div className="loading-spinner"></div></div>}

                {/* Price Pane */}
                <div style={{ flex: '3 1 0', position: 'relative', borderBottom: (hasRSI || hasMACD) ? '1px solid rgba(255,255,255,0.05)' : 'none' }}>
                    <div ref={priceChartContainerRef} style={{ width: '100%', height: '100%', position: 'absolute' }} />
                </div>

                {/* MACD Pane */}
                {hasMACD && <div style={{ flex: '1 1 0', position: 'relative', borderBottom: hasRSI ? '1px solid rgba(255,255,255,0.05)' : 'none' }}>
                    <div className="pane-label" style={{ position: 'absolute', top: 4, left: 8, fontSize: '10px', color: '#a0a5b9', zIndex: 1 }}>MACD (12, 26, 9)</div>
                    <div ref={macdChartContainerRef} style={{ width: '100%', height: '100%', position: 'absolute' }} />
                </div>}

                {/* RSI Pane */}
                {hasRSI && <div style={{ flex: '1 1 0', position: 'relative' }}>
                    <div className="pane-label" style={{ position: 'absolute', top: 4, left: 8, fontSize: '10px', color: '#a0a5b9', zIndex: 1 }}>RSI (14)</div>
                    <div ref={rsiChartContainerRef} style={{ width: '100%', height: '100%', position: 'absolute' }} />
                </div>}
            </div>
        </section>
    );
}

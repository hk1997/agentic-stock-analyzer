import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts'
import type { PricePoint } from '../../types/api'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface StockChartProps {
    ticker: string
    price: number
    change: number
    changePct: number
    history: PricePoint[]
    loading?: boolean
}

export function StockChart({ ticker, price, change, changePct, history, loading }: StockChartProps) {
    const isPositive = change >= 0

    if (loading) {
        return (
            <section className="chart-card glass-panel">
                <div className="chart-card__header">
                    <div className="loading-skeleton" style={{ width: 120, height: 28 }} />
                </div>
                <div className="chart-card__body loading-skeleton" />
            </section>
        )
    }

    return (
        <section className="chart-card glass-panel">
            <div className="chart-card__header">
                <span className="chart-card__ticker">{ticker}</span>
                <div className="chart-card__price">
                    <span className="chart-card__value">${price.toFixed(2)}</span>
                    <span className={`chart-card__change ${isPositive ? 'chart-card__change--up' : 'chart-card__change--down'}`}>
                        {isPositive ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                        {' '}{isPositive ? '+' : ''}{change.toFixed(2)} ({changePct.toFixed(2)}%)
                    </span>
                </div>
            </div>

            <div className="chart-card__body">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={history} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                        <defs>
                            <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={isPositive ? '#00e676' : '#ff1744'} stopOpacity={0.2} />
                                <stop offset="100%" stopColor={isPositive ? '#00e676' : '#ff1744'} stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <XAxis
                            dataKey="time"
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: 'rgba(160,165,185,0.5)', fontSize: 11 }}
                            interval="preserveStartEnd"
                        />
                        <YAxis
                            domain={['auto', 'auto']}
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: 'rgba(160,165,185,0.5)', fontSize: 11 }}
                            width={60}
                        />
                        <Tooltip
                            contentStyle={{
                                background: 'rgba(10,10,20,0.9)',
                                border: '1px solid rgba(255,255,255,0.1)',
                                borderRadius: 12,
                                color: '#f0f0f5',
                                fontSize: 13,
                            }}
                        />
                        <Area
                            type="monotone"
                            dataKey="close"
                            stroke={isPositive ? '#00e676' : '#ff1744'}
                            strokeWidth={2}
                            fill="url(#chartGradient)"
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </section>
    )
}

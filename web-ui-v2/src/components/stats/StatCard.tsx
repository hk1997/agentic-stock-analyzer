import { ArrowUpRight, ArrowDownRight } from 'lucide-react'

interface StatCardProps {
    label: string
    value: string
    sentiment?: 'bullish' | 'bearish' | 'neutral'
    loading?: boolean
}

export function StatCard({ label, value, sentiment, loading }: StatCardProps) {
    if (loading) {
        return (
            <div className="stat-card glass-panel">
                <div className="loading-skeleton" style={{ width: 80, height: 14, marginBottom: 8 }} />
                <div className="loading-skeleton" style={{ width: 100, height: 32 }} />
            </div>
        )
    }

    return (
        <div className="stat-card glass-panel">
            <div className="stat-card__label">{label}</div>
            <div className="stat-card__value">{value}</div>
            {sentiment && sentiment !== 'neutral' && (
                <span className={`badge badge--${sentiment}`}>
                    {sentiment === 'bullish' ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                    {sentiment.toUpperCase()}
                </span>
            )}
        </div>
    )
}

interface StatsRowProps {
    peRatio?: number | null
    marketCap?: number | null
    fiftyTwoWeekHigh?: number | null
    fiftyTwoWeekLow?: number | null
    loading?: boolean
}

function formatMarketCap(cap: number | null | undefined): string {
    if (!cap) return '—'
    if (cap >= 1e12) return `$${(cap / 1e12).toFixed(1)}T`
    if (cap >= 1e9) return `$${(cap / 1e9).toFixed(1)}B`
    if (cap >= 1e6) return `$${(cap / 1e6).toFixed(0)}M`
    return `$${cap.toLocaleString()}`
}

export function StatsRow({ peRatio, marketCap, fiftyTwoWeekHigh, fiftyTwoWeekLow, loading }: StatsRowProps) {
    return (
        <div className="stats-row">
            <StatCard
                label="P/E Ratio"
                value={peRatio ? peRatio.toFixed(1) : '—'}
                sentiment={peRatio ? (peRatio < 25 ? 'bullish' : peRatio > 40 ? 'bearish' : 'neutral') : undefined}
                loading={loading}
            />
            <StatCard
                label="Market Cap"
                value={formatMarketCap(marketCap)}
                loading={loading}
            />
            <StatCard
                label="52W High"
                value={fiftyTwoWeekHigh ? `$${fiftyTwoWeekHigh.toFixed(2)}` : '—'}
                loading={loading}
            />
            <StatCard
                label="52W Low"
                value={fiftyTwoWeekLow ? `$${fiftyTwoWeekLow.toFixed(2)}` : '—'}
                loading={loading}
            />
        </div>
    )
}

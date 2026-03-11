import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { usePortfolio } from '../../hooks/usePortfolio'
import type { Holding } from '../../hooks/usePortfolio'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import {
    DollarSign,
    TrendingUp,
    TrendingDown,
    Plus,
    Trash2,
    Edit3,
    X,
    RefreshCw,
    Briefcase,
    BarChart3,
    PieChart as PieIcon,
    Upload,
    FileText,
    CheckCircle,
    AlertCircle,
    ChevronDown,
    ChevronRight,
    ArrowUpDown,
    ArrowUp,
    ArrowDown,
    Banknote,
    Calendar,
    Receipt,
    Activity,
    Target,
    Shield,
} from 'lucide-react'

type TabId = 'holdings' | 'realized' | 'dividends' | 'benchmarks'

interface RealizedTicker {
    ticker: string
    name: string
    total_proceeds: number
    total_realized_pnl: number
    total_shares_sold: number
    num_trades: number
    trades: { date: string; shares: number; price: number; proceeds: number; pnl: number }[]
}

interface DividendTicker {
    ticker: string
    name: string
    total_income: number
    num_payments: number
    payments: { date: string; shares: number; per_share: number; income: number }[]
}

interface RealizedData {
    total_realized_pnl: number
    total_dividend_income: number
    total_income: number
    realized: RealizedTicker[]
    dividends: DividendTicker[]
}

interface BenchmarkReturns {
    '1m': number | null
    '3m': number | null
    '6m': number | null
    'ytd': number | null
    '1y': number | null
    'since_inception': number | null
}

interface BenchmarkData {
    portfolio_return: BenchmarkReturns
    benchmarks: { name: string; ticker: string; returns: BenchmarkReturns }[]
    beta: number | null
    alpha: number | null
    sharpe_ratio: number | null
    inception_date: string
    total_invested: number
    current_value: number
    unrealized_pnl: number
    realized_pnl: number
    dividend_income: number
    total_return_pct: number | null
}

type SortDir = 'asc' | 'desc'
type SortState<K extends string> = { key: K; dir: SortDir }

function useSorted<T, K extends string>(items: T[], sort: SortState<K> | null, accessor: (item: T, key: K) => string | number) {
    return useMemo(() => {
        if (!sort || !items.length) return items
        const sorted = [...items].sort((a, b) => {
            const av = accessor(a, sort.key)
            const bv = accessor(b, sort.key)
            if (typeof av === 'string' && typeof bv === 'string') {
                return sort.dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
            }
            return sort.dir === 'asc' ? (av as number) - (bv as number) : (bv as number) - (av as number)
        })
        return sorted
    }, [items, sort, accessor])
}

function SortableHeader<K extends string>({ label, sortKey, sort, onSort, className }: {
    label: string, sortKey: K, sort: SortState<K> | null,
    onSort: (key: K) => void, className?: string
}) {
    const active = sort?.key === sortKey
    return (
        <th className={`sortable-th ${className || ''} ${active ? 'sortable-th--active' : ''}`}
            onClick={() => onSort(sortKey)}>
            {label}
            <span className="sort-icon">
                {active ? (sort!.dir === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />) : <ArrowUpDown size={12} />}
            </span>
        </th>
    )
}

function toggleSort<K extends string>(prev: SortState<K> | null, key: K): SortState<K> {
    if (prev?.key === key) return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
    return { key, dir: 'desc' }
}

const COLORS = ['#00e676', '#2979ff', '#ff9100', '#e040fb', '#00e5ff', '#ffea00', '#ff1744', '#76ff03', '#d500f9', '#1de9b6']

export function PortfolioPage() {
    const { portfolio, loading, error, addHolding, updateHolding, removeHolding, importCsv, refresh } = usePortfolio()
    const [showAddModal, setShowAddModal] = useState(false)
    const [editHolding, setEditHolding] = useState<Holding | null>(null)
    const [formTicker, setFormTicker] = useState('')
    const [formShares, setFormShares] = useState('')
    const [formCost, setFormCost] = useState('')

    // Tab state
    const [activeTab, setActiveTab] = useState<TabId>('holdings')
    const [realizedData, setRealizedData] = useState<RealizedData | null>(null)
    const [realizedLoading, setRealizedLoading] = useState(false)
    const [expandedTickers, setExpandedTickers] = useState<Set<string>>(new Set())

    // Benchmark state
    const [benchmarkData, setBenchmarkData] = useState<BenchmarkData | null>(null)
    const [benchmarkLoading, setBenchmarkLoading] = useState(false)
    const [benchmarkPeriod, setBenchmarkPeriod] = useState<keyof BenchmarkReturns>('since_inception')

    // Sort state for each tab
    type HoldingKey = 'ticker' | 'name' | 'sector' | 'shares' | 'avg_cost_basis' | 'current_price' | 'current_value' | 'unrealized_pnl' | 'unrealized_pnl_pct' | 'weight_pct'
    type RealizedKey = 'ticker' | 'name' | 'num_trades' | 'total_shares_sold' | 'total_proceeds' | 'total_realized_pnl'
    type DividendKey = 'ticker' | 'name' | 'num_payments' | 'total_income'
    const [holdingSort, setHoldingSort] = useState<SortState<HoldingKey> | null>(null)
    const [realizedSort, setRealizedSort] = useState<SortState<RealizedKey> | null>(null)
    const [dividendSort, setDividendSort] = useState<SortState<DividendKey> | null>(null)

    const holdingAccessor = useCallback((h: Holding, key: HoldingKey) => {
        if (key === 'ticker' || key === 'name' || key === 'sector') return (h as unknown as Record<string, string | number>)[key] as string
        return (h as unknown as Record<string, string | number>)[key] as number
    }, [])
    const realizedAccessor = useCallback((r: RealizedTicker, key: RealizedKey) => {
        if (key === 'ticker' || key === 'name') return (r as unknown as Record<string, string | number>)[key] as string
        return (r as unknown as Record<string, string | number>)[key] as number
    }, [])
    const dividendAccessor = useCallback((d: DividendTicker, key: DividendKey) => {
        if (key === 'ticker' || key === 'name') return (d as unknown as Record<string, string | number>)[key] as string
        return (d as unknown as Record<string, string | number>)[key] as number
    }, [])

    const sortedHoldings = useSorted(portfolio?.holdings || [], holdingSort, holdingAccessor)
    const sortedRealized = useSorted(realizedData?.realized || [], realizedSort, realizedAccessor)
    const sortedDividends = useSorted(realizedData?.dividends || [], dividendSort, dividendAccessor)

    // Import state
    const [showImportModal, setShowImportModal] = useState(false)
    const [importFile, setImportFile] = useState<File | null>(null)
    const [importLoading, setImportLoading] = useState(false)
    const [importResult, setImportResult] = useState<{ new_transactions?: number; skipped?: number; holdings_count?: number; total_realized_pnl?: number; total_in_csv?: number; error?: string } | null>(null)
    const [dragOver, setDragOver] = useState(false)
    const fileInputRef = useRef<HTMLInputElement>(null)

    // Fetch realized data when tab switches
    const fetchRealized = useCallback(async () => {
        const pid = portfolio?.id
        if (!pid) return
        setRealizedLoading(true)
        try {
            const res = await fetch(`/api/portfolio/${pid}/realized`)
            if (res.ok) {
                const data = await res.json()
                setRealizedData(data)
            }
        } catch { /* ignore */ }
        setRealizedLoading(false)
    }, [portfolio?.id])

    useEffect(() => {
        if ((activeTab === 'realized' || activeTab === 'dividends') && !realizedData) {
            fetchRealized()
        }
    }, [activeTab, realizedData, fetchRealized])

    // Fetch benchmarks data when tab switches
    const fetchBenchmarks = useCallback(async () => {
        if (!portfolio?.id) return
        setBenchmarkLoading(true)
        try {
            const res = await fetch(`/api/portfolio/${portfolio.id}/benchmarks`)
            const data = await res.json()
            if (!data.error) setBenchmarkData(data)
        } catch { /* ignore */ } finally {
            setBenchmarkLoading(false)
        }
    }, [portfolio?.id])

    useEffect(() => {
        if (activeTab === 'benchmarks' && !benchmarkData) fetchBenchmarks()
    }, [activeTab, benchmarkData, fetchBenchmarks])

    const toggleExpand = (ticker: string) => {
        setExpandedTickers(prev => {
            const next = new Set(prev)
            next.has(ticker) ? next.delete(ticker) : next.add(ticker)
            return next
        })
    }

    const resetForm = () => {
        setFormTicker('')
        setFormShares('')
        setFormCost('')
        setEditHolding(null)
    }

    const handleAdd = async () => {
        if (!formTicker || !formShares || !formCost) return
        await addHolding(formTicker.toUpperCase(), parseFloat(formShares), parseFloat(formCost))
        resetForm()
        setShowAddModal(false)
    }

    const handleUpdate = async () => {
        if (!editHolding || !formTicker || !formShares || !formCost) return
        await updateHolding(editHolding.id, formTicker.toUpperCase(), parseFloat(formShares), parseFloat(formCost))
        resetForm()
    }

    const handleDelete = async (id: number) => {
        await removeHolding(id)
    }

    const openEdit = (h: Holding) => {
        setEditHolding(h)
        setFormTicker(h.ticker)
        setFormShares(String(h.shares))
        setFormCost(String(h.avg_cost_basis))
    }

    // Import handlers
    const handleImportFile = (file: File) => {
        if (!file.name.toLowerCase().endsWith('.csv')) {
            setImportResult({ error: 'Please select a CSV file.' })
            return
        }
        setImportFile(file)
        setImportResult(null)
    }

    const handleImportConfirm = async () => {
        if (!importFile) return
        setImportLoading(true)
        try {
            const result = await importCsv(importFile)
            setImportResult(result)
            if (result && !result.error) {
                setImportFile(null)
            }
        } catch (e: unknown) {
            setImportResult({ error: e instanceof Error ? e.message : 'Import failed' })
        } finally {
            setImportLoading(false)
        }
    }

    const closeImportModal = () => {
        setShowImportModal(false)
        setImportFile(null)
        setImportResult(null)
        setImportLoading(false)
    }

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault()
        setDragOver(false)
        const file = e.dataTransfer.files[0]
        if (file) handleImportFile(file)
    }

    // Sector aggregation
    const sectorData = portfolio ? Object.entries(
        portfolio.holdings.reduce<Record<string, number>>((acc, h) => {
            const s = h.sector || 'Unknown'
            acc[s] = (acc[s] || 0) + h.current_value
            return acc
        }, {})
    ).map(([name, value]) => ({ name, value: Math.round(value) })) : []

    const allocationData = portfolio
        ? portfolio.holdings.map(h => ({ name: h.ticker, value: Math.round(h.current_value) }))
        : []

    if (loading && !portfolio) {
        return (
            <main className="main-content">
                <div className="portfolio-page">
                    <div className="portfolio-loading">
                        <RefreshCw size={32} className="spin" />
                        <p>Loading portfolio...</p>
                    </div>
                </div>
            </main>
        )
    }

    return (
        <main className="main-content">
            <div className="portfolio-page">
                {/* Header */}
                <div className="portfolio-header">
                    <div className="portfolio-header__left">
                        <Briefcase size={28} />
                        <div>
                            <h1>{portfolio?.name || 'My Portfolio'}</h1>
                            <p className="portfolio-header__subtitle">
                                {portfolio?.num_holdings || 0} holdings
                                {(portfolio as any)?.last_updated && (
                                    <span className="last-updated"><Calendar size={12} /> Updated {(portfolio as any).last_updated}</span>
                                )}
                            </p>
                        </div>
                    </div>
                    <div className="portfolio-header__actions">
                        <button className="btn btn--secondary" onClick={refresh}>
                            <RefreshCw size={16} /> Refresh
                        </button>
                        <button className="btn btn--secondary" onClick={() => { setShowImportModal(true); setImportResult(null); setImportFile(null) }}>
                            <Upload size={16} /> Import CSV
                        </button>
                        <button className="btn btn--primary" onClick={() => { resetForm(); setShowAddModal(true) }}>
                            <Plus size={16} /> Add Holding
                        </button>
                    </div>
                </div>

                {error && <div className="portfolio-error">{error}</div>}

                {/* Summary Cards */}
                <div className="portfolio-summary">
                    <div className="summary-card">
                        <div className="summary-card__icon"><DollarSign size={20} /></div>
                        <div className="summary-card__content">
                            <span className="summary-card__label">Total Value</span>
                            <span className="summary-card__value">${portfolio?.total_value?.toLocaleString(undefined, { minimumFractionDigits: 2 }) || '0.00'}</span>
                        </div>
                    </div>
                    <div className="summary-card">
                        <div className="summary-card__icon"><DollarSign size={20} /></div>
                        <div className="summary-card__content">
                            <span className="summary-card__label">Total Cost</span>
                            <span className="summary-card__value">${portfolio?.total_cost?.toLocaleString(undefined, { minimumFractionDigits: 2 }) || '0.00'}</span>
                        </div>
                    </div>
                    <div className="summary-card">
                        <div className={`summary-card__icon ${(portfolio?.total_pnl ?? 0) >= 0 ? 'positive' : 'negative'}`}>
                            {(portfolio?.total_pnl ?? 0) >= 0 ? <TrendingUp size={20} /> : <TrendingDown size={20} />}
                        </div>
                        <div className="summary-card__content">
                            <span className="summary-card__label">Unrealized P&L</span>
                            <span className={`summary-card__value ${(portfolio?.total_pnl ?? 0) >= 0 ? 'positive' : 'negative'}`}>
                                {(portfolio?.total_pnl ?? 0) >= 0 ? '+' : ''}${portfolio?.total_pnl?.toLocaleString(undefined, { minimumFractionDigits: 2 }) || '0.00'}
                            </span>
                        </div>
                    </div>
                    <div className="summary-card">
                        <div className={`summary-card__icon ${(portfolio?.total_pnl_pct ?? 0) >= 0 ? 'positive' : 'negative'}`}>
                            <BarChart3 size={20} />
                        </div>
                        <div className="summary-card__content">
                            <span className="summary-card__label">Return %</span>
                            <span className={`summary-card__value ${(portfolio?.total_pnl_pct ?? 0) >= 0 ? 'positive' : 'negative'}`}>
                                {(portfolio?.total_pnl_pct ?? 0) >= 0 ? '+' : ''}{portfolio?.total_pnl_pct?.toFixed(2) || '0.00'}%
                            </span>
                        </div>
                    </div>
                </div>

                {/* Tab Bar */}
                <div className="portfolio-tabs">
                    <button className={`portfolio-tab ${activeTab === 'holdings' ? 'portfolio-tab--active' : ''}`} onClick={() => setActiveTab('holdings')}>
                        <Briefcase size={16} /> Holdings
                    </button>
                    <button className={`portfolio-tab ${activeTab === 'realized' ? 'portfolio-tab--active' : ''}`} onClick={() => setActiveTab('realized')}>
                        <Banknote size={16} /> Realized P&L
                    </button>
                    <button className={`portfolio-tab ${activeTab === 'dividends' ? 'portfolio-tab--active' : ''}`} onClick={() => setActiveTab('dividends')}>
                        <Receipt size={16} /> Dividends
                    </button>
                    <button className={`portfolio-tab ${activeTab === 'benchmarks' ? 'portfolio-tab--active' : ''}`} onClick={() => setActiveTab('benchmarks')}>
                        <Activity size={16} /> Benchmarks
                    </button>
                </div>

                {/* Holdings Tab */}
                {activeTab === 'holdings' && (
                    <>
                        <div className="portfolio-card">
                            <h2 className="portfolio-card__title"><Briefcase size={18} /> Holdings</h2>
                            {portfolio && portfolio.holdings.length > 0 ? (
                                <div className="holdings-table-wrapper">
                                    <table className="holdings-table">
                                        <thead>
                                            <tr>
                                                <SortableHeader label="Ticker" sortKey="ticker" sort={holdingSort} onSort={k => setHoldingSort(toggleSort(holdingSort, k))} />
                                                <SortableHeader label="Name" sortKey="name" sort={holdingSort} onSort={k => setHoldingSort(toggleSort(holdingSort, k))} />
                                                <SortableHeader label="Sector" sortKey="sector" sort={holdingSort} onSort={k => setHoldingSort(toggleSort(holdingSort, k))} />
                                                <SortableHeader label="Shares" sortKey="shares" sort={holdingSort} onSort={k => setHoldingSort(toggleSort(holdingSort, k))} className="num" />
                                                <SortableHeader label="Avg Cost" sortKey="avg_cost_basis" sort={holdingSort} onSort={k => setHoldingSort(toggleSort(holdingSort, k))} className="num" />
                                                <SortableHeader label="Price" sortKey="current_price" sort={holdingSort} onSort={k => setHoldingSort(toggleSort(holdingSort, k))} className="num" />
                                                <SortableHeader label="Value" sortKey="current_value" sort={holdingSort} onSort={k => setHoldingSort(toggleSort(holdingSort, k))} className="num" />
                                                <SortableHeader label="P&L" sortKey="unrealized_pnl" sort={holdingSort} onSort={k => setHoldingSort(toggleSort(holdingSort, k))} className="num" />
                                                <SortableHeader label="P&L %" sortKey="unrealized_pnl_pct" sort={holdingSort} onSort={k => setHoldingSort(toggleSort(holdingSort, k))} className="num" />
                                                <SortableHeader label="Weight" sortKey="weight_pct" sort={holdingSort} onSort={k => setHoldingSort(toggleSort(holdingSort, k))} className="num" />
                                                <th>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {sortedHoldings.map(h => (
                                                <tr key={h.id}>
                                                    <td className="ticker-cell">{h.ticker}</td>
                                                    <td className="name-cell">{h.name}</td>
                                                    <td className="sector-cell">{h.sector}</td>
                                                    <td className="num">{h.shares}</td>
                                                    <td className="num">${h.avg_cost_basis.toFixed(2)}</td>
                                                    <td className="num">${h.current_price.toFixed(2)}</td>
                                                    <td className="num">${h.current_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                                                    <td className={`num ${h.unrealized_pnl >= 0 ? 'positive' : 'negative'}`}>
                                                        {h.unrealized_pnl >= 0 ? '+' : ''}${h.unrealized_pnl.toFixed(2)}
                                                    </td>
                                                    <td className={`num ${h.unrealized_pnl_pct >= 0 ? 'positive' : 'negative'}`}>
                                                        {h.unrealized_pnl_pct >= 0 ? '+' : ''}{h.unrealized_pnl_pct.toFixed(2)}%
                                                    </td>
                                                    <td className="num">{h.weight_pct.toFixed(1)}%</td>
                                                    <td className="actions-cell">
                                                        <button className="icon-btn" onClick={() => openEdit(h)} title="Edit"><Edit3 size={14} /></button>
                                                        <button className="icon-btn icon-btn--danger" onClick={() => handleDelete(h.id)} title="Delete"><Trash2 size={14} /></button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <div className="portfolio-empty">
                                    <p>No holdings yet. Click <strong>"Add Holding"</strong> or <strong>"Import CSV"</strong> to get started.</p>
                                </div>
                            )}
                        </div>

                        {/* Charts Row */}
                        {portfolio && portfolio.holdings.length > 0 && (
                            <div className="portfolio-charts-row">
                                <div className="portfolio-card portfolio-card--half">
                                    <h2 className="portfolio-card__title"><PieIcon size={18} /> Allocation by Ticker</h2>
                                    <ResponsiveContainer width="100%" height={300}>
                                        <PieChart>
                                            <Pie data={allocationData} cx="50%" cy="50%" outerRadius={100} innerRadius={50} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                                                {allocationData.map((_entry, i) => (
                                                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                                                ))}
                                            </Pie>
                                            <Tooltip formatter={(value: number) => `$${value.toLocaleString()}`} contentStyle={{ background: '#1a1e2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#e0e0e0' }} labelStyle={{ color: '#fff' }} itemStyle={{ color: '#ccc' }} />
                                            <Legend />
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                                <div className="portfolio-card portfolio-card--half">
                                    <h2 className="portfolio-card__title"><PieIcon size={18} /> Allocation by Sector</h2>
                                    <ResponsiveContainer width="100%" height={300}>
                                        <PieChart>
                                            <Pie data={sectorData} cx="50%" cy="50%" outerRadius={100} innerRadius={50} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                                                {sectorData.map((_entry, i) => (
                                                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                                                ))}
                                            </Pie>
                                            <Tooltip formatter={(value: number) => `$${value.toLocaleString()}`} contentStyle={{ background: '#1a1e2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#e0e0e0' }} labelStyle={{ color: '#fff' }} itemStyle={{ color: '#ccc' }} />
                                            <Legend />
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        )}
                    </>
                )}

                {/* Realized P&L Tab */}
                {activeTab === 'realized' && (
                    <div className="portfolio-card">
                        <h2 className="portfolio-card__title"><Banknote size={18} /> Realized Profit & Loss</h2>
                        {realizedLoading ? (
                            <div className="portfolio-loading"><RefreshCw size={24} className="spin" /> Loading...</div>
                        ) : realizedData && realizedData.realized.length > 0 ? (
                            <>
                                <div className="realized-summary-strip">
                                    <div className={`realized-summary-pill ${realizedData.total_realized_pnl >= 0 ? 'positive' : 'negative'}`}>
                                        {realizedData.total_realized_pnl >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                                        Total Realized: <strong>£{realizedData.total_realized_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong>
                                    </div>
                                </div>
                                <div className="holdings-table-wrapper">
                                    <table className="holdings-table">
                                        <thead>
                                            <tr>
                                                <th style={{ width: 30 }}></th>
                                                <SortableHeader label="Ticker" sortKey="ticker" sort={realizedSort} onSort={k => setRealizedSort(toggleSort(realizedSort, k))} />
                                                <SortableHeader label="Name" sortKey="name" sort={realizedSort} onSort={k => setRealizedSort(toggleSort(realizedSort, k))} />
                                                <SortableHeader label="Trades" sortKey="num_trades" sort={realizedSort} onSort={k => setRealizedSort(toggleSort(realizedSort, k))} className="num" />
                                                <SortableHeader label="Shares Sold" sortKey="total_shares_sold" sort={realizedSort} onSort={k => setRealizedSort(toggleSort(realizedSort, k))} className="num" />
                                                <SortableHeader label="Total Proceeds" sortKey="total_proceeds" sort={realizedSort} onSort={k => setRealizedSort(toggleSort(realizedSort, k))} className="num" />
                                                <SortableHeader label="Realized P&L" sortKey="total_realized_pnl" sort={realizedSort} onSort={k => setRealizedSort(toggleSort(realizedSort, k))} className="num" />
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {sortedRealized.map(r => (
                                                <React.Fragment key={r.ticker}>
                                                    <tr className="expandable-row" onClick={() => toggleExpand('r_' + r.ticker)}>
                                                        <td>{expandedTickers.has('r_' + r.ticker) ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</td>
                                                        <td className="ticker-cell">{r.ticker}</td>
                                                        <td className="name-cell">{r.name}</td>
                                                        <td className="num">{r.num_trades}</td>
                                                        <td className="num">{r.total_shares_sold.toFixed(2)}</td>
                                                        <td className="num">£{r.total_proceeds.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                                                        <td className={`num ${r.total_realized_pnl >= 0 ? 'positive' : 'negative'}`}>
                                                            {r.total_realized_pnl >= 0 ? '+' : ''}£{r.total_realized_pnl.toFixed(2)}
                                                        </td>
                                                    </tr>
                                                    {expandedTickers.has('r_' + r.ticker) && r.trades.map((t, i) => (
                                                        <tr key={i} className="detail-row">
                                                            <td></td>
                                                            <td className="detail-date">{t.date}</td>
                                                            <td></td>
                                                            <td className="num detail-num">{t.shares.toFixed(4)}</td>
                                                            <td className="num detail-num">${t.price.toFixed(2)}</td>
                                                            <td className="num detail-num">£{t.proceeds.toFixed(2)}</td>
                                                            <td className={`num detail-num ${t.pnl >= 0 ? 'positive' : 'negative'}`}>
                                                                {t.pnl >= 0 ? '+' : ''}£{t.pnl.toFixed(2)}
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </React.Fragment>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </>
                        ) : (
                            <div className="portfolio-empty"><p>No realized trades yet. Sell positions will appear here.</p></div>
                        )}
                    </div>
                )}

                {/* Dividends Tab */}
                {activeTab === 'dividends' && (
                    <div className="portfolio-card">
                        <h2 className="portfolio-card__title"><Receipt size={18} /> Dividend Income</h2>
                        {realizedLoading ? (
                            <div className="portfolio-loading"><RefreshCw size={24} className="spin" /> Loading...</div>
                        ) : realizedData && realizedData.dividends.length > 0 ? (
                            <>
                                <div className="realized-summary-strip">
                                    <div className="realized-summary-pill positive">
                                        <DollarSign size={16} />
                                        Total Dividends: <strong>£{realizedData.total_dividend_income.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong>
                                    </div>
                                </div>
                                <div className="holdings-table-wrapper">
                                    <table className="holdings-table">
                                        <thead>
                                            <tr>
                                                <th style={{ width: 30 }}></th>
                                                <SortableHeader label="Ticker" sortKey="ticker" sort={dividendSort} onSort={k => setDividendSort(toggleSort(dividendSort, k))} />
                                                <SortableHeader label="Name" sortKey="name" sort={dividendSort} onSort={k => setDividendSort(toggleSort(dividendSort, k))} />
                                                <SortableHeader label="Payments" sortKey="num_payments" sort={dividendSort} onSort={k => setDividendSort(toggleSort(dividendSort, k))} className="num" />
                                                <SortableHeader label="Total Income" sortKey="total_income" sort={dividendSort} onSort={k => setDividendSort(toggleSort(dividendSort, k))} className="num" />
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {sortedDividends.map(d => (
                                                <React.Fragment key={d.ticker}>
                                                    <tr className="expandable-row" onClick={() => toggleExpand('d_' + d.ticker)}>
                                                        <td>{expandedTickers.has('d_' + d.ticker) ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</td>
                                                        <td className="ticker-cell">{d.ticker}</td>
                                                        <td className="name-cell">{d.name}</td>
                                                        <td className="num">{d.num_payments}</td>
                                                        <td className="num positive">£{d.total_income.toFixed(2)}</td>
                                                    </tr>
                                                    {expandedTickers.has('d_' + d.ticker) && d.payments.map((p, i) => (
                                                        <tr key={i} className="detail-row">
                                                            <td></td>
                                                            <td className="detail-date">{p.date}</td>
                                                            <td className="detail-num">{p.shares.toFixed(2)} shares @ ${p.per_share.toFixed(4)}</td>
                                                            <td></td>
                                                            <td className="num detail-num positive">£{p.income.toFixed(2)}</td>
                                                        </tr>
                                                    ))}
                                                </React.Fragment>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </>
                        ) : (
                            <div className="portfolio-empty"><p>No dividend income recorded yet. Dividends from your holdings will appear here.</p></div>
                        )}
                    </div>
                )}

                {/* Benchmarks Tab */}
                {activeTab === 'benchmarks' && (
                    <div className="portfolio-card">
                        <h2 className="portfolio-card__title"><Activity size={18} /> Benchmark Comparison</h2>
                        {benchmarkLoading ? (
                            <div className="portfolio-loading"><RefreshCw size={24} className="spin" /> Loading benchmarks...</div>
                        ) : benchmarkData ? (
                            <>
                                {/* Risk Metrics */}
                                <div className="benchmark-metrics">
                                    <div className="benchmark-metric-card">
                                        <div className="benchmark-metric-card__icon"><Target size={18} /></div>
                                        <div className="benchmark-metric-card__content">
                                            <span className="benchmark-metric-card__label">Beta</span>
                                            <span className="benchmark-metric-card__value">{benchmarkData.beta?.toFixed(2) ?? '—'}</span>
                                            <span className="benchmark-metric-card__hint">{benchmarkData.beta != null ? (benchmarkData.beta > 1 ? 'Higher volatility' : benchmarkData.beta < 1 ? 'Lower volatility' : 'Market level') : ''}</span>
                                        </div>
                                    </div>
                                    <div className="benchmark-metric-card">
                                        <div className={`benchmark-metric-card__icon ${(benchmarkData.alpha ?? 0) >= 0 ? 'positive' : 'negative'}`}><TrendingUp size={18} /></div>
                                        <div className="benchmark-metric-card__content">
                                            <span className="benchmark-metric-card__label">Alpha (annualized)</span>
                                            <span className={`benchmark-metric-card__value ${(benchmarkData.alpha ?? 0) >= 0 ? 'positive' : 'negative'}`}>{benchmarkData.alpha != null ? `${benchmarkData.alpha >= 0 ? '+' : ''}${benchmarkData.alpha}%` : '—'}</span>
                                            <span className="benchmark-metric-card__hint">{benchmarkData.alpha != null ? (benchmarkData.alpha > 0 ? 'Outperforming market' : 'Underperforming market') : ''}</span>
                                        </div>
                                    </div>
                                    <div className="benchmark-metric-card">
                                        <div className="benchmark-metric-card__icon"><Shield size={18} /></div>
                                        <div className="benchmark-metric-card__content">
                                            <span className="benchmark-metric-card__label">Sharpe Ratio</span>
                                            <span className="benchmark-metric-card__value">{benchmarkData.sharpe_ratio?.toFixed(2) ?? '—'}</span>
                                            <span className="benchmark-metric-card__hint">{benchmarkData.sharpe_ratio != null ? (benchmarkData.sharpe_ratio > 1 ? 'Good risk-adjusted' : benchmarkData.sharpe_ratio > 0 ? 'Moderate' : 'Poor') : ''}</span>
                                        </div>
                                    </div>
                                </div>

                                {/* Period Selector */}
                                <div className="benchmark-period-bar">
                                    {([['1m', '1M'], ['3m', '3M'], ['6m', '6M'], ['ytd', 'YTD'], ['1y', '1Y'], ['since_inception', 'All']] as [keyof BenchmarkReturns, string][]).map(([key, label]) => (
                                        <button key={key} className={`benchmark-period-btn ${benchmarkPeriod === key ? 'benchmark-period-btn--active' : ''}`}
                                            onClick={() => setBenchmarkPeriod(key)}>{label}</button>
                                    ))}
                                </div>

                                {/* Comparison Table */}
                                <div className="holdings-table-wrapper">
                                    <table className="holdings-table benchmark-table">
                                        <thead>
                                            <tr>
                                                <th></th>
                                                {([['1m', '1M'], ['3m', '3M'], ['6m', '6M'], ['ytd', 'YTD'], ['1y', '1Y'], ['since_inception', 'All']] as [keyof BenchmarkReturns, string][]).map(([key, label]) => (
                                                    <th key={key} className={`num ${benchmarkPeriod === key ? 'benchmark-col--active' : ''}`}>{label}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr className="benchmark-row--portfolio">
                                                <td><strong>Your Portfolio</strong></td>
                                                {(['1m', '3m', '6m', 'ytd', '1y', 'since_inception'] as (keyof BenchmarkReturns)[]).map(key => {
                                                    const val = benchmarkData.portfolio_return[key]
                                                    return <td key={key} className={`num ${benchmarkPeriod === key ? 'benchmark-col--active' : ''} ${val != null ? (val >= 0 ? 'positive' : 'negative') : ''}`}>
                                                        {val != null ? `${val >= 0 ? '+' : ''}${val.toFixed(2)}%` : '—'}
                                                    </td>
                                                })}
                                            </tr>
                                            {benchmarkData.benchmarks.map(bm => (
                                                <tr key={bm.ticker}>
                                                    <td>{bm.name}</td>
                                                    {(['1m', '3m', '6m', 'ytd', '1y', 'since_inception'] as (keyof BenchmarkReturns)[]).map(key => {
                                                        const val = bm.returns[key]
                                                        return <td key={key} className={`num ${benchmarkPeriod === key ? 'benchmark-col--active' : ''} ${val != null ? (val >= 0 ? 'positive' : 'negative') : ''}`}>
                                                            {val != null ? `${val >= 0 ? '+' : ''}${val.toFixed(2)}%` : '—'}
                                                        </td>
                                                    })}
                                                </tr>
                                            ))}
                                            {/* Outperformance row */}
                                            {benchmarkData.benchmarks.length > 0 && (
                                                <tr className="benchmark-row--diff">
                                                    <td>vs {benchmarkData.benchmarks[0].name}</td>
                                                    {(['1m', '3m', '6m', 'ytd', '1y', 'since_inception'] as (keyof BenchmarkReturns)[]).map(key => {
                                                        const pv = benchmarkData.portfolio_return[key]
                                                        const bv = benchmarkData.benchmarks[0].returns[key]
                                                        const diff = pv != null && bv != null ? pv - bv : null
                                                        return <td key={key} className={`num ${benchmarkPeriod === key ? 'benchmark-col--active' : ''} ${diff != null ? (diff >= 0 ? 'positive' : 'negative') : ''}`}>
                                                            {diff != null ? `${diff >= 0 ? '+' : ''}${diff.toFixed(2)}%` : '—'}
                                                        </td>
                                                    })}
                                                </tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>

                                {/* Return Breakdown */}
                                <div className="benchmark-breakdown">
                                    <h3 className="benchmark-breakdown__title">Return Breakdown (Since Inception)</h3>
                                    <div className="benchmark-breakdown__grid">
                                        <div className="benchmark-breakdown__item">
                                            <span className="benchmark-breakdown__label">Total Invested</span>
                                            <span className="benchmark-breakdown__value">${benchmarkData.total_invested.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                                        </div>
                                        <div className="benchmark-breakdown__item">
                                            <span className="benchmark-breakdown__label">Current Value</span>
                                            <span className="benchmark-breakdown__value">${benchmarkData.current_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                                        </div>
                                        <div className="benchmark-breakdown__item">
                                            <span className="benchmark-breakdown__label">Unrealized P&L</span>
                                            <span className={`benchmark-breakdown__value ${benchmarkData.unrealized_pnl >= 0 ? 'positive' : 'negative'}`}>{benchmarkData.unrealized_pnl >= 0 ? '+' : ''}${benchmarkData.unrealized_pnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                                        </div>
                                        <div className="benchmark-breakdown__item">
                                            <span className="benchmark-breakdown__label">Realized P&L</span>
                                            <span className={`benchmark-breakdown__value ${benchmarkData.realized_pnl >= 0 ? 'positive' : 'negative'}`}>{benchmarkData.realized_pnl >= 0 ? '+' : ''}${benchmarkData.realized_pnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                                        </div>
                                        <div className="benchmark-breakdown__item">
                                            <span className="benchmark-breakdown__label">Dividends</span>
                                            <span className="benchmark-breakdown__value positive">+${benchmarkData.dividend_income.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                                        </div>
                                        <div className="benchmark-breakdown__item benchmark-breakdown__item--total">
                                            <span className="benchmark-breakdown__label">Total Return</span>
                                            <span className={`benchmark-breakdown__value ${(benchmarkData.total_return_pct ?? 0) >= 0 ? 'positive' : 'negative'}`}>{benchmarkData.total_return_pct != null ? `${benchmarkData.total_return_pct >= 0 ? '+' : ''}${benchmarkData.total_return_pct}%` : '—'}</span>
                                        </div>
                                    </div>
                                </div>

                                <p className="benchmark-inception">Inception date: {benchmarkData.inception_date}</p>
                            </>
                        ) : (
                            <div className="portfolio-empty"><p>No benchmark data available. Import transactions to see performance comparison.</p></div>
                        )}
                    </div>
                )}

                {/* Add / Edit Modal */}
                {(showAddModal || editHolding) && (
                    <div className="modal-overlay" onClick={() => { setShowAddModal(false); resetForm() }}>
                        <div className="modal" onClick={e => e.stopPropagation()}>
                            <div className="modal__header">
                                <h3>{editHolding ? 'Edit Holding' : 'Add Holding'}</h3>
                                <button className="icon-btn" onClick={() => { setShowAddModal(false); resetForm() }}><X size={18} /></button>
                            </div>
                            <div className="modal__body">
                                <label>
                                    Ticker
                                    <input
                                        type="text"
                                        placeholder="e.g. AAPL"
                                        value={formTicker}
                                        onChange={e => setFormTicker(e.target.value.toUpperCase())}
                                        disabled={!!editHolding}
                                    />
                                </label>
                                <label>
                                    Shares
                                    <input
                                        type="number"
                                        placeholder="10"
                                        value={formShares}
                                        onChange={e => setFormShares(e.target.value)}
                                        min="0"
                                        step="any"
                                    />
                                </label>
                                <label>
                                    Avg Cost Basis ($)
                                    <input
                                        type="number"
                                        placeholder="150.00"
                                        value={formCost}
                                        onChange={e => setFormCost(e.target.value)}
                                        min="0"
                                        step="any"
                                    />
                                </label>
                            </div>
                            <div className="modal__footer">
                                <button className="btn btn--secondary" onClick={() => { setShowAddModal(false); resetForm() }}>Cancel</button>
                                <button className="btn btn--primary" onClick={editHolding ? handleUpdate : handleAdd}>
                                    {editHolding ? 'Save Changes' : 'Add'}
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Import CSV Modal */}
                {showImportModal && (
                    <div className="modal-overlay" onClick={closeImportModal}>
                        <div className="modal modal--import" onClick={e => e.stopPropagation()}>
                            <div className="modal__header">
                                <h3><Upload size={20} /> Import from Trading 212</h3>
                                <button className="icon-btn" onClick={closeImportModal}><X size={18} /></button>
                            </div>
                            <div className="modal__body">
                                {/* Success result */}
                                {importResult && !importResult.error && (
                                    <div className="import-result import-result--success">
                                        <CheckCircle size={24} />
                                        <div>
                                            <strong>Import Successful!</strong>
                                            <p>{importResult.new_transactions} new transaction{importResult.new_transactions !== 1 ? 's' : ''} imported, {importResult.skipped} skipped (duplicates).</p>
                                            <p className="import-result__detail">{importResult.holdings_count} active holdings · {importResult.total_in_csv} total rows parsed.</p>
                                        </div>
                                    </div>
                                )}

                                {/* Error result */}
                                {importResult?.error && (
                                    <div className="import-result import-result--error">
                                        <AlertCircle size={24} />
                                        <div>
                                            <strong>Import Failed</strong>
                                            <p>{importResult.error}</p>
                                        </div>
                                    </div>
                                )}

                                {/* File dropzone (shown when no success result yet) */}
                                {(!importResult || importResult.error) && (
                                    <>
                                        <p className="import-instructions">
                                            Export your transaction history from Trading 212 as CSV:<br />
                                            <strong>History → Export → CSV</strong>
                                        </p>
                                        <div
                                            className={`import-dropzone ${dragOver ? 'import-dropzone--active' : ''} ${importFile ? 'import-dropzone--has-file' : ''}`}
                                            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                                            onDragLeave={() => setDragOver(false)}
                                            onDrop={handleDrop}
                                            onClick={() => fileInputRef.current?.click()}
                                        >
                                            <input
                                                ref={fileInputRef}
                                                type="file"
                                                accept=".csv"
                                                style={{ display: 'none' }}
                                                onChange={e => {
                                                    const f = e.target.files?.[0]
                                                    if (f) handleImportFile(f)
                                                }}
                                            />
                                            {importFile ? (
                                                <div className="import-dropzone__file">
                                                    <FileText size={28} />
                                                    <span>{importFile.name}</span>
                                                    <span className="import-dropzone__size">{(importFile.size / 1024).toFixed(1)} KB</span>
                                                </div>
                                            ) : (
                                                <div className="import-dropzone__prompt">
                                                    <Upload size={32} />
                                                    <span>Drop CSV file here or click to browse</span>
                                                </div>
                                            )}
                                        </div>
                                    </>
                                )}
                            </div>
                            <div className="modal__footer">
                                <button className="btn btn--secondary" onClick={closeImportModal}>
                                    {importResult && !importResult.error ? 'Done' : 'Cancel'}
                                </button>
                                {(!importResult || importResult.error) && (
                                    <button
                                        className="btn btn--primary"
                                        onClick={handleImportConfirm}
                                        disabled={!importFile || importLoading}
                                    >
                                        {importLoading ? (
                                            <><RefreshCw size={16} className="spin" /> Importing...</>
                                        ) : (
                                            <><Upload size={16} /> Import</>
                                        )}
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </main>
    )
}

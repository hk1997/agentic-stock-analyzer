import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { apiFetch } from '../../utils/api'
import {
    Target,
    Home,
    Car,
    Shield,
    Plane,
    DollarSign,
    Plus,
    Trash2,
    Clock,
    X,
    TrendingUp,
    Calendar,
    Users,
    User,
    ChevronRight,
    ArrowUpRight,
    HelpCircle,
    Edit3
} from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts'

interface Contribution {
    id: number
    goal_id: number
    contributor_id: number
    contributor_name: string
    amount: number
    date: string
    description: string | null
}

interface Goal {
    id: number
    owner_id: number
    owner_name: string
    title: string
    category: string
    target_amount: number
    target_date: string
    linked_asset_type: string | null
    linked_asset_id: number | null
    income_sources: string | null
    cash_flows: string | null
    created_at: string
    contributions: Contribution[]
    total_manual_saved: number
    linked_asset_value: number
    total_saved: number
    progress_percent: number
    partner_breakdown: Record<string, number>
    savings_velocity: number
    run_rate_months: number | null
    status: 'Complete' | 'On Track' | 'Behind'
}

interface PortfolioItem {
    id: number
    name: string
}

interface ManualAssetItem {
    id: number
    asset_type: string
    value: number
    description: string | null
}

export function GoalsPage() {
    // Currency selection states
    const [currency, setCurrency] = useState<string>(() => {
        return localStorage.getItem('goals_currency') || 'USD'
    })
    const [exchangeRates, setExchangeRates] = useState<any>({
        USD_TO_GBP: 1.0 / 1.27,
        USD_TO_INR: 1.0 / 0.012,
        USD_TO_EUR: 1.0 / 1.08
    })

    useEffect(() => {
        localStorage.setItem('goals_currency', currency)
    }, [currency])

    const getCurrencySymbol = useCallback((curr: string) => {
        switch (curr.toUpperCase()) {
            case 'INR': return '₹'
            case 'GBP': return '£'
            case 'EUR': return '€'
            default: return '$'
        }
    }, [])

    const convertFromUSD = useCallback((amountUsd: number) => {
        if (currency === 'USD') return amountUsd
        const rateKey = `USD_TO_${currency}`
        const rate = exchangeRates[rateKey] || 1.0
        return amountUsd * rate
    }, [currency, exchangeRates])

    const convertToUSD = useCallback((amountForeign: number) => {
        if (currency === 'USD') return amountForeign
        const rateKey = `USD_TO_${currency}`
        const rate = exchangeRates[rateKey] || 1.0
        return rate > 0 ? amountForeign / rate : amountForeign
    }, [currency, exchangeRates])

    const formatValue = useCallback((amountUsd: number, options: Intl.NumberFormatOptions = { maximumFractionDigits: 0 }) => {
        const converted = convertFromUSD(amountUsd)
        const symbol = getCurrencySymbol(currency)
        return `${symbol}${converted.toLocaleString(undefined, options)}`
    }, [currency, convertFromUSD, getCurrencySymbol])

    // List states
    const [goals, setGoals] = useState<Goal[]>([])
    const [portfolios, setPortfolios] = useState<PortfolioItem[]>([])
    const [manualAssets, setManualAssets] = useState<ManualAssetItem[]>([])
    const [accounts, setAccounts] = useState<any[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    // Form modals
    const [showAddGoalModal, setShowAddGoalModal] = useState(false)
    const [showEditGoalModal, setShowEditGoalModal] = useState(false)
    const [showAddContribModal, setShowAddContribModal] = useState(false)
    const [selectedGoal, setSelectedGoal] = useState<Goal | null>(null)
    const [editingGoal, setEditingGoal] = useState<Goal | null>(null)

    // Form inputs: Goal
    const [goalTitle, setGoalTitle] = useState('')
    const [goalCategory, setGoalCategory] = useState('House')
    const [goalTargetAmount, setGoalTargetAmount] = useState('')
    const [goalTargetDate, setGoalTargetDate] = useState('')
    const [goalLinkedAssetType, setGoalLinkedAssetType] = useState<string>('none')
    const [goalLinkedAssetId, setGoalLinkedAssetId] = useState<string>('')
    const [goalIncomeSources, setGoalIncomeSources] = useState('')

    // Form inputs: Contribution
    const [contribAmount, setContribAmount] = useState('')
    const [contribDescription, setContribDescription] = useState('')
    const [contribDate, setContribDate] = useState('')

    // Detail drawer state
    const [activeDetailGoal, setActiveDetailGoal] = useState<Goal | null>(null)
    const [calculatorVelocity, setCalculatorVelocity] = useState<number>(0)

    // Cooperative Cash Flow states
    const [continuousYou, setContinuousYou] = useState<number>(0)
    const [continuousPartner, setContinuousPartner] = useState<number>(0)
    const [nonContinuousList, setNonContinuousList] = useState<any[]>([])
    const [isSavingPlan, setIsSavingPlan] = useState(false)

    // Add One-off Cash Flow form states
    const [oneOffLabel, setOneOffLabel] = useState('')
    const [oneOffAmount, setOneOffAmount] = useState('')
    const [oneOffMonthOffset, setOneOffMonthOffset] = useState<number>(1)
    const [oneOffOwner, setOneOffOwner] = useState('You')

    // Fetch lists
    const fetchAllData = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const [goalsData, portfoliosData, assetsData, accountsData, ratesData] = await Promise.all([
                apiFetch('/api/finance/goals'),
                apiFetch('/api/portfolio').catch(() => []),
                apiFetch('/api/finance/manual-assets').catch(() => []),
                apiFetch('/api/finance/accounts').catch(() => []),
                apiFetch('/api/finance/exchange-rates').catch(() => null)
            ])
            setGoals(goalsData)
            setPortfolios(portfoliosData)
            setManualAssets(assetsData)
            setAccounts(accountsData)
            if (ratesData) {
                setExchangeRates(ratesData)
            }
        } catch (err: any) {
            setError(err.message || 'Failed to load goals data')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        fetchAllData()
    }, [fetchAllData])

    // Calculator velocity setter and cash flow initializers when active goal changes
    useEffect(() => {
        if (activeDetailGoal) {
            setCalculatorVelocity(Math.round(activeDetailGoal.savings_velocity || 100))
            
            try {
                const parsed = activeDetailGoal.cash_flows ? JSON.parse(activeDetailGoal.cash_flows) : []
                
                // Continuous continuous amounts
                const youCont = parsed.find((c: any) => c.owner === 'You' && c.type === 'continuous')?.amount || 0
                const partnerName = Object.keys(activeDetailGoal.partner_breakdown).find(k => k !== 'You') || 'Partner'
                const partnerCont = parsed.find((c: any) => c.owner === partnerName && c.type === 'continuous')?.amount || 0
                
                setContinuousYou(Math.round(convertFromUSD(youCont)))
                setContinuousPartner(Math.round(convertFromUSD(partnerCont)))
                
                // Filter non-continuous cash flows
                const nonCont = parsed.filter((c: any) => c.type === 'non_continuous').map((c: any) => ({
                    ...c,
                    amount: convertFromUSD(c.amount)
                }))
                setNonContinuousList(nonCont)
            } catch (e) {
                console.error("Failed to parse cash flows", e)
                setContinuousYou(0)
                setContinuousPartner(0)
                setNonContinuousList([])
            }
        }
    }, [activeDetailGoal, currency, convertFromUSD])

    // KPI Metrics calculation
    const metrics = useMemo(() => {
        if (!goals.length) return { totalTargets: 0, totalSaved: 0, overallProgress: 0, velocity: 0 }
        const totalTargets = goals.reduce((sum, g) => sum + g.target_amount, 0)
        const totalSaved = goals.reduce((sum, g) => sum + g.total_saved, 0)
        const overallProgress = totalTargets > 0 ? (totalSaved / totalTargets) * 100 : 0
        const velocity = goals.reduce((sum, g) => sum + g.savings_velocity, 0)
        return { totalTargets, totalSaved, overallProgress, velocity }
    }, [goals])

    // Category Icon resolver
    const getCategoryIcon = (category: string) => {
        switch (category) {
            case 'House':
                return <Home size={22} />
            case 'Car':
                return <Car size={22} />
            case 'Emergency Fund':
                return <Shield size={22} />
            case 'Vacation':
                return <Plane size={22} />
            default:
                return <Target size={22} />
        }
    }

    // Submit actions
    const handleAddGoal = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!goalTitle || !goalTargetAmount || !goalTargetDate) return
        
        setError(null)
        try {
            await apiFetch('/api/finance/goals', {
                method: 'POST',
                body: JSON.stringify({
                    title: goalTitle,
                    category: goalCategory,
                    target_amount: convertToUSD(parseFloat(goalTargetAmount)),
                    target_date: new Date(goalTargetDate).toISOString(),
                    linked_asset_type: goalLinkedAssetType === 'none' ? null : goalLinkedAssetType,
                    linked_asset_id: goalLinkedAssetId ? parseInt(goalLinkedAssetId) : null,
                    income_sources: goalIncomeSources || null
                })
            })
            // Reset
            setGoalTitle('')
            setGoalCategory('House')
            setGoalTargetAmount('')
            setGoalTargetDate('')
            setGoalLinkedAssetType('none')
            setGoalLinkedAssetId('')
            setGoalIncomeSources('')
            setShowAddGoalModal(false)
            fetchAllData()
        } catch (err: any) {
            setError(err.message || 'Failed to create goal')
        }
    }

    const handleAddContribution = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!selectedGoal || !contribAmount) return

        setError(null)
        try {
            await apiFetch(`/api/finance/goals/${selectedGoal.id}/contributions`, {
                method: 'POST',
                body: JSON.stringify({
                    amount: convertToUSD(parseFloat(contribAmount)),
                    date: contribDate ? new Date(contribDate).toISOString() : null,
                    description: contribDescription || null
                })
            })
            // Reset
            setContribAmount('')
            setContribDescription('')
            setContribDate('')
            setShowAddContribModal(false)
            setSelectedGoal(null)
            fetchAllData()
            
            // Refresh detail drawer if it is currently open for this goal
            if (activeDetailGoal && activeDetailGoal.id === selectedGoal.id) {
                const refreshedGoals = await apiFetch('/api/finance/goals')
                setGoals(refreshedGoals)
                const updated = refreshedGoals.find((g: Goal) => g.id === selectedGoal.id)
                if (updated) setActiveDetailGoal(updated)
            }
        } catch (err: any) {
            setError(err.message || 'Failed to add contribution')
        }
    }

    const handleDeleteGoal = async (goalId: number) => {
        if (!confirm('Are you sure you want to delete this financial goal?')) return
        try {
            await apiFetch(`/api/finance/goals/${goalId}`, { method: 'DELETE' })
            fetchAllData()
            if (activeDetailGoal?.id === goalId) {
                setActiveDetailGoal(null)
            }
        } catch (err: any) {
            setError(err.message || 'Failed to delete goal')
        }
    }

    const handleDeleteContribution = async (goalId: number, contribId: number) => {
        if (!confirm('Delete this contribution transaction?')) return
        try {
            await apiFetch(`/api/finance/goals/${goalId}/contributions/${contribId}`, { method: 'DELETE' })
            // Refresh
            const refreshedGoals = await apiFetch('/api/finance/goals')
            setGoals(refreshedGoals)
            if (activeDetailGoal) {
                const updated = refreshedGoals.find((g: Goal) => g.id === goalId)
                if (updated) setActiveDetailGoal(updated)
            }
        } catch (err: any) {
            setError(err.message || 'Failed to delete contribution')
        }
    }

    const openEditGoal = (goal: Goal) => {
        setEditingGoal(goal)
        setGoalTitle(goal.title)
        setGoalCategory(goal.category)
        setGoalTargetAmount(String(Math.round(convertFromUSD(goal.target_amount))))
        const formattedDate = goal.target_date ? goal.target_date.split('T')[0] : ''
        setGoalTargetDate(formattedDate)
        setGoalLinkedAssetType(goal.linked_asset_type || 'none')
        setGoalLinkedAssetId(goal.linked_asset_id ? String(goal.linked_asset_id) : '')
        setGoalIncomeSources(goal.income_sources || '')
        setShowEditGoalModal(true)
    }

    const handleEditGoalSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!editingGoal || !goalTitle || !goalTargetAmount || !goalTargetDate) return

        setError(null)
        try {
            await apiFetch(`/api/finance/goals/${editingGoal.id}`, {
                method: 'PATCH',
                body: JSON.stringify({
                    title: goalTitle,
                    category: goalCategory,
                    target_amount: convertToUSD(parseFloat(goalTargetAmount)),
                    target_date: new Date(goalTargetDate).toISOString(),
                    linked_asset_type: goalLinkedAssetType === 'none' ? null : goalLinkedAssetType,
                    linked_asset_id: goalLinkedAssetId ? parseInt(goalLinkedAssetId) : null,
                    income_sources: goalIncomeSources || null
                })
            })
            // Reset
            setGoalTitle('')
            setGoalCategory('House')
            setGoalTargetAmount('')
            setGoalTargetDate('')
            setGoalLinkedAssetType('none')
            setGoalLinkedAssetId('')
            setGoalIncomeSources('')
            setShowEditGoalModal(false)
            setEditingGoal(null)
            fetchAllData()
            
            // Refresh details drawer if open
            if (activeDetailGoal && activeDetailGoal.id === editingGoal.id) {
                const refreshedGoals = await apiFetch('/api/finance/goals')
                setGoals(refreshedGoals)
                const updated = refreshedGoals.find((g: Goal) => g.id === editingGoal.id)
                if (updated) setActiveDetailGoal(updated)
            }
        } catch (err: any) {
            setError(err.message || 'Failed to update goal')
        }
    }

    // Cumulative savings timeline chart calculations
    const chartData = useMemo(() => {
        if (!activeDetailGoal) return []
        
        // Sort contributions chronologically
        const sortedContribs = [...activeDetailGoal.contributions].sort(
            (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
        )
        
        let cumulative = activeDetailGoal.linked_asset_value
        const points = []
        
        // Initial point: creation date of the goal
        points.push({
            date: new Date(activeDetailGoal.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
            amount: convertFromUSD(cumulative)
        })

        for (const c of sortedContribs) {
            cumulative += c.amount
            points.push({
                date: new Date(c.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
                amount: convertFromUSD(cumulative)
            })
        }
        
        // Add final point representing today
        points.push({
            date: 'Today',
            amount: convertFromUSD(cumulative)
        })
        
        return points
    }, [activeDetailGoal, convertFromUSD])

    // Forecast calculation inside slider drawer
    const projectionDate = useMemo(() => {
        if (!activeDetailGoal) return ''
        const remaining = activeDetailGoal.target_amount - activeDetailGoal.total_saved
        if (remaining <= 0) return 'Already Reached!'
        if (calculatorVelocity <= 0) return 'Never (Savings rate too low)'
        
        const months = remaining / calculatorVelocity
        const targetDate = new Date()
        targetDate.setMonth(targetDate.getMonth() + Math.ceil(months))
        return targetDate.toLocaleDateString(undefined, { year: 'numeric', month: 'long' })
    }, [activeDetailGoal, calculatorVelocity])

    // Projected savings curve calculation (real-time forecasting)
    const projectionChartData = useMemo(() => {
        if (!activeDetailGoal) return { points: [], reachedDateStr: '', shortAmount: 0, monthsToTarget: 0 }
        
        const partnerName = Object.keys(activeDetailGoal.partner_breakdown).find(k => k !== 'You') || 'Partner'
        const points = []
        
        let cumulative = convertFromUSD(activeDetailGoal.total_saved)
        const target = convertFromUSD(activeDetailGoal.target_amount)
        const targetDate = new Date(activeDetailGoal.target_date)
        const today = new Date()
        
        // Calculate months between today and target date
        let monthsToTarget = 12
        if (targetDate > today) {
            monthsToTarget = Math.max(1, (targetDate.getFullYear() - today.getFullYear()) * 12 + (targetDate.getMonth() - today.getMonth()))
        }
        
        // Let's project up to targetDate (or until target reached + 6 months, max 60 months)
        const maxMonths = Math.min(60, Math.max(monthsToTarget + 6, 12))
        
        let reachedMonth: number | null = null
        
        // Start point (Month 0 - Today)
        points.push({
            monthIndex: 0,
            dateStr: 'Today',
            amount: Math.round(cumulative),
            target: target
        })
        
        for (let m = 1; m <= maxMonths; m++) {
            // Add continuous savings
            cumulative += Number(continuousYou || 0)
            cumulative += Number(continuousPartner || 0)
            
            // Add non-continuous one-off inflows scheduled for this month
            const oneOffs = nonContinuousList.filter((c: any) => c.monthOffset === m)
            const oneOffSum = oneOffs.reduce((sum, c) => sum + Number(c.amount || 0), 0)
            cumulative += oneOffSum
            
            // Generate dynamic month name
            const projectDate = new Date()
            projectDate.setMonth(today.getMonth() + m)
            const dateStr = projectDate.toLocaleDateString(undefined, { month: 'short', year: 'numeric' })
            
            points.push({
                monthIndex: m,
                dateStr,
                amount: Math.round(cumulative),
                target: target,
                continuousYou: Number(continuousYou || 0),
                continuousPartner: Number(continuousPartner || 0),
                oneOffSum: oneOffSum
            })
            
            if (cumulative >= target && reachedMonth === null) {
                reachedMonth = m
            }
        }
        
        let reachedDateStr = ''
        let shortAmount = 0
        
        if (reachedMonth !== null) {
            const dateReached = new Date()
            dateReached.setMonth(today.getMonth() + reachedMonth)
            reachedDateStr = dateReached.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
        } else {
            // Find projected amount at targetDate month
            const targetMonthPoint = points.find(p => p.monthIndex === monthsToTarget)
            const projectedAtTarget = targetMonthPoint ? targetMonthPoint.amount : cumulative
            if (projectedAtTarget < target) {
                shortAmount = Math.max(0, target - projectedAtTarget)
            }
        }
        
        return {
            points,
            reachedDateStr,
            shortAmount,
            monthsToTarget
        }
    }, [activeDetailGoal, continuousYou, continuousPartner, nonContinuousList, convertFromUSD])

    const handleAddOneOff = (e: React.FormEvent) => {
        e.preventDefault()
        if (!oneOffAmount || !oneOffLabel) return
        
        const newFlow = {
            id: String(Date.now()),
            owner: oneOffOwner,
            type: 'non_continuous',
            amount: parseFloat(oneOffAmount),
            label: oneOffLabel,
            monthOffset: Number(oneOffMonthOffset)
        }
        
        setNonContinuousList(prev => [...prev, newFlow])
        setOneOffLabel('')
        setOneOffAmount('')
    }

    const handleRemoveOneOff = (id: string) => {
        setNonContinuousList(prev => prev.filter(c => c.id !== id))
    }

    const handleSaveCashFlows = async () => {
        if (!activeDetailGoal) return
        
        setIsSavingPlan(true)
        setError(null)
        
        const partnerName = Object.keys(activeDetailGoal.partner_breakdown).find(k => k !== 'You') || 'Partner'
        
        const fullFlows = [
            {
                id: 'cont-you',
                owner: 'You',
                type: 'continuous',
                amount: convertToUSD(Number(continuousYou || 0)),
                label: 'Continuous savings'
            },
            {
                id: 'cont-partner',
                owner: partnerName,
                type: 'continuous',
                amount: convertToUSD(Number(continuousPartner || 0)),
                label: 'Continuous savings'
            },
            ...nonContinuousList.map(c => ({
                ...c,
                amount: convertToUSD(c.amount)
            }))
        ]
        
        try {
            await apiFetch(`/api/finance/goals/${activeDetailGoal.id}`, {
                method: 'PATCH',
                body: JSON.stringify({
                    cash_flows: JSON.stringify(fullFlows)
                })
            })
            
            // Refresh local goals list
            const refreshedGoals = await apiFetch('/api/finance/goals')
            setGoals(refreshedGoals)
            
            // Refresh current selected goal details
            const updated = refreshedGoals.find((g: Goal) => g.id === activeDetailGoal.id)
            if (updated) {
                setActiveDetailGoal(updated)
            }
            alert('Cooperative savings plan saved successfully!')
        } catch (err: any) {
            setError(err.message || 'Failed to save savings plan')
        } finally {
            setIsSavingPlan(false)
        }
    }

    const getMonthNameFromOffset = (offset: number) => {
        const d = new Date()
        d.setMonth(d.getMonth() + offset)
        return d.toLocaleDateString(undefined, { month: 'short', year: 'numeric' })
    }

    if (loading && !goals.length) {
        return (
            <main className="main-content">
                <div style={{ display: 'flex', flexDirection: 'column', height: '80vh', justifyContent: 'center', alignItems: 'center', color: 'var(--text-secondary)' }}>
                    <div className="agent-step__spinner" style={{ width: 32, height: 32, marginBottom: '1rem' }} />
                    <p>Loading cooperative goals...</p>
                </div>
            </main>
        )
    }

    return (
        <main className="main-content">
            <div style={{ paddingBottom: '3rem' }}>
                
                {/* Header */}
                <div className="portfolio-header">
                    <div className="portfolio-header__left">
                        <Users size={28} />
                        <div>
                            <h1>Joint Financial Goals</h1>
                            <p className="portfolio-header__subtitle">Cooperative wealth tracking for you and your partner</p>
                        </div>
                    </div>
                    <div className="portfolio-header__actions" style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                        <select
                            value={currency}
                            onChange={(e) => setCurrency(e.target.value)}
                            className="chat-input__field"
                            style={{
                                width: '100px',
                                padding: '0.45rem 0.75rem',
                                fontSize: '0.85rem',
                                background: 'rgba(255, 255, 255, 0.05)',
                                border: '1px solid var(--glass-border)',
                                borderRadius: '10px',
                                color: 'var(--text-primary)',
                                cursor: 'pointer'
                            }}
                        >
                            <option value="USD" style={{ background: 'var(--bg-surface)' }}>USD ($)</option>
                            <option value="GBP" style={{ background: 'var(--bg-surface)' }}>GBP (£)</option>
                            <option value="INR" style={{ background: 'var(--bg-surface)' }}>INR (₹)</option>
                            <option value="EUR" style={{ background: 'var(--bg-surface)' }}>EUR (€)</option>
                        </select>
                        <button className="btn btn--primary" onClick={() => setShowAddGoalModal(true)}>
                            <Plus size={16} /> Add New Goal
                        </button>
                    </div>
                </div>

                {error && <div className="portfolio-error" style={{ marginBottom: '1.5rem' }}>{error}</div>}

                {/* KPI Cards Row */}
                <div className="portfolio-summary" style={{ marginBottom: '2rem' }}>
                    <div className="summary-card">
                        <div className="summary-card__icon"><Target size={20} /></div>
                        <div className="summary-card__content">
                            <span className="summary-card__label">Total Milestones Target</span>
                            <span className="summary-card__value">{formatValue(metrics.totalTargets)}</span>
                        </div>
                    </div>
                    <div className="summary-card">
                        <div className="summary-card__icon positive"><DollarSign size={20} /></div>
                        <div className="summary-card__content">
                            <span className="summary-card__label">Total Jointly Saved</span>
                            <span className="summary-card__value">{formatValue(metrics.totalSaved)}</span>
                        </div>
                    </div>
                    <div className="summary-card">
                        <div className="summary-card__icon"><TrendingUp size={20} /></div>
                        <div className="summary-card__content">
                            <span className="summary-card__label">Joint Monthly Velocity</span>
                            <span className="summary-card__value">{formatValue(metrics.velocity)}/mo</span>
                        </div>
                    </div>
                    <div className="summary-card">
                        <div className="summary-card__icon positive" style={{ color: 'var(--accent)' }}><Users size={20} /></div>
                        <div className="summary-card__content">
                            <span className="summary-card__label">Overall Combined Progress</span>
                            <span className="summary-card__value">{metrics.overallProgress.toFixed(1)}%</span>
                        </div>
                    </div>
                </div>

                {/* Goals Grid */}
                {!goals.length ? (
                    <div className="portfolio-card" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                        <Target size={48} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />
                        <h3>No Active Goals Yet</h3>
                        <p style={{ marginTop: '0.5rem', marginBottom: '1.5rem', fontSize: '0.9rem' }}>Create a savings target to begin contributing jointly with your partner.</p>
                        <button className="btn btn--primary" onClick={() => setShowAddGoalModal(true)}>
                            <Plus size={16} /> Create Goal
                        </button>
                    </div>
                ) : (
                    <div className="goals-grid">
                        {goals.map(goal => {
                            // Calculate remaining balance
                            const remaining = goal.target_amount - goal.total_saved
                            const daysToTarget = Math.max(0, Math.ceil((new Date(goal.target_date).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24)))
                            const monthsToTarget = (daysToTarget / 30).toFixed(1)

                            // Status color resolver
                            let statusColor = 'var(--text-muted)'
                            if (goal.status === 'Complete') statusColor = 'var(--bullish)'
                            else if (goal.status === 'On Track') statusColor = 'var(--accent)'
                            else if (goal.status === 'Behind') statusColor = '#ffb300'

                            return (
                                <div key={goal.id} className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', position: 'relative' }}>
                                    
                                    {/* Card Top */}
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                                            <div style={{
                                                width: '42px', height: '42px', borderRadius: '10px',
                                                background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--glass-border)',
                                                display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent)'
                                            }}>
                                                {getCategoryIcon(goal.category)}
                                            </div>
                                            <div>
                                                <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>{goal.title}</h3>
                                                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem', marginTop: '0.15rem' }}>
                                                    <Calendar size={12} /> Target: {new Date(goal.target_date).toLocaleDateString(undefined, { year: 'numeric', month: 'short' })}
                                                </span>
                                                {goal.income_sources && (
                                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem', marginTop: '0.4rem' }}>
                                                        {goal.income_sources.split(',').map(s => s.trim()).filter(Boolean).map(source => (
                                                            <span key={source} style={{
                                                                fontSize: '0.62rem', background: 'rgba(255,255,255,0.04)',
                                                                border: '1px solid var(--glass-border)', padding: '0.05rem 0.35rem',
                                                                borderRadius: '4px', color: 'var(--text-secondary)'
                                                            }}>
                                                                {source}
                                                            </span>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                        <span className="badge" style={{ color: statusColor, background: `rgba(255,255,255,0.02)`, border: `1px solid ${statusColor}44` }}>
                                            {goal.status}
                                        </span>
                                    </div>

                                    {/* Main Progress Bar */}
                                    <div>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '0.5rem' }}>
                                            <span style={{ color: 'var(--text-secondary)' }}>Saved: <strong>{formatValue(goal.total_saved)}</strong></span>
                                            <span style={{ color: 'var(--text-muted)' }}>Target: {formatValue(goal.target_amount)}</span>
                                        </div>
                                        <div style={{ height: '8px', background: 'rgba(255, 255, 255, 0.05)', borderRadius: '4px', overflow: 'hidden' }}>
                                            <div style={{
                                                height: '100%',
                                                width: `${goal.progress_percent}%`,
                                                background: 'var(--accent-gradient)',
                                                boxShadow: '0 0 8px rgba(0, 242, 254, 0.3)',
                                                borderRadius: '4px',
                                                transition: 'width 0.4s ease'
                                            }} />
                                        </div>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>
                                            <span>{goal.progress_percent.toFixed(0)}% Completed</span>
                                            {remaining > 0 ? (
                                                <span>{formatValue(remaining)} left</span>
                                            ) : (
                                                <span style={{ color: 'var(--bullish)', fontWeight: 600 }}>Goal Reached! 🎉</span>
                                            )}
                                        </div>
                                    </div>

                                    {/* Partner Split Progress Bar */}
                                    {goal.total_manual_saved > 0 && (
                                        <div style={{ background: 'rgba(255, 255, 255, 0.015)', border: '1px solid var(--glass-border)', padding: '0.75rem', borderRadius: '10px' }}>
                                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: '0.5rem' }}>
                                                Partner Contribution Split
                                            </span>
                                            <div style={{ display: 'flex', height: '6px', borderRadius: '3px', overflow: 'hidden', marginBottom: '0.4rem' }}>
                                                {Object.entries(goal.partner_breakdown).map(([name, amount], index) => {
                                                    const pct = goal.total_manual_saved > 0 ? (amount / goal.total_manual_saved) * 100 : 0
                                                    if (pct === 0) return null
                                                    
                                                    // Assign different colors to split sides
                                                    const color = index === 0 ? 'var(--accent)' : 'var(--accent-purple)'
                                                    return (
                                                        <div key={name} style={{ width: `${pct}%`, background: color, height: '100%' }} title={`${name}: ${formatValue(amount)}`} />
                                                    )
                                                })}
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                                {Object.entries(goal.partner_breakdown).map(([name, amount], index) => {
                                                    const pct = goal.total_manual_saved > 0 ? (amount / goal.total_manual_saved) * 100 : 0
                                                    const color = index === 0 ? 'var(--accent)' : 'var(--accent-purple)'
                                                    return (
                                                        <span key={name} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                                            <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: color }} />
                                                            {name}: {pct.toFixed(0)}%
                                                        </span>
                                                    )
                                                })}
                                            </div>
                                        </div>
                                    )}

                                    {/* Forecast info */}
                                    {remaining > 0 && (
                                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', fontSize: '0.8rem', color: 'var(--text-secondary)', borderTop: '1px solid rgba(255,255,255,0.03)', paddingTop: '0.75rem' }}>
                                            <Clock size={14} style={{ color: 'var(--text-muted)' }} />
                                            <span>
                                                Pace: <strong>{formatValue(goal.savings_velocity)}/mo</strong>.
                                                {goal.run_rate_months !== null ? (
                                                    <span> Estimated completion in <strong>{goal.run_rate_months.toFixed(1)} months</strong> ({monthsToTarget} months target).</span>
                                                ) : (
                                                    <span> No velocity recorded. Save monthly to get projections.</span>
                                                )}
                                            </span>
                                        </div>
                                    )}

                                    {/* Action Buttons */}
                                    <div style={{ display: 'flex', gap: '0.75rem', marginTop: 'auto' }}>
                                        {remaining > 0 && (
                                            <button className="btn btn--primary" style={{ flex: 1, padding: '0.45rem 1rem' }} onClick={() => { setSelectedGoal(goal); setShowAddContribModal(true) }}>
                                                Save Money
                                            </button>
                                        )}
                                        <button className="btn btn--secondary" style={{ flex: 1, padding: '0.45rem 1rem' }} onClick={() => setActiveDetailGoal(goal)}>
                                            Insights
                                        </button>
                                        <button className="icon-btn" style={{ padding: '0.5rem', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--glass-border)' }} onClick={() => openEditGoal(goal)} title="Edit Goal">
                                            <Edit3 size={16} />
                                        </button>
                                        <button className="icon-btn icon-btn--danger" style={{ padding: '0.5rem', borderRadius: '10px' }} onClick={() => handleDeleteGoal(goal.id)} title="Delete Goal">
                                            <Trash2 size={16} />
                                        </button>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                )}
            </div>

            {/* DETAIL DRAWER / SLIDE-IN PANEL */}
            {activeDetailGoal && (
                <>
                    <div className="drawer-backdrop" onClick={() => setActiveDetailGoal(null)} />
                    <div className="details-drawer">
                        <div className="drawer-handle" />
                        {/* Header */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--glass-border)', paddingBottom: '1rem' }}>
                            <div>
                                <h2 style={{ fontSize: '1.3rem', fontWeight: 700 }}>{activeDetailGoal.title}</h2>
                                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>Goal Insights & Transaction Ledger</p>
                            </div>
                            <button className="icon-btn" onClick={() => setActiveDetailGoal(null)} style={{ padding: '0.5rem', borderRadius: '50%' }}>
                                <X size={20} />
                            </button>
                        </div>

                        {/* Progress details */}
                        <div className="grid-2-col">
                            <div className="glass-panel" style={{ padding: '1rem', textAlign: 'center' }}>
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>TOTAL TARGET</span>
                                <h3 style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '0.25rem' }}>{formatValue(activeDetailGoal.target_amount)}</h3>
                            </div>
                            <div className="glass-panel" style={{ padding: '1rem', textAlign: 'center' }}>
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>TOTAL SAVED</span>
                                <h3 style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '0.25rem', color: 'var(--accent)' }}>{formatValue(activeDetailGoal.total_saved)}</h3>
                            </div>
                        </div>

                    {/* Potential Income Sources (pills) */}
                    {activeDetailGoal.income_sources && (
                        <div className="glass-panel" style={{ padding: '1rem' }}>
                            <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.6rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Potential Income Sources</h4>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                                {activeDetailGoal.income_sources.split(',').map(s => s.trim()).filter(Boolean).map(source => (
                                    <span key={source} style={{
                                        fontSize: '0.75rem', background: 'rgba(0, 242, 254, 0.06)',
                                        border: '1px solid rgba(0, 242, 254, 0.2)', padding: '0.2rem 0.5rem',
                                        borderRadius: '6px', color: 'var(--accent)'
                                    }}>
                                        {source}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Recharts Area Chart */}
                    <div className="glass-panel" style={{ padding: '1rem' }}>
                        <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Cooperative Savings Growth</h4>
                        {chartData.length > 0 ? (
                            <div style={{ width: '100%', height: 180 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                        <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={10} tickLine={false} />
                                        <YAxis stroke="var(--text-muted)" fontSize={10} tickLine={false} tickFormatter={(val) => `${getCurrencySymbol(currency)}${val.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} />
                                        <RechartsTooltip formatter={(value: number) => `${getCurrencySymbol(currency)}${value.toLocaleString()}`} contentStyle={{ background: '#10101c', border: '1px solid var(--glass-border)', color: '#fff', borderRadius: 8 }} />
                                        <Area type="monotone" dataKey="amount" stroke="var(--accent)" fill="rgba(0, 242, 254, 0.08)" strokeWidth={2} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        ) : (
                            <p style={{ textAlign: 'center', fontSize: '0.85rem', color: 'var(--text-muted)' }}>No transaction history to chart</p>
                        )}
                    </div>

                    {/* Cooperative Cash Flow Planner & Forecast */}
                    <div className="glass-panel" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--glass-border)', paddingBottom: '0.75rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <TrendingUp size={18} style={{ color: 'var(--accent)' }} />
                                <h4 style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                    Cooperative Forecast & Plan
                                </h4>
                            </div>
                            <button
                                type="button"
                                className="btn btn--primary"
                                style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem', borderRadius: '15px' }}
                                onClick={handleSaveCashFlows}
                                disabled={isSavingPlan}
                            >
                                {isSavingPlan ? 'Saving...' : 'Save Plan'}
                            </button>
                        </div>

                        {/* Status Message */}
                        {projectionChartData.reachedDateStr ? (
                            <div style={{
                                padding: '0.75rem', borderRadius: '8px', fontSize: '0.8rem',
                                background: 'rgba(0, 242, 254, 0.04)', border: '1px solid rgba(0, 242, 254, 0.15)',
                                color: 'var(--accent)'
                            }}>
                                🎉 <strong>On Track!</strong> Projected to reach target of <strong>{formatValue(activeDetailGoal.target_amount)}</strong> in <strong>{projectionChartData.reachedDateStr}</strong>.
                            </div>
                        ) : (
                            <div style={{
                                padding: '0.75rem', borderRadius: '8px', fontSize: '0.8rem',
                                background: 'rgba(255, 71, 87, 0.05)', border: '1px solid rgba(255, 71, 87, 0.15)',
                                color: '#ff4757'
                            }}>
                                ⚠️ <strong>Behind Target:</strong> Short by <strong>{getCurrencySymbol(currency)}{Math.round(projectionChartData.shortAmount).toLocaleString()}</strong> at target date. Increase monthly savings or add one-off inflows.
                            </div>
                        )}

                        {/* Recharts Projection Chart */}
                        {projectionChartData.points.length > 0 && (
                            <div style={{ width: '100%', height: 160, background: 'rgba(0,0,0,0.15)', borderRadius: '10px', padding: '0.5rem' }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={projectionChartData.points} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                                        <XAxis dataKey="dateStr" stroke="var(--text-muted)" fontSize={9} tickLine={false} />
                                        <YAxis stroke="var(--text-muted)" fontSize={9} tickLine={false} tickFormatter={(val) => `${getCurrencySymbol(currency)}${val.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} />
                                        <RechartsTooltip
                                            content={({ active, payload }) => {
                                                if (active && payload && payload.length) {
                                                    const data = payload[0].payload
                                                    const symbol = getCurrencySymbol(currency)
                                                    return (
                                                        <div style={{ background: '#10101c', border: '1px solid var(--glass-border)', padding: '0.5rem', borderRadius: 8, fontSize: '0.75rem', color: '#fff' }}>
                                                            <p style={{ fontWeight: 600, marginBottom: '0.25rem' }}>{data.dateStr}</p>
                                                            <p style={{ color: 'var(--accent)' }}>Projected: {symbol}{data.amount.toLocaleString()}</p>
                                                            <p style={{ color: 'rgba(255,255,255,0.4)' }}>Target: {symbol}{data.target.toLocaleString()}</p>
                                                            {data.monthIndex > 0 && (
                                                                <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', marginTop: '0.25rem', paddingTop: '0.25rem', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                                                    <p>This month's flow:</p>
                                                                    <p>• You: +{symbol}{data.continuousYou}</p>
                                                                    <p style={{ textTransform: 'capitalize' }}>• {Object.keys(activeDetailGoal.partner_breakdown).find(k => k !== 'You') || 'Partner'}: +{symbol}{data.continuousPartner}</p>
                                                                    {data.oneOffSum > 0 && <p style={{ color: 'var(--accent)' }}>• One-off: +{symbol}{data.oneOffSum}</p>}
                                                                </div>
                                                            )}
                                                        </div>
                                                    )
                                                }
                                                return null
                                            }}
                                        />
                                        <Area type="monotone" dataKey="amount" stroke="var(--accent)" fill="rgba(0, 242, 254, 0.06)" strokeWidth={2} />
                                        <Area type="monotone" dataKey="target" stroke="rgba(255, 255, 255, 0.15)" strokeDasharray="4 4" fill="none" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        )}

                        {/* Continuous contributions inputs */}
                        <div className="grid-2-col">
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Your Monthly Saving ({getCurrencySymbol(currency)})</label>
                                <input
                                    type="number"
                                    className="chat-input__field"
                                    style={{ padding: '0.45rem 0.75rem', fontSize: '0.82rem', background: 'rgba(0,0,0,0.2)' }}
                                    value={continuousYou === 0 ? '' : continuousYou}
                                    onChange={(e) => setContinuousYou(Number(e.target.value || 0))}
                                    placeholder="e.g. 500"
                                />
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
                                    {(Object.keys(activeDetailGoal.partner_breakdown).find(k => k !== 'You') || 'Partner')}'s Monthly Saving ({getCurrencySymbol(currency)})
                                </label>
                                <input
                                    type="number"
                                    className="chat-input__field"
                                    style={{ padding: '0.45rem 0.75rem', fontSize: '0.82rem', background: 'rgba(0,0,0,0.2)' }}
                                    value={continuousPartner === 0 ? '' : continuousPartner}
                                    onChange={(e) => setContinuousPartner(Number(e.target.value || 0))}
                                    placeholder="e.g. 400"
                                />
                            </div>
                        </div>

                        {/* Non-Continuous Windfalls Section */}
                        <div style={{ borderTop: '1px solid rgba(255,255,255,0.03)', paddingTop: '0.75rem' }}>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: '0.5rem' }}>
                                One-off Windfalls (Non-Continuous)
                            </span>

                            {/* Windfalls list */}
                            {nonContinuousList.length > 0 ? (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '0.75rem', maxHeight: '120px', overflowY: 'auto', paddingRight: '0.25rem' }}>
                                    {nonContinuousList.map(c => (
                                        <div key={c.id} style={{
                                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                            padding: '0.4rem 0.6rem', background: 'rgba(255,255,255,0.015)', border: '1px solid var(--glass-border)',
                                            borderRadius: '8px', fontSize: '0.75rem'
                                        }}>
                                            <div>
                                                <span style={{ fontWeight: 600 }}>{c.label}</span>
                                                <span style={{ color: 'var(--text-muted)', marginLeft: '0.4rem' }}>
                                                    ({c.owner} • {getMonthNameFromOffset(c.monthOffset)})
                                                </span>
                                            </div>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                                <span style={{ fontWeight: 600, color: 'var(--accent)' }}>+{getCurrencySymbol(currency)}{c.amount.toLocaleString()}</span>
                                                <button
                                                    type="button"
                                                    onClick={() => handleRemoveOneOff(c.id)}
                                                    style={{ border: 'none', background: 'none', color: '#ff4757', cursor: 'pointer', padding: '0.1rem', display: 'flex' }}
                                                >
                                                    <Trash2 size={12} />
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontStyle: 'italic', marginBottom: '0.75rem', textAlign: 'center' }}>
                                    No planned one-off windfalls added yet.
                                </p>
                            )}

                            {/* Add Windfall inline form */}
                            <div className="windfall-grid">
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
                                    <label style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Label</label>
                                    <input
                                        type="text"
                                        placeholder="e.g. Bonus"
                                        value={oneOffLabel}
                                        onChange={(e) => setOneOffLabel(e.target.value)}
                                        className="chat-input__field"
                                        style={{ padding: '0.3rem 0.5rem', fontSize: '0.75rem', borderRadius: '10px' }}
                                    />
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
                                    <label style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Amount ({getCurrencySymbol(currency)})</label>
                                    <input
                                        type="number"
                                        placeholder="e.g. 5000"
                                        value={oneOffAmount}
                                        onChange={(e) => setOneOffAmount(e.target.value)}
                                        className="chat-input__field"
                                        style={{ padding: '0.3rem 0.5rem', fontSize: '0.75rem', borderRadius: '10px' }}
                                    />
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
                                    <label style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>When</label>
                                    <select
                                        value={oneOffMonthOffset}
                                        onChange={(e) => setOneOffMonthOffset(Number(e.target.value))}
                                        className="chat-input__field"
                                        style={{ padding: '0.3rem 0.5rem', fontSize: '0.75rem', borderRadius: '10px', background: 'rgba(0,0,0,0.2)' }}
                                    >
                                        {Array.from({ length: 24 }, (_, i) => i + 1).map(offset => (
                                            <option key={offset} value={offset}>
                                                {getMonthNameFromOffset(offset)}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
                                    <label style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Who</label>
                                    <select
                                        value={oneOffOwner}
                                        onChange={(e) => setOneOffOwner(e.target.value)}
                                        className="chat-input__field"
                                        style={{ padding: '0.3rem 0.5rem', fontSize: '0.75rem', borderRadius: '10px', background: 'rgba(0,0,0,0.2)' }}
                                    >
                                        <option value="You">You</option>
                                        <option value={Object.keys(activeDetailGoal.partner_breakdown).find(k => k !== 'You') || 'Partner'}>
                                            {Object.keys(activeDetailGoal.partner_breakdown).find(k => k !== 'You') || 'Partner'}
                                        </option>
                                    </select>
                                </div>
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        if (!oneOffAmount || !oneOffLabel) return
                                        const newFlow = {
                                            id: String(Date.now()),
                                            owner: oneOffOwner,
                                            type: 'non_continuous',
                                            amount: parseFloat(oneOffAmount),
                                            label: oneOffLabel,
                                            monthOffset: Number(oneOffMonthOffset)
                                        }
                                        setNonContinuousList(prev => [...prev, newFlow])
                                        setOneOffLabel('')
                                        setOneOffAmount('')
                                    }}
                                    className="btn btn--primary"
                                    style={{ padding: '0.35rem', display: 'flex', justifyContent: 'center', alignItems: 'center', height: '28px', borderRadius: '10px' }}
                                    title="Add One-off Windfall"
                                >
                                    <Plus size={14} />
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Ledger / History list */}
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Savings Ledger</h4>
                        
                        {activeDetailGoal.linked_asset_type && (
                            <div style={{
                                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                padding: '0.75rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--glass-border)',
                                borderRadius: '10px', fontSize: '0.8rem'
                            }}>
                                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)' }} />
                                    <div>
                                        <p style={{ fontWeight: 600 }}>Linked {
                                            activeDetailGoal.linked_asset_type === 'portfolio' ? 'Portfolio' :
                                            activeDetailGoal.linked_asset_type === 'account' ? 'Financial Account' : 'Manual Asset'
                                        }</p>
                                        <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Dynamically synced asset value</p>
                                    </div>
                                </div>
                                <span style={{ fontWeight: 600, color: 'var(--accent)' }}>+{formatValue(activeDetailGoal.linked_asset_value)}</span>
                            </div>
                        )}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', overflowY: 'auto', flex: 1, maxHeight: '200px' }}>
                            {!activeDetailGoal.contributions.length ? (
                                <p style={{ textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-muted)', padding: '2rem' }}>No manual contributions logged.</p>
                            ) : (
                                activeDetailGoal.contributions.map(contrib => (
                                    <div key={contrib.id} style={{
                                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                        padding: '0.75rem', background: 'rgba(255,255,255,0.015)', border: '1px solid var(--glass-border)',
                                        borderRadius: '10px', fontSize: '0.8rem'
                                    }}>
                                        <div>
                                            <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                                                <span style={{ fontWeight: 600 }}>{contrib.contributor_name}</span>
                                                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>({new Date(contrib.date).toLocaleDateString()})</span>
                                            </div>
                                            <p style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>{contrib.description || 'Manual saving contribution'}</p>
                                        </div>
                                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                            <span style={{ fontWeight: 600, color: 'var(--bullish)' }}>+{formatValue(contrib.amount)}</span>
                                            <button className="icon-btn icon-btn--danger" style={{ padding: '0.25rem' }} onClick={() => handleDeleteContribution(activeDetailGoal.id, contrib.id)} title="Delete transaction">
                                                <Trash2 size={12} />
                                            </button>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
                </>
            )}

            {/* ADD GOAL MODAL */}
            {showAddGoalModal && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
                    background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)', zIndex: 110,
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                    <form onSubmit={handleAddGoal} className="glass-panel" style={{
                        width: '420px', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.25rem',
                        background: 'var(--bg-surface)', border: '1px solid var(--glass-border)', borderRadius: '20px'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--glass-border)', paddingBottom: '0.75rem' }}>
                            <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Add New Savings Goal</h3>
                            <button type="button" className="icon-btn" onClick={() => setShowAddGoalModal(false)}>
                                <X size={18} />
                            </button>
                        </div>

                        {/* Title */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Goal Title</label>
                            <input
                                type="text"
                                className="chat-input__field"
                                value={goalTitle}
                                onChange={(e) => setGoalTitle(e.target.value)}
                                placeholder="e.g. Buying a House"
                                required
                            />
                        </div>

                        {/* Split Category and Target Amount */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Category</label>
                                <select
                                    value={goalCategory}
                                    onChange={(e) => setGoalCategory(e.target.value)}
                                    className="chat-input__field"
                                    style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid var(--glass-border)', borderRadius: '20px' }}
                                >
                                    <option value="House">House 🏠</option>
                                    <option value="Car">Car 🚗</option>
                                    <option value="Emergency Fund">Emergency Fund 🛡️</option>
                                    <option value="Vacation">Vacation ✈️</option>
                                    <option value="Other">Other 🎯</option>
                                </select>
                            </div>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Target Amount ({getCurrencySymbol(currency)})</label>
                                <input
                                    type="number"
                                    className="chat-input__field"
                                    value={goalTargetAmount}
                                    onChange={(e) => setGoalTargetAmount(e.target.value)}
                                    placeholder="e.g. 50000"
                                    required
                                />
                            </div>
                        </div>

                        {/* Target Date */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Target Completion Date</label>
                            <input
                                type="date"
                                className="chat-input__field"
                                value={goalTargetDate}
                                onChange={(e) => setGoalTargetDate(e.target.value)}
                                required
                            />
                        </div>

                        {/* Income Sources */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Potential Income Sources (comma-separated)</label>
                            <input
                                type="text"
                                className="chat-input__field"
                                value={goalIncomeSources}
                                onChange={(e) => setGoalIncomeSources(e.target.value)}
                                placeholder="e.g. Salary, Dividends, Side Hustle"
                            />
                        </div>

                        {/* Linked Asset Toggle */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Link Live Funding Asset (Optional)</label>
                            <select
                                value={goalLinkedAssetType}
                                onChange={(e) => {
                                    setGoalLinkedAssetType(e.target.value)
                                    setGoalLinkedAssetId('')
                                }}
                                className="chat-input__field"
                                style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid var(--glass-border)', borderRadius: '20px' }}
                            >
                                <option value="none">No Link (Manual Contributions Only)</option>
                                <option value="portfolio">Portfolio (Sync shares & cost value)</option>
                                <option value="manual_asset">Manual Asset (Sync asset balance)</option>
                                <option value="account">Financial Account (Sync balance)</option>
                            </select>
                        </div>

                        {/* Conditional Dropdown for Asset ID */}
                        {goalLinkedAssetType === 'portfolio' && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Select Portfolio</label>
                                <select
                                    value={goalLinkedAssetId}
                                    onChange={(e) => setGoalLinkedAssetId(e.target.value)}
                                    className="chat-input__field"
                                    style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid var(--glass-border)', borderRadius: '20px' }}
                                    required
                                >
                                    <option value="">-- Choose Portfolio --</option>
                                    {portfolios.map(p => (
                                        <option key={p.id} value={p.id}>{p.name}</option>
                                    ))}
                                </select>
                            </div>
                        )}

                        {goalLinkedAssetType === 'manual_asset' && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Select Asset</label>
                                <select
                                    value={goalLinkedAssetId}
                                    onChange={(e) => setGoalLinkedAssetId(e.target.value)}
                                    className="chat-input__field"
                                    style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid var(--glass-border)', borderRadius: '20px' }}
                                    required
                                >
                                    <option value="">-- Choose Asset --</option>
                                    {manualAssets.map(a => (
                                        <option key={a.id} value={a.id}>{a.asset_type} ({a.description || 'No desc'}) - {formatValue(a.value)}</option>
                                    ))}
                                </select>
                            </div>
                        )}

                        {goalLinkedAssetType === 'account' && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Select Account</label>
                                <select
                                    value={goalLinkedAssetId}
                                    onChange={(e) => setGoalLinkedAssetId(e.target.value)}
                                    className="chat-input__field"
                                    style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid var(--glass-border)', borderRadius: '20px' }}
                                    required
                                >
                                    <option value="">-- Choose Account --</option>
                                    {accounts.map(a => (
                                        <option key={a.id} value={a.id}>
                                            {a.name} ({a.account_class ? (a.account_class === 'real_estate' ? 'Real Estate' : a.account_class === 'credit_card' ? 'Credit Card' : a.account_class.charAt(0).toUpperCase() + a.account_class.slice(1)) : ''}) - {a.currency} {a.balance.toLocaleString()}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}

                        {/* Submit */}
                        <button type="submit" className="btn btn--primary" style={{ marginTop: '0.5rem', padding: '0.75rem' }}>
                            Create Goal
                        </button>
                    </form>
                </div>
            )}

            {/* EDIT GOAL MODAL */}
            {showEditGoalModal && editingGoal && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
                    background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)', zIndex: 110,
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                    <form onSubmit={handleEditGoalSubmit} className="glass-panel" style={{
                        width: '420px', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.25rem',
                        background: 'var(--bg-surface)', border: '1px solid var(--glass-border)', borderRadius: '20px'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--glass-border)', paddingBottom: '0.75rem' }}>
                            <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Edit Savings Goal</h3>
                            <button type="button" className="icon-btn" onClick={() => { setShowEditGoalModal(false); setEditingGoal(null); }}>
                                <X size={18} />
                            </button>
                        </div>

                        {/* Title */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Goal Title</label>
                            <input
                                type="text"
                                className="chat-input__field"
                                value={goalTitle}
                                onChange={(e) => setGoalTitle(e.target.value)}
                                placeholder="e.g. Buying a House"
                                required
                            />
                        </div>

                        {/* Split Category and Target Amount */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Category</label>
                                <select
                                    value={goalCategory}
                                    onChange={(e) => setGoalCategory(e.target.value)}
                                    className="chat-input__field"
                                    style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid var(--glass-border)', borderRadius: '20px' }}
                                >
                                    <option value="House">House 🏠</option>
                                    <option value="Car">Car 🚗</option>
                                    <option value="Emergency Fund">Emergency Fund 🛡️</option>
                                    <option value="Vacation">Vacation ✈️</option>
                                    <option value="Other">Other 🎯</option>
                                </select>
                            </div>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Target Amount ({getCurrencySymbol(currency)})</label>
                                <input
                                    type="number"
                                    className="chat-input__field"
                                    value={goalTargetAmount}
                                    onChange={(e) => setGoalTargetAmount(e.target.value)}
                                    placeholder="e.g. 50000"
                                    required
                                />
                            </div>
                        </div>

                        {/* Target Date */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Target Completion Date</label>
                            <input
                                type="date"
                                className="chat-input__field"
                                value={goalTargetDate}
                                onChange={(e) => setGoalTargetDate(e.target.value)}
                                required
                            />
                        </div>

                        {/* Income Sources */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Potential Income Sources (comma-separated)</label>
                            <input
                                type="text"
                                className="chat-input__field"
                                value={goalIncomeSources}
                                onChange={(e) => setGoalIncomeSources(e.target.value)}
                                placeholder="e.g. Salary, Dividends, Side Hustle"
                            />
                        </div>

                        {/* Linked Asset Toggle */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Link Live Funding Asset (Optional)</label>
                            <select
                                value={goalLinkedAssetType}
                                onChange={(e) => {
                                    setGoalLinkedAssetType(e.target.value)
                                    setGoalLinkedAssetId('')
                                }}
                                className="chat-input__field"
                                style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid var(--glass-border)', borderRadius: '20px' }}
                            >
                                <option value="none">No Link (Manual Contributions Only)</option>
                                <option value="portfolio">Portfolio (Sync shares & cost value)</option>
                                <option value="manual_asset">Manual Asset (Sync asset balance)</option>
                                <option value="account">Financial Account (Sync balance)</option>
                            </select>
                        </div>

                        {/* Conditional Dropdown for Asset ID */}
                        {goalLinkedAssetType === 'portfolio' && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Select Portfolio</label>
                                <select
                                    value={goalLinkedAssetId}
                                    onChange={(e) => setGoalLinkedAssetId(e.target.value)}
                                    className="chat-input__field"
                                    style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid var(--glass-border)', borderRadius: '20px' }}
                                    required
                                >
                                    <option value="">-- Choose Portfolio --</option>
                                    {portfolios.map(p => (
                                        <option key={p.id} value={p.id}>{p.name}</option>
                                    ))}
                                </select>
                            </div>
                        )}

                        {goalLinkedAssetType === 'manual_asset' && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Select Asset</label>
                                <select
                                    value={goalLinkedAssetId}
                                    onChange={(e) => setGoalLinkedAssetId(e.target.value)}
                                    className="chat-input__field"
                                    style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid var(--glass-border)', borderRadius: '20px' }}
                                    required
                                >
                                    <option value="">-- Choose Asset --</option>
                                    {manualAssets.map(a => (
                                        <option key={a.id} value={a.id}>{a.asset_type} ({a.description || 'No desc'}) - {formatValue(a.value)}</option>
                                    ))}
                                </select>
                            </div>
                        )}

                        {goalLinkedAssetType === 'account' && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Select Account</label>
                                <select
                                    value={goalLinkedAssetId}
                                    onChange={(e) => setGoalLinkedAssetId(e.target.value)}
                                    className="chat-input__field"
                                    style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid var(--glass-border)', borderRadius: '20px' }}
                                    required
                                >
                                    <option value="">-- Choose Account --</option>
                                    {accounts.map(a => (
                                        <option key={a.id} value={a.id}>
                                            {a.name} ({a.account_class ? (a.account_class === 'real_estate' ? 'Real Estate' : a.account_class === 'credit_card' ? 'Credit Card' : a.account_class.charAt(0).toUpperCase() + a.account_class.slice(1)) : ''}) - {a.currency} {a.balance.toLocaleString()}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}

                        {/* Submit */}
                        <button type="submit" className="btn btn--primary" style={{ marginTop: '0.5rem', padding: '0.75rem' }}>
                            Update Goal
                        </button>
                    </form>
                </div>
            )}

            {/* ADD CONTRIBUTION MODAL */}
            {showAddContribModal && selectedGoal && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
                    background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)', zIndex: 110,
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                    <form onSubmit={handleAddContribution} className="glass-panel" style={{
                        width: '380px', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.25rem',
                        background: 'var(--bg-surface)', border: '1px solid var(--glass-border)', borderRadius: '20px'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--glass-border)', paddingBottom: '0.75rem' }}>
                            <div>
                                <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Contribute Money</h3>
                                <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>To: {selectedGoal.title}</p>
                            </div>
                            <button type="button" className="icon-btn" onClick={() => { setShowAddContribModal(false); setSelectedGoal(null) }}>
                                <X size={18} />
                            </button>
                        </div>

                        {/* Amount */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Contribution Amount ({getCurrencySymbol(currency)})</label>
                            <input
                                type="number"
                                className="chat-input__field"
                                value={contribAmount}
                                onChange={(e) => setContribAmount(e.target.value)}
                                placeholder="e.g. 1000"
                                required
                                autoFocus
                            />
                        </div>

                        {/* Date */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Date (Optional, defaults to now)</label>
                            <input
                                type="date"
                                className="chat-input__field"
                                value={contribDate}
                                onChange={(e) => setContribDate(e.target.value)}
                            />
                        </div>

                        {/* Description */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Memo / Description</label>
                            <input
                                type="text"
                                className="chat-input__field"
                                value={contribDescription}
                                onChange={(e) => setContribDescription(e.target.value)}
                                placeholder="e.g. May Savings Split"
                            />
                        </div>

                        {/* Submit */}
                        <button type="submit" className="btn btn--primary" style={{ marginTop: '0.5rem', padding: '0.75rem' }}>
                            Confirm Contribution
                        </button>
                    </form>
                </div>
            )}
        </main>
    )
}

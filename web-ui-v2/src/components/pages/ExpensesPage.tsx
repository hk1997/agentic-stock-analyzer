import React, { useState, useEffect, useRef } from 'react';
import { apiFetch } from '../../utils/api';
import { storage } from '../../utils/storage';
import { Upload, Plus, AlertCircle, CheckCircle, Search, Filter, Edit2, Check, X, Trash2, ArrowLeftRight } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, PieChart, Pie, Cell } from 'recharts';
import { CategorizationPopup } from './CategorizationPopup';
import { useAuth } from '../../hooks/useAuth';

const COLORS = [
    'var(--accent-blue)', 
    'var(--accent-purple)', 
    'var(--accent-green)', 
    '#ff9500', // orange
    '#ffcc00', // yellow
    '#00c7be', // teal
    '#ff3b30'  // red
];

export function ExpensesPage() {
    const { user } = useAuth();
    const [expenses, setExpenses] = useState<any[]>([]);
    const [hoveredPieIndex, setHoveredPieIndex] = useState<number | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [selectedMonth, setSelectedMonth] = useState('');
    const [uncategorizedExpenses, setUncategorizedExpenses] = useState<any[]>([]);

    const [myPreExisting, setMyPreExisting] = useState<number>(() => {
        const val = storage.getItem('expenses_my_pre_existing');
        return val ? parseFloat(val) : 0;
    });
    const [partnerPreExisting, setPartnerPreExisting] = useState<number>(() => {
        const val = storage.getItem('expenses_partner_pre_existing');
        return val ? parseFloat(val) : 0;
    });

    const [myExpected, setMyExpected] = useState<number>(() => {
        const val = storage.getItem('expenses_my_expected');
        return val ? parseFloat(val) : 0;
    });
    const [partnerExpected, setPartnerExpected] = useState<number>(() => {
        const val = storage.getItem('expenses_partner_expected');
        return val ? parseFloat(val) : 0;
    });

    useEffect(() => {
        storage.setItem('expenses_my_pre_existing', myPreExisting.toString());
    }, [myPreExisting]);

    useEffect(() => {
        storage.setItem('expenses_partner_pre_existing', partnerPreExisting.toString());
    }, [partnerPreExisting]);

    useEffect(() => {
        storage.setItem('expenses_my_expected', myExpected.toString());
    }, [myExpected]);

    useEffect(() => {
        storage.setItem('expenses_partner_expected', partnerExpected.toString());
    }, [partnerExpected]);
    
    // Filters state
    const [search, setSearch] = useState('');
    const [filterCategory, setFilterCategory] = useState('');
    const [filterType, setFilterType] = useState('all'); // 'all' | 'personal' | 'joint'
    const [minAmount, setMinAmount] = useState('');
    const [maxAmount, setMaxAmount] = useState('');

    // Inline edit state
    const [editingExpenseId, setEditingExpenseId] = useState<number | null>(null);
    const [editCategory, setEditCategory] = useState('');
    const [editDescription, setEditDescription] = useState('');
    const [editAmount, setEditAmount] = useState('');
    const [editType, setEditType] = useState('my-personal'); // 'my-personal' | 'linked-personal' | 'joint'
    const [editDate, setEditDate] = useState('');

    // Upload state
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [uploadStatus, setUploadStatus] = useState<{
        type: 'idle'|'uploading'|'success'|'error', 
        msg: string, 
        added?: number, 
        duplicates?: number, 
        failed?: number
    }>({type: 'idle', msg: ''});
    const [showUploadModal, setShowUploadModal] = useState(false);
    const [uploadFile, setUploadFile] = useState<File | null>(null);
    const [uploadDefaultCategory, setUploadDefaultCategory] = useState('');
    const [uploadIsJoint, setUploadIsJoint] = useState(false);
    const [uploadPeriod, setUploadPeriod] = useState('');

    // Form state
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [category, setCategory] = useState('');
    const [amount, setAmount] = useState('');
    const [description, setDescription] = useState('');
    const [isJoint, setIsJoint] = useState(false);

    const loadExpenses = async () => {
        try {
            const queryParams = selectedMonth ? `?month=${selectedMonth}` : '';
            const data = await apiFetch(`/api/finance/expenses${queryParams}`);
            setExpenses(data);
        } catch (error) {
            console.error("Failed to load expenses", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadExpenses();
    }, [selectedMonth]);

    const handleAddExpense = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await apiFetch('/api/finance/expenses', {
                method: 'POST',
                body: JSON.stringify({
                    date: new Date(date).toISOString(),
                    category,
                    amount: parseFloat(amount),
                    description,
                    is_joint: isJoint
                })
            });
            // Reset form
            setCategory('');
            setAmount('');
            setDescription('');
            setIsJoint(false);
            loadExpenses();
        } catch (error) {
            console.error("Failed to add expense", error);
        }
    };

    const handleModalUpload = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!uploadFile) return;

        setUploadStatus({ type: 'uploading', msg: 'Uploading CSV...' });
        const formData = new FormData();
        formData.append('file', uploadFile);

        try {
            const params = new URLSearchParams();
            if (uploadDefaultCategory.trim()) {
                params.append('default_category', uploadDefaultCategory.trim());
            }
            if (uploadIsJoint) {
                params.append('default_is_joint', 'true');
            }
            if (uploadPeriod) {
                params.append('default_period', uploadPeriod);
            }

            const queryString = params.toString() ? `?${params.toString()}` : '';
            const res = await apiFetch(`/api/finance/expenses/upload${queryString}`, {
                method: 'POST',
                body: formData,
            });
            setUploadStatus({ 
                type: 'success', 
                msg: 'Upload completed successfully',
                added: res.added,
                duplicates: res.duplicates,
                failed: res.failed
            });
            setShowUploadModal(false);
            
            if (res.uncategorized > 0) {
                const uncategorizedData = await apiFetch('/api/finance/expenses/uncategorized');
                setUncategorizedExpenses(uncategorizedData);
            }
            
            loadExpenses();
        } catch (error: any) {
            setUploadStatus({ type: 'error', msg: error.message || 'Failed to upload CSV' });
        } finally {
            setUploadFile(null);
            setTimeout(() => setUploadStatus({ type: 'idle', msg: '' }), 7000);
        }
    };

    const startEditing = (e: any) => {
        setEditingExpenseId(e.id);
        setEditCategory(e.category);
        setEditDescription(e.description || '');
        setEditAmount(e.amount.toString());
        setEditDate(new Date(e.date).toISOString().split('T')[0]);
        if (e.is_joint === 1) {
            setEditType('joint');
        } else if (e.owner_id === user?.id) {
            setEditType('my-personal');
        } else {
            setEditType('linked-personal');
        }
    };

    const handleSaveEdit = async (id: number) => {
        try {
            await apiFetch(`/api/finance/expenses/${id}`, {
                method: 'PATCH',
                body: JSON.stringify({
                    category: editCategory,
                    description: editDescription,
                    amount: parseFloat(editAmount),
                    date: new Date(editDate).toISOString(),
                    ownership_type: editType
                })
            });
            setEditingExpenseId(null);
            loadExpenses();
        } catch (error) {
            console.error("Failed to save expense edit", error);
        }
    };

    const handleDeleteExpense = async (id: number) => {
        if (!window.confirm("Are you sure you want to delete this expense?")) {
            return;
        }
        try {
            await apiFetch(`/api/finance/expenses/${id}`, {
                method: 'DELETE'
            });
            loadExpenses();
        } catch (error) {
            console.error("Failed to delete expense", error);
        }
    };

    // Calculate filtered expenses
    const filteredExpenses = expenses.filter(e => {
        if (search && !e.description?.toLowerCase().includes(search.toLowerCase())) {
            return false;
        }
        if (filterCategory && e.category !== filterCategory) {
            return false;
        }
        if (filterType === 'my-personal') {
            if (e.is_joint || e.owner_id !== user?.id) return false;
        }
        if (filterType === 'linked-personal') {
            if (e.is_joint || e.owner_id === user?.id) return false;
        }
        if (filterType === 'joint') {
            if (!e.is_joint) return false;
        }
        if (minAmount && e.amount < parseFloat(minAmount)) {
            return false;
        }
        if (maxAmount && e.amount > parseFloat(maxAmount)) {
            return false;
        }
        return true;
    });

    // Compute dynamic metrics
    const totalAmount = filteredExpenses.reduce((sum, e) => sum + e.amount, 0);
    const myPersonalTotal = filteredExpenses.filter(e => !e.is_joint && e.owner_id === user?.id).reduce((sum, e) => sum + e.amount, 0);
    const linkedPersonalTotal = filteredExpenses.filter(e => !e.is_joint && e.owner_id !== user?.id).reduce((sum, e) => sum + e.amount, 0);
    const jointTotal = filteredExpenses.filter(e => e.is_joint).reduce((sum, e) => sum + e.amount, 0);

    // Split & Settle Up Calculations (computed over the complete month's loaded expenses, not impacted by search filters)
    const myJointPaid = expenses
        .filter(e => e.is_joint && e.payer_id === user?.id)
        .reduce((sum, e) => sum + e.amount, 0);

    const partnerJointPaid = expenses
        .filter(e => e.is_joint && e.payer_id !== user?.id)
        .reduce((sum, e) => sum + e.amount, 0);

    const totalJointPaid = myJointPaid + partnerJointPaid + myPreExisting + partnerPreExisting;
    
    // Split: base expectations, remaining split 50-50
    const baseTargetSum = myExpected + partnerExpected;
    const extraAmount = baseTargetSum > 0 ? Math.max(0, totalJointPaid - baseTargetSum) : totalJointPaid;
    let myExpectedShare = 0;
    let partnerExpectedShare = 0;

    if (baseTargetSum > 0) {
        const baseAmount = Math.min(totalJointPaid, baseTargetSum);
        const myBaseShare = baseAmount * (myExpected / baseTargetSum);
        const partnerBaseShare = baseAmount * (partnerExpected / baseTargetSum);

        myExpectedShare = myBaseShare + extraAmount / 2;
        partnerExpectedShare = partnerBaseShare + extraAmount / 2;
    } else {
        myExpectedShare = totalJointPaid / 2;
        partnerExpectedShare = totalJointPaid / 2;
    }

    const expectedShare = totalJointPaid / 2; // general 50/50 ref for backup

    const myJointGap = Math.max(0, myExpectedShare - (myJointPaid + myPreExisting));
    const partnerJointGap = Math.max(0, partnerExpectedShare - (partnerJointPaid + partnerPreExisting));

    const partnerPersonalPaidByMe = expenses
        .filter(e => !e.is_joint && e.owner_id !== user?.id && e.payer_id === user?.id)
        .reduce((sum, e) => sum + e.amount, 0);

    const myPersonalPaidByPartner = expenses
        .filter(e => !e.is_joint && e.owner_id === user?.id && e.payer_id !== user?.id)
        .reduce((sum, e) => sum + e.amount, 0);

    const myPersonalTotalAll = expenses
        .filter(e => !e.is_joint && e.owner_id === user?.id)
        .reduce((sum, e) => sum + e.amount, 0);

    const partnerPersonalTotalAll = expenses
        .filter(e => !e.is_joint && e.owner_id !== user?.id)
        .reduce((sum, e) => sum + e.amount, 0);

    const jointAdjustment = (myJointPaid + myPreExisting) - myExpectedShare;
    const personalAdjustment = partnerPersonalPaidByMe - myPersonalPaidByPartner;
    const netOwedToMe = jointAdjustment + personalAdjustment;

    const myJointPct = totalJointPaid > 0 ? ((myJointPaid + myPreExisting) / totalJointPaid) * 100 : 50;
    const partnerJointPct = totalJointPaid > 0 ? ((partnerJointPaid + partnerPreExisting) / totalJointPaid) * 100 : 50;

    // List of unique categories for filters
    const uniqueCategories = Array.from(new Set(expenses.map(e => e.category))).sort();

    // Grouping for chart
    const categoryTotals = filteredExpenses.reduce((acc, curr) => {
        acc[curr.category] = (acc[curr.category] || 0) + curr.amount;
        return acc;
    }, {} as Record<string, number>);

    const chartData = Object.keys(categoryTotals).map(cat => ({
        category: cat,
        amount: categoryTotals[cat]
    })).sort((a, b) => b.amount - a.amount);

    // Grouping for line/area chart (daily totals)
    const dateTotals = filteredExpenses.reduce((acc, curr) => {
        const dateStr = new Date(curr.date).toISOString().split('T')[0];
        acc[dateStr] = (acc[dateStr] || 0) + curr.amount;
        return acc;
    }, {} as Record<string, number>);

    const lineChartData = Object.keys(dateTotals).map(date => ({
        date,
        amount: parseFloat(dateTotals[date].toFixed(2))
    })).sort((a, b) => a.date.localeCompare(b.date));

    // Grouping for pie chart (only positive sectors)
    const pieChartData = Object.keys(categoryTotals).map(cat => ({
        name: cat,
        value: categoryTotals[cat] < 0 ? 0 : parseFloat(categoryTotals[cat].toFixed(2))
    })).filter(item => item.value > 0);

    const totalPieValue = pieChartData.reduce((sum, item) => sum + item.value, 0);

    if (isLoading) return <div className="main-content">Loading...</div>;

    return (
        <>
        <main className="main-content">
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h1 style={{ margin: 0, color: 'var(--text-primary)' }}>Expenses</h1>
                    <p style={{ color: 'var(--text-secondary)', margin: '0.5rem 0 0 0' }}>Track and manage your cash flow</p>
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <input 
                        type="month" 
                        value={selectedMonth}
                        onChange={(e) => setSelectedMonth(e.target.value)}
                        style={{ 
                            background: 'rgba(255, 255, 255, 0.06)', 
                            border: '1px solid var(--glass-border)', 
                            padding: '0 0.75rem', 
                            borderRadius: 'var(--radius-md)', 
                            color: 'var(--text-primary)', 
                            height: '38px',
                            fontFamily: 'inherit',
                            fontSize: '0.85rem',
                            outline: 'none',
                            cursor: 'pointer'
                        }}
                    />
                    
                    {uploadStatus.type === 'uploading' && <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{uploadStatus.msg}</span>}
                    {uploadStatus.type === 'error' && <span style={{ color: 'var(--accent-red)', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}><AlertCircle size={16}/> {uploadStatus.msg}</span>}
                    {uploadStatus.type === 'success' && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--border)', padding: '0.4rem 0.8rem', borderRadius: '8px', fontSize: '0.85rem' }}>
                            <CheckCircle size={16} style={{ color: 'var(--accent-green)' }} />
                            <span style={{ color: 'var(--text-primary)' }}>Import Complete:</span>
                            <span style={{ color: 'var(--accent-green)', fontWeight: 600 }}>{uploadStatus.added} Added</span>
                            <span style={{ color: 'var(--text-secondary)' }}>•</span>
                            <span style={{ color: '#ffc107', fontWeight: 600 }}>{uploadStatus.duplicates} Duplicates</span>
                            <span style={{ color: 'var(--text-secondary)' }}>•</span>
                            <span style={{ color: 'var(--accent-red)', fontWeight: 600 }}>{uploadStatus.failed} Failed</span>
                        </div>
                    )}
                    
                    <button 
                        className="btn btn-secondary" 
                        onClick={() => {
                            setUploadFile(null);
                            setUploadDefaultCategory('');
                            setUploadIsJoint(false);
                            setUploadPeriod('');
                            setShowUploadModal(true);
                        }}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', height: '38px', padding: '0 1rem' }}
                    >
                        <Upload size={18} /> Upload CSV
                    </button>
                </div>
            </header>

            {/* Stat Summary Cards */}
            <div className="expenses-kpi-grid">
                <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Total Expenses (Filtered)</span>
                    <span style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                        ${totalAmount.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                    </span>
                </div>
                <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>My Personal Expenses</span>
                    <span style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'var(--accent-blue)' }}>
                        ${myPersonalTotal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                    </span>
                </div>
                <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Linked Account Personal</span>
                    <span style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'var(--accent-green)' }}>
                        ${linkedPersonalTotal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                    </span>
                </div>
                <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Joint Expenses</span>
                    <span style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'var(--accent-purple)' }}>
                        ${jointTotal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                    </span>
                </div>
            </div>

            {/* Visual Insights Grid */}
            <div className="stats-grid" style={{ marginTop: '1.5rem' }}>
                {/* Panel 1: Category Allocation (Bar + Pie Chart side-by-side) */}
                <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem', height: '350px' }}>
                    <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-primary)' }}>Category Allocation</h3>
                    <div style={{ display: 'flex', flex: 1, gap: '1rem', height: 'calc(100% - 2.5rem)', overflow: 'hidden' }}>
                        <div style={{ flex: 1.3, height: '100%' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={chartData} margin={{ top: 10, right: 0, left: -25, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                                    <XAxis dataKey="category" stroke="var(--text-secondary)" tick={{fontSize: 9}} />
                                    <YAxis stroke="var(--text-secondary)" tick={{fontSize: 9}} />
                                    <Tooltip 
                                        cursor={{fill: 'rgba(255, 255, 255, 0.05)'}}
                                        contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '8px' }}
                                        itemStyle={{ color: 'var(--text-primary)' }}
                                        labelStyle={{ color: 'var(--text-secondary)' }}
                                        formatter={(value: number) => [`$${value.toLocaleString()}`, 'Amount']}
                                    />
                                    <Bar dataKey="amount" fill="var(--accent-blue)" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                        <div style={{ flex: 0.7, height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie
                                        data={pieChartData}
                                        cx="50%"
                                        cy="50%"
                                        innerRadius={40}
                                        outerRadius={65}
                                        paddingAngle={3}
                                        dataKey="value"
                                        nameKey="name"
                                        onMouseEnter={(_, index) => setHoveredPieIndex(index)}
                                        onMouseLeave={() => setHoveredPieIndex(null)}
                                    >
                                        {pieChartData.map((entry, index) => (
                                            <Cell 
                                                key={`cell-${index}`} 
                                                fill={COLORS[index % COLORS.length]} 
                                                style={{
                                                    outline: 'none',
                                                    cursor: 'pointer',
                                                    opacity: hoveredPieIndex === null || hoveredPieIndex === index ? 1 : 0.6,
                                                    transition: 'opacity 0.2s ease'
                                                }}
                                            />
                                        ))}
                                    </Pie>
                                    <Tooltip 
                                        contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '8px' }}
                                        itemStyle={{ color: 'var(--text-primary)' }}
                                        labelStyle={{ color: 'var(--text-secondary)' }}
                                        formatter={(value: number, name: any) => {
                                            const pct = totalPieValue > 0 ? ((value / totalPieValue) * 100).toFixed(1) : '0.0';
                                            return [`$${value.toLocaleString()} (${pct}%)`, name];
                                        }}
                                    />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>

                {/* Panel 2: Spending Trend (Area Chart) */}
                <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem', height: '350px' }}>
                    <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-primary)' }}>Spending Trend</h3>
                    <div style={{ flex: 1, height: 'calc(100% - 2.5rem)' }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={lineChartData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="colorAmount" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="var(--accent-blue)" stopOpacity={0.3}/>
                                        <stop offset="95%" stopColor="var(--accent-blue)" stopOpacity={0.0}/>
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                                <XAxis 
                                    dataKey="date" 
                                    stroke="var(--text-secondary)" 
                                    tick={{fontSize: 9}}
                                    tickFormatter={(str) => {
                                        if (!str) return '';
                                        const parts = str.split('-');
                                        if (parts.length < 3) return str;
                                        return `${parts[1]}/${parts[2]}`; // MM/DD
                                    }}
                                />
                                <YAxis stroke="var(--text-secondary)" tick={{fontSize: 9}} />
                                <Tooltip 
                                    contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '8px' }}
                                    itemStyle={{ color: 'var(--text-primary)' }}
                                    labelStyle={{ color: 'var(--text-secondary)' }}
                                    formatter={(value: number) => [`$${value.toLocaleString()}`, 'Amount']}
                                    labelFormatter={(label) => `Date: ${new Date(label).toLocaleDateString()}`}
                                />
                                <Area type="monotone" dataKey="amount" stroke="var(--accent-blue)" strokeWidth={2} fillOpacity={1} fill="url(#colorAmount)" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            {/* Split & Settle Up Section */}
            {user && (
                <div className="glass-panel" style={{ padding: '2rem', marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', borderBottom: '1px solid var(--border)', paddingBottom: '1rem' }}>
                        <ArrowLeftRight size={22} style={{ color: 'var(--accent)' }} />
                        <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>Split & Settle Up</h3>
                    </div>

                    <div className="stats-grid">
                        {/* 1. Joint Split */}
                        <div style={{ background: 'rgba(255, 255, 255, 0.02)', border: '1px solid rgba(255, 255, 255, 0.04)', borderRadius: '12px', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            <h4 style={{ margin: 0, fontSize: '1rem', color: 'var(--text-primary)', fontWeight: 500 }}>
                                Joint Expenses Split {baseTargetSum > 0 ? `(${myExpected}:${partnerExpected} base + 50/50 extra)` : '(50/50 split)'}
                            </h4>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                                    <span>You: ${(myJointPaid + myPreExisting).toFixed(2)} ({myJointPct.toFixed(0)}%)</span>
                                    <span>Partner: ${(partnerJointPaid + partnerPreExisting).toFixed(2)} ({partnerJointPct.toFixed(0)}%)</span>
                                </div>
                                <div style={{ height: '8px', background: 'rgba(255, 255, 255, 0.05)', borderRadius: '4px', overflow: 'hidden', display: 'flex' }}>
                                    <div style={{ width: `${myJointPct}%`, background: 'var(--accent-blue)', height: '100%', transition: 'width 0.3s ease' }} />
                                    <div style={{ width: `${partnerJointPct}%`, background: 'var(--accent-purple)', height: '100%', transition: 'width 0.3s ease' }} />
                                </div>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <span>Joint Expenses (Transactions):</span>
                                    <span style={{ color: 'var(--text-primary)' }}>${(myJointPaid + partnerJointPaid).toFixed(2)}</span>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <span>Pre-existing / External:</span>
                                    <span style={{ color: 'var(--text-primary)' }}>+${(myPreExisting + partnerPreExisting).toFixed(2)}</span>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: '0.5rem', fontWeight: 600 }}>
                                    <span>Total Joint Pool:</span>
                                    <span style={{ color: 'var(--text-primary)' }}>${totalJointPaid.toFixed(2)}</span>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.25rem' }}>
                                    <span>Expected Share:</span>
                                    <span style={{ color: 'var(--text-primary)', textAlign: 'right' }}>
                                        {baseTargetSum > 0 
                                            ? `You: $${myExpectedShare.toFixed(2)} | Partner: $${partnerExpectedShare.toFixed(2)}` 
                                            : `$${expectedShare.toFixed(2)} each`}
                                    </span>
                                </div>
                            </div>
                            <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: '0.75rem', marginTop: '0.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                    <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Expected Base Contributions</span>
                                    <div className="grid-2-col">
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                            <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>You expect to add</label>
                                            <input 
                                                type="number" 
                                                step="0.01"
                                                placeholder="0.00" 
                                                value={myExpected || ''} 
                                                onChange={e => setMyExpected(parseFloat(e.target.value) || 0)} 
                                                style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.35rem 0.5rem', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem', outline: 'none' }}
                                            />
                                        </div>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                            <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Partner expects to add</label>
                                            <input 
                                                type="number" 
                                                step="0.01"
                                                placeholder="0.00" 
                                                value={partnerExpected || ''} 
                                                onChange={e => setPartnerExpected(parseFloat(e.target.value) || 0)} 
                                                style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.35rem 0.5rem', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem', outline: 'none' }}
                                            />
                                        </div>
                                    </div>
                                </div>

                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', borderTop: '1px solid rgba(255, 255, 255, 0.03)', paddingTop: '0.5rem' }}>
                                    <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Pre-existing / External Payments</span>
                                    <div className="grid-2-col">
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                            <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Paid by You</label>
                                            <input 
                                                type="number" 
                                                step="0.01"
                                                placeholder="0.00" 
                                                value={myPreExisting || ''} 
                                                onChange={e => setMyPreExisting(parseFloat(e.target.value) || 0)} 
                                                style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.35rem 0.5rem', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem', outline: 'none' }}
                                            />
                                        </div>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                            <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Paid by Partner</label>
                                            <input 
                                                type="number" 
                                                step="0.01"
                                                placeholder="0.00" 
                                                value={partnerPreExisting || ''} 
                                                onChange={e => setPartnerPreExisting(parseFloat(e.target.value) || 0)} 
                                                style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.35rem 0.5rem', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem', outline: 'none' }}
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* 2. Personal Split */}
                        <div style={{ background: 'rgba(255, 255, 255, 0.02)', border: '1px solid rgba(255, 255, 255, 0.04)', borderRadius: '12px', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            <h4 style={{ margin: 0, fontSize: '1rem', color: 'var(--text-primary)', fontWeight: 500 }}>Personal Expenses Paid By Other</h4>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                    <span>Partner's personal paid by You:</span>
                                    <span style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--bullish)', marginTop: '0.25rem' }}>
                                        ${partnerPersonalPaidByMe.toFixed(2)}
                                    </span>
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: '0.75rem' }}>
                                    <span>Your personal paid by Partner:</span>
                                    <span style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--accent-red)', marginTop: '0.25rem' }}>
                                        ${myPersonalPaidByPartner.toFixed(2)}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* 3. Settlement Summary */}
                        <div style={{ background: 'rgba(255, 255, 255, 0.02)', border: '1px solid rgba(255, 255, 255, 0.04)', borderRadius: '12px', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            <h4 style={{ margin: 0, fontSize: '1rem', color: 'var(--text-primary)', fontWeight: 500 }}>Net Settlement</h4>
                            
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.85rem' }}>
                                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>End-of-Month Due Breakdown</span>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.02)', padding: '0.5rem 0.75rem', borderRadius: '6px' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 500, color: 'var(--text-primary)' }}>
                                        <span>You owe:</span>
                                        <span>${(extraAmount / 2 + myPersonalTotalAll).toFixed(2)}</span>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)', paddingLeft: '0.5rem' }}>
                                        <span>• Joint Excess Share (50/50):</span>
                                        <span>${(extraAmount / 2).toFixed(2)}</span>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)', paddingLeft: '0.5rem' }}>
                                        <span>• Personal Expenses:</span>
                                        <span>${myPersonalTotalAll.toFixed(2)}</span>
                                    </div>
                                </div>
                                
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', background: 'rgba(255, 255, 255, 0.01)', border: '1px solid rgba(255, 255, 255, 0.02)', padding: '0.5rem 0.75rem', borderRadius: '6px' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 500, color: 'var(--text-primary)' }}>
                                        <span>Partner owes:</span>
                                        <span>${(extraAmount / 2 + partnerPersonalTotalAll).toFixed(2)}</span>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)', paddingLeft: '0.5rem' }}>
                                        <span>• Joint Excess Share (50/50):</span>
                                        <span>${(extraAmount / 2).toFixed(2)}</span>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)', paddingLeft: '0.5rem' }}>
                                        <span>• Personal Expenses:</span>
                                        <span>${partnerPersonalTotalAll.toFixed(2)}</span>
                                    </div>
                                </div>
                            </div>


                        </div>
                    </div>
                </div>
            )}

            <div className="expenses-layout-grid">
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    {/* Filters Bar */}
                    <div className="glass-panel" style={{ padding: '1rem 1.5rem', display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                            <Filter size={16} /> Filters:
                        </div>
                        
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: '1 1 180px' }}>
                            <Search size={16} style={{ color: 'var(--text-secondary)' }} />
                            <input 
                                type="text" 
                                placeholder="Search description..." 
                                value={search} 
                                onChange={e => setSearch(e.target.value)} 
                                style={{ flexGrow: 1, background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.4rem 0.75rem', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.85rem' }} 
                            />
                        </div>

                        <select 
                            value={filterCategory} 
                            onChange={e => setFilterCategory(e.target.value)} 
                            style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.4rem 0.75rem', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.85rem', cursor: 'pointer' }}
                        >
                            <option value="">All Categories</option>
                            {uniqueCategories.map(cat => (
                                <option key={cat} value={cat}>{cat}</option>
                            ))}
                        </select>

                        <select 
                            value={filterType} 
                            onChange={e => setFilterType(e.target.value)} 
                            style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.4rem 0.75rem', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.85rem', cursor: 'pointer' }}
                        >
                            <option value="all">All Types</option>
                            <option value="my-personal">My Personal</option>
                            <option value="linked-personal">Linked Account Personal</option>
                            <option value="joint">Joint</option>
                        </select>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                            <input 
                                type="number" 
                                placeholder="Min $" 
                                value={minAmount} 
                                onChange={e => setMinAmount(e.target.value)} 
                                style={{ width: '80px', background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.4rem 0.5rem', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.85rem' }} 
                            />
                            <span style={{ color: 'var(--text-secondary)' }}>-</span>
                            <input 
                                type="number" 
                                placeholder="Max $" 
                                value={maxAmount} 
                                onChange={e => setMaxAmount(e.target.value)} 
                                style={{ width: '80px', background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.4rem 0.5rem', borderRadius: '8px', color: 'var(--text-primary)', fontSize: '0.85rem' }} 
                            />
                        </div>

                        {(search || filterCategory || filterType !== 'all' || minAmount || maxAmount) && (
                            <button 
                                onClick={() => {
                                    setSearch('');
                                    setFilterCategory('');
                                    setFilterType('all');
                                    setMinAmount('');
                                    setMaxAmount('');
                                }}
                                style={{ background: 'none', border: 'none', color: 'var(--accent-red)', fontSize: '0.85rem', cursor: 'pointer', padding: '0.25rem' }}
                            >
                                Clear
                            </button>
                        )}
                    </div>

                    <div className="glass-panel" style={{ padding: '1.5rem', flexGrow: 1 }}>
                        <h3 style={{ margin: '0 0 1rem 0' }}>Recent Transactions</h3>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                            {filteredExpenses.length === 0 ? (
                                <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '2rem' }}>No expenses found.</div>
                            ) : (
                                <table className="responsive-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                                    <thead>
                                        <tr style={{ borderBottom: '1px solid var(--border)', textAlign: 'left', color: 'var(--text-secondary)' }}>
                                            <th style={{ padding: '0.75rem 0.5rem' }}>Date</th>
                                            <th style={{ padding: '0.75rem 0.5rem' }}>Category</th>
                                            <th style={{ padding: '0.75rem 0.5rem' }}>Description</th>
                                            <th style={{ padding: '0.75rem 0.5rem' }}>Type</th>
                                            <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Amount</th>
                                            <th style={{ padding: '0.75rem 0.5rem', textAlign: 'center', width: '100px' }}>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {filteredExpenses.map((e, i) => {
                                            const isEditing = editingExpenseId === e.id;
                                            return (
                                                <tr key={i} style={{ borderBottom: '1px solid var(--border)', verticalAlign: 'middle' }}>
                                                    {isEditing ? (
                                                        <>
                                                            <td data-label="Date" style={{ padding: '0.5rem' }}>
                                                                <input 
                                                                    type="date" 
                                                                    value={editDate} 
                                                                    onChange={opt => setEditDate(opt.target.value)} 
                                                                    style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.3rem 0.5rem', borderRadius: '4px', color: 'var(--text-primary)', fontSize: '0.85rem', width: '100%' }}
                                                                />
                                                            </td>
                                                            <td data-label="Category" style={{ padding: '0.5rem' }}>
                                                                <input 
                                                                    type="text" 
                                                                    value={editCategory} 
                                                                    onChange={opt => setEditCategory(opt.target.value)} 
                                                                    style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.3rem 0.5rem', borderRadius: '4px', color: 'var(--text-primary)', fontSize: '0.85rem', width: '100%' }}
                                                                />
                                                            </td>
                                                            <td data-label="Description" style={{ padding: '0.5rem' }}>
                                                                <input 
                                                                    type="text" 
                                                                    value={editDescription} 
                                                                    onChange={opt => setEditDescription(opt.target.value)} 
                                                                    style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.3rem 0.5rem', borderRadius: '4px', color: 'var(--text-primary)', fontSize: '0.85rem', width: '100%' }}
                                                                />
                                                            </td>
                                                            <td data-label="Type" style={{ padding: '0.5rem' }}>
                                                                <select 
                                                                    value={editType} 
                                                                    onChange={opt => setEditType(opt.target.value)} 
                                                                    style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.3rem 0.5rem', borderRadius: '4px', color: 'var(--text-primary)', fontSize: '0.85rem', width: '100%', cursor: 'pointer' }}
                                                                >
                                                                    <option value="my-personal">My Personal</option>
                                                                    <option value="linked-personal">Linked Personal</option>
                                                                    <option value="joint">Joint</option>
                                                                </select>
                                                            </td>
                                                            <td data-label="Amount" style={{ padding: '0.5rem', textAlign: 'right' }}>
                                                                <input 
                                                                    type="number" 
                                                                    step="0.01" 
                                                                    value={editAmount} 
                                                                    onChange={opt => setEditAmount(opt.target.value)} 
                                                                    style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.3rem 0.5rem', borderRadius: '4px', color: 'var(--text-primary)', fontSize: '0.85rem', width: '100%', textAlign: 'right' }}
                                                                />
                                                            </td>
                                                            <td data-label="Actions" style={{ padding: '0.5rem', textAlign: 'center' }}>
                                                                <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
                                                                    <button onClick={() => handleSaveEdit(e.id)} className="icon-btn" title="Save" style={{ color: 'var(--bullish)' }}>
                                                                        <Check size={16} />
                                                                    </button>
                                                                    <button onClick={() => setEditingExpenseId(null)} className="icon-btn icon-btn--danger" title="Cancel">
                                                                        <X size={16} />
                                                                    </button>
                                                                </div>
                                                            </td>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <td data-label="Date" style={{ padding: '0.75rem 0.5rem', color: 'var(--text-primary)' }}>{new Date(e.date).toLocaleDateString()}</td>
                                                            <td data-label="Category" style={{ padding: '0.75rem 0.5rem' }}>
                                                                <span style={{ background: 'rgba(10, 132, 255, 0.15)', color: 'var(--accent-blue)', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.8rem' }}>
                                                                    {e.category}
                                                                </span>
                                                            </td>
                                                            <td data-label="Description" style={{ padding: '0.75rem 0.5rem', color: 'var(--text-primary)' }}>{e.description || '-'}</td>
                                                            <td data-label="Type" style={{ padding: '0.75rem 0.5rem' }}>
                                                                {e.is_joint ? (
                                                                    <span style={{ color: 'var(--accent-purple)', fontSize: '0.8rem' }}>
                                                                        Joint ({e.payer_id === user?.id ? 'Paid by Me' : 'Paid by Partner'})
                                                                    </span>
                                                                ) : e.owner_id === user?.id ? (
                                                                    <span style={{ color: 'var(--accent-blue)', fontSize: '0.8rem' }}>
                                                                        Personal ({e.payer_id === user?.id ? 'Paid by Me' : 'Paid by Partner'})
                                                                    </span>
                                                                ) : (
                                                                    <span style={{ color: 'var(--accent-green)', fontSize: '0.8rem' }}>
                                                                        Linked Personal ({e.payer_id === user?.id ? 'Paid by Me' : 'Paid by Partner'})
                                                                    </span>
                                                                )}
                                                            </td>
                                                            <td data-label="Amount" style={{ padding: '0.75rem 0.5rem', textAlign: 'right', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                                                                ${e.amount.toLocaleString(undefined, {minimumFractionDigits: 2})}
                                                            </td>
                                                            <td data-label="Actions" style={{ padding: '0.75rem 0.5rem', textAlign: 'center' }}>
                                                                <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
                                                                    <button onClick={() => startEditing(e)} className="icon-btn" title="Edit">
                                                                        <Edit2 size={16} />
                                                                    </button>
                                                                    <button onClick={() => handleDeleteExpense(e.id)} className="icon-btn icon-btn--danger" title="Delete" style={{ color: 'var(--accent-red)' }}>
                                                                        <Trash2 size={16} />
                                                                    </button>
                                                                </div>
                                                            </td>
                                                        </>
                                                    )}
                                                </tr>
                                            );
                                        })}
                                        {/* Dynamic Total row */}
                                        <tr style={{ borderTop: '2px solid var(--border)', background: 'rgba(255, 255, 255, 0.02)' }}>
                                            <td style={{ padding: '1rem 0.5rem', fontWeight: 'bold', color: 'var(--text-primary)' }}>Total</td>
                                            <td style={{ padding: '1rem 0.5rem' }}></td>
                                            <td style={{ padding: '1rem 0.5rem' }}></td>
                                            <td style={{ padding: '1rem 0.5rem' }}></td>
                                            <td style={{ padding: '1rem 0.5rem', textAlign: 'right', fontWeight: 'bold', color: 'var(--text-primary)', fontSize: '1rem' }}>
                                                ${totalAmount.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                                            </td>
                                            <td style={{ padding: '1rem 0.5rem' }}></td>
                                        </tr>
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>
                </div>

                <div className="glass-panel" style={{ padding: '1.5rem', height: 'fit-content' }}>
                    <h3 style={{ margin: '0 0 1rem 0' }}>Add Expense</h3>
                    <form onSubmit={handleAddExpense} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Date</label>
                            <input type="date" required value={date} onChange={e => setDate(e.target.value)} style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }} />
                        </div>
                        
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Category</label>
                            <input type="text" placeholder="e.g. Groceries" required value={category} onChange={e => setCategory(e.target.value)} style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }} />
                        </div>
                        
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Amount</label>
                            <input type="number" placeholder="0.00" step="0.01" required value={amount} onChange={e => setAmount(e.target.value)} style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }} />
                        </div>
                        
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Description</label>
                            <input type="text" placeholder="Optional" value={description} onChange={e => setDescription(e.target.value)} style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }} />
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem' }}>
                            <input type="checkbox" id="joint-checkbox" checked={isJoint} onChange={e => setIsJoint(e.target.checked)} />
                            <label htmlFor="joint-checkbox" style={{ fontSize: '0.9rem', color: 'var(--text-primary)', cursor: 'pointer' }}>Mark as Joint Expense</label>
                        </div>
                        
                        <button type="submit" className="btn btn-primary" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem', padding: '0.75rem', borderRadius: '8px', marginTop: '0.5rem' }}>
                            <Plus size={18} /> Add Record
                        </button>
                    </form>
                </div>
            </div>
        </main>
        
        {uncategorizedExpenses.length > 0 && (
            <CategorizationPopup 
                expenses={uncategorizedExpenses} 
                onClose={() => {
                    setUncategorizedExpenses([]);
                    loadExpenses();
                }} 
                onComplete={() => {
                    setUncategorizedExpenses([]);
                    loadExpenses();
                }} 
            />
        )}

        {showUploadModal && (
            <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
                <div className="glass-panel" style={{ width: '450px', padding: '2rem', position: 'relative', background: 'var(--bg-card)' }}>
                    <button onClick={() => setShowUploadModal(false)} style={{ position: 'absolute', top: '1rem', right: '1rem', background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                        <X size={20} />
                    </button>
                    
                    <h3 style={{ margin: '0 0 1.5rem 0', color: 'var(--text-primary)' }}>Upload Expenses CSV</h3>
                    
                    <form onSubmit={handleModalUpload} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>CSV File</label>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                <input 
                                    type="file" 
                                    accept=".csv" 
                                    id="modal-file-input" 
                                    onChange={(e) => {
                                        const file = e.target.files?.[0];
                                        if (file) setUploadFile(file);
                                    }}
                                    style={{ display: 'none' }}
                                />
                                <button 
                                    type="button"
                                    className="btn"
                                    onClick={() => document.getElementById('modal-file-input')?.click()}
                                    style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.5rem 1rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                                >
                                    Choose File
                                </button>
                                <span style={{ fontSize: '0.9rem', color: uploadFile ? 'var(--text-primary)' : 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '240px' }}>
                                    {uploadFile ? uploadFile.name : 'No file chosen'}
                                </span>
                            </div>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                            <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Default Category (Optional)</label>
                            <input 
                                type="text" 
                                list="existing-categories"
                                placeholder="e.g. Groceries" 
                                value={uploadDefaultCategory} 
                                onChange={e => setUploadDefaultCategory(e.target.value)} 
                                style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }} 
                            />
                            <datalist id="existing-categories">
                                {uniqueCategories.map(cat => (
                                    <option key={cat} value={cat} />
                                ))}
                            </datalist>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                            <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Period/Month of Expense (Optional)</label>
                            <input 
                                type="month" 
                                value={uploadPeriod} 
                                onChange={e => setUploadPeriod(e.target.value)} 
                                style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }} 
                            />
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <input 
                                type="checkbox" 
                                id="modal-joint-checkbox" 
                                checked={uploadIsJoint} 
                                onChange={e => setUploadIsJoint(e.target.checked)} 
                                style={{ cursor: 'pointer' }}
                            />
                            <label htmlFor="modal-joint-checkbox" style={{ fontSize: '0.9rem', color: 'var(--text-primary)', cursor: 'pointer', userSelect: 'none' }}>
                                Mark all transactions as Joint
                            </label>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '1rem' }}>
                            <button 
                                type="button" 
                                onClick={() => setShowUploadModal(false)} 
                                className="btn" 
                                style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', color: 'var(--text-primary)', padding: '0.75rem 1.5rem', borderRadius: '8px', cursor: 'pointer' }}
                            >
                                Cancel
                            </button>
                            <button 
                                type="submit" 
                                className="btn btn-primary" 
                                disabled={!uploadFile || uploadStatus.type === 'uploading'}
                                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.75rem 1.5rem', borderRadius: '8px', cursor: 'pointer' }}
                            >
                                <Check size={18} /> Upload
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        )}
        </>
    );
}

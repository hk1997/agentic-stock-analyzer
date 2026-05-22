import React, { useState, useEffect, useRef } from 'react';
import { apiFetch } from '../../utils/api';
import { Upload, Plus, AlertCircle, CheckCircle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export function ExpensesPage() {
    const [expenses, setExpenses] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    
    // Upload state
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [uploadStatus, setUploadStatus] = useState<{type: 'idle'|'uploading'|'success'|'error', msg: string}>({type: 'idle', msg: ''});

    // Form state
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [category, setCategory] = useState('');
    const [amount, setAmount] = useState('');
    const [description, setDescription] = useState('');
    const [isJoint, setIsJoint] = useState(false);

    const loadExpenses = async () => {
        try {
            const data = await apiFetch('/api/finance/expenses');
            setExpenses(data);
        } catch (error) {
            console.error("Failed to load expenses", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadExpenses();
    }, []);

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

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setUploadStatus({ type: 'uploading', msg: 'Uploading CSV...' });
        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await apiFetch('/api/finance/expenses/upload', {
                method: 'POST',
                body: formData,
            });
            setUploadStatus({ type: 'success', msg: `Successfully added ${res.added} expenses.` });
            loadExpenses();
        } catch (error: any) {
            setUploadStatus({ type: 'error', msg: error.message || 'Failed to upload CSV' });
        } finally {
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
            setTimeout(() => setUploadStatus({ type: 'idle', msg: '' }), 5000);
        }
    };

    // Calculate chart data (group by category)
    const categoryTotals = expenses.reduce((acc, curr) => {
        acc[curr.category] = (acc[curr.category] || 0) + curr.amount;
        return acc;
    }, {} as Record<string, number>);

    const chartData = Object.keys(categoryTotals).map(cat => ({
        category: cat,
        amount: categoryTotals[cat]
    })).sort((a, b) => b.amount - a.amount); // Sort by highest expense

    if (isLoading) return <div className="page-container">Loading...</div>;

    return (
        <div className="page-container" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h1 style={{ margin: 0, color: 'var(--text-primary)' }}>Expenses</h1>
                    <p style={{ color: 'var(--text-secondary)', margin: '0.5rem 0 0 0' }}>Track and manage your cash flow</p>
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    {uploadStatus.type === 'error' && <span style={{ color: 'var(--accent-red)', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}><AlertCircle size={16}/> {uploadStatus.msg}</span>}
                    {uploadStatus.type === 'success' && <span style={{ color: 'var(--accent-green)', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}><CheckCircle size={16}/> {uploadStatus.msg}</span>}
                    
                    <input 
                        type="file" 
                        accept=".csv" 
                        ref={fileInputRef} 
                        style={{ display: 'none' }} 
                        onChange={handleFileUpload}
                    />
                    <button 
                        className="btn" 
                        onClick={() => fileInputRef.current?.click()}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--bg-card)', border: '1px solid var(--border)', padding: '0.5rem 1rem', borderRadius: '8px' }}
                    >
                        <Upload size={18} /> Upload CSV
                    </button>
                </div>
            </header>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: '2rem' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    <div className="glass-panel" style={{ padding: '1.5rem', height: '300px' }}>
                        <h3 style={{ margin: '0 0 1.5rem 0' }}>Expenses by Category</h3>
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                                <XAxis dataKey="category" stroke="var(--text-secondary)" tick={{fontSize: 12}} />
                                <YAxis stroke="var(--text-secondary)" tick={{fontSize: 12}} />
                                <Tooltip 
                                    cursor={{fill: 'var(--hover-bg)'}}
                                    contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '8px' }}
                                    formatter={(value: number) => [`$${value.toLocaleString()}`, 'Amount']}
                                />
                                <Bar dataKey="amount" fill="var(--accent-blue)" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>

                    <div className="glass-panel" style={{ padding: '1.5rem', flexGrow: 1 }}>
                        <h3 style={{ margin: '0 0 1rem 0' }}>Recent Transactions</h3>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                            {expenses.length === 0 ? (
                                <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '2rem' }}>No expenses found.</div>
                            ) : (
                                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                                    <thead>
                                        <tr style={{ borderBottom: '1px solid var(--border)', textAlign: 'left', color: 'var(--text-secondary)' }}>
                                            <th style={{ padding: '0.75rem 0.5rem' }}>Date</th>
                                            <th style={{ padding: '0.75rem 0.5rem' }}>Category</th>
                                            <th style={{ padding: '0.75rem 0.5rem' }}>Description</th>
                                            <th style={{ padding: '0.75rem 0.5rem' }}>Type</th>
                                            <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Amount</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {expenses.map((e, i) => (
                                            <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                                                <td style={{ padding: '0.75rem 0.5rem', color: 'var(--text-primary)' }}>{new Date(e.date).toLocaleDateString()}</td>
                                                <td style={{ padding: '0.75rem 0.5rem' }}>
                                                    <span style={{ background: 'rgba(10, 132, 255, 0.15)', color: 'var(--accent-blue)', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.8rem' }}>
                                                        {e.category}
                                                    </span>
                                                </td>
                                                <td style={{ padding: '0.75rem 0.5rem', color: 'var(--text-primary)' }}>{e.description || '-'}</td>
                                                <td style={{ padding: '0.75rem 0.5rem' }}>
                                                    {e.is_joint ? (
                                                        <span style={{ color: 'var(--accent-purple)', fontSize: '0.8rem' }}>Joint</span>
                                                    ) : (
                                                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>Personal</span>
                                                    )}
                                                </td>
                                                <td style={{ padding: '0.75rem 0.5rem', textAlign: 'right', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                                                    ${e.amount.toLocaleString(undefined, {minimumFractionDigits: 2})}
                                                </td>
                                            </tr>
                                        ))}
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
        </div>
    );
}

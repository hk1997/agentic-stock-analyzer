import React, { useState, useEffect } from 'react';
import { apiFetch } from '../../utils/api';
import { useAuth } from '../../hooks/useAuth';
import { Activity, DollarSign, TrendingUp, TrendingDown, CreditCard, Link as LinkIcon, Plus } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export function DashboardPage() {
    const { user } = useAuth();
    const [netWorth, setNetWorth] = useState(0);
    const [nwHistory, setNwHistory] = useState<any[]>([]);
    const [expenses, setExpenses] = useState<any[]>([]);
    const [portfolio, setPortfolio] = useState<{total_value: number, total_pnl: number}>({total_value: 0, total_pnl: 0});
    const [linkedUsers, setLinkedUsers] = useState<any[]>([]);
    const [linkEmail, setLinkEmail] = useState('');
    const [isLoading, setIsLoading] = useState(true);

    const loadData = async () => {
        try {
            const [nwData, expData, portData, linkData] = await Promise.all([
                apiFetch('/api/finance/net-worth-history'),
                apiFetch('/api/finance/expenses'),
                apiFetch('/api/finance/unified-portfolio'),
                apiFetch('/api/auth/linked-accounts')
            ]);
            
            if (nwData.length > 0) {
                setNetWorth(nwData[nwData.length - 1].net_worth);
                setNwHistory(nwData);
            }
            setExpenses(expData);
            setPortfolio(portData);
            setLinkedUsers(linkData);
        } catch (error) {
            console.error("Dashboard data load failed", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    const handleLinkAccount = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await apiFetch('/api/auth/link-account', {
                method: 'POST',
                body: JSON.stringify({ target_email: linkEmail })
            });
            setLinkEmail('');
            loadData();
        } catch (error) {
            alert("Failed to link account. Please check the email.");
        }
    };

    const currentMonthExpenses = expenses
        .filter(e => new Date(e.date).getMonth() === new Date().getMonth())
        .reduce((sum, e) => sum + e.amount, 0);

    if (isLoading) return <div className="page-container">Loading your financial summary...</div>;

    return (
        <main className="main-content">
            <header className="header" style={{ alignItems: 'flex-end' }}>
                <div>
                    <h1 style={{ margin: 0, color: 'var(--text-primary)' }}>Welcome back, {user?.name || user?.email.split('@')[0]}</h1>
                    <p style={{ color: 'var(--text-secondary)', margin: '0.5rem 0 0 0' }}>Here's your 360° financial overview.</p>
                </div>
            </header>

            {/* Quick Stats */}
            <div className="stats-grid">
                <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h3 style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '1rem', fontWeight: '500' }}>Total Net Worth</h3>
                        <div style={{ background: 'rgba(10, 132, 255, 0.15)', padding: '0.5rem', borderRadius: '8px', color: 'var(--accent-blue)' }}>
                            <Activity size={20} />
                        </div>
                    </div>
                    <div style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                        ${netWorth.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                    </div>
                </div>

                <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h3 style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '1rem', fontWeight: '500' }}>Investments</h3>
                        <div style={{ background: 'rgba(48, 209, 88, 0.15)', padding: '0.5rem', borderRadius: '8px', color: 'var(--accent-green)' }}>
                            <TrendingUp size={20} />
                        </div>
                    </div>
                    <div style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                        ${portfolio.total_value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                    </div>
                    <div style={{ fontSize: '0.9rem', color: (portfolio.total_pnl || 0) >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                        {(portfolio.total_pnl || 0) >= 0 ? '+' : ''}${(portfolio.total_pnl || 0).toLocaleString(undefined, {minimumFractionDigits: 2})} P&L
                    </div>
                </div>

                <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h3 style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '1rem', fontWeight: '500' }}>This Month's Spend</h3>
                        <div style={{ background: 'rgba(255, 69, 58, 0.15)', padding: '0.5rem', borderRadius: '8px', color: 'var(--accent-red)' }}>
                            <CreditCard size={20} />
                        </div>
                    </div>
                    <div style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                        ${currentMonthExpenses.toLocaleString(undefined, {minimumFractionDigits: 2})}
                    </div>
                </div>
            </div>

            <div className="dashboard-layout-grid">
                <div className="glass-panel" style={{ padding: '1.5rem', height: '400px' }}>
                    <h3 style={{ margin: '0 0 1.5rem 0' }}>Net Worth Trajectory</h3>
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={nwHistory} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                            <defs>
                                <linearGradient id="colorNwMain" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="var(--accent-blue)" stopOpacity={0.8}/>
                                    <stop offset="95%" stopColor="var(--accent-blue)" stopOpacity={0}/>
                                </linearGradient>
                            </defs>
                            <XAxis dataKey="date" stroke="var(--text-secondary)" />
                            <YAxis stroke="var(--text-secondary)" />
                            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                            <Tooltip 
                                contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '8px' }}
                                formatter={(value: number) => [`$${value.toLocaleString()}`, 'Net Worth']}
                            />
                            <Area type="monotone" dataKey="net_worth" stroke="var(--accent-blue)" fillOpacity={1} fill="url(#colorNwMain)" />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                        <h3 style={{ margin: '0 0 1rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <LinkIcon size={18} /> Linked Accounts
                        </h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            {linkedUsers.length === 0 ? (
                                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', margin: 0 }}>No accounts linked yet.</p>
                            ) : (
                                linkedUsers.map(u => (
                                    <div key={u.id} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'var(--bg-main)', padding: '0.75rem', borderRadius: '8px' }}>
                                        <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'var(--accent-blue)', color: 'white', display: 'flex', justifyContent: 'center', alignItems: 'center', fontWeight: 'bold' }}>
                                            {u.name ? u.name[0].toUpperCase() : u.email[0].toUpperCase()}
                                        </div>
                                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                                            <span style={{ fontWeight: '500' }}>{u.name || 'User'}</span>
                                            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{u.email}</span>
                                        </div>
                                    </div>
                                ))
                            )}

                            <form onSubmit={handleLinkAccount} style={{ marginTop: '0.5rem', display: 'flex', gap: '0.5rem' }}>
                                <input 
                                    type="email" 
                                    placeholder="Partner's Email" 
                                    required 
                                    value={linkEmail}
                                    onChange={(e) => setLinkEmail(e.target.value)}
                                    style={{ flex: 1, background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.5rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                                />
                                <button type="submit" className="btn btn-primary" style={{ padding: '0.5rem 1rem', borderRadius: '8px' }}>
                                    Link
                                </button>
                            </form>
                        </div>
                    </div>

                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                        <h3 style={{ margin: '0 0 1rem 0' }}>Recent Expenses</h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                            {expenses.slice(0, 4).map((e, i) => (
                                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border)' }}>
                                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                                        <span style={{ fontWeight: '500' }}>{e.category}</span>
                                        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{new Date(e.date).toLocaleDateString()}</span>
                                    </div>
                                    <div style={{ fontWeight: 'bold', color: 'var(--text-primary)' }}>
                                        ${e.amount.toLocaleString(undefined, {minimumFractionDigits: 2})}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </main>
    );
}

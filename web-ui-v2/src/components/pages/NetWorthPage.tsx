import React, { useState, useEffect } from 'react';
import { apiFetch } from '../../utils/api';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Trash2, Shield, Plus, DollarSign, Wallet, CreditCard, Landmark, Home, Coins, TrendingUp } from 'lucide-react';

export function NetWorthPage() {
    const [history, setHistory] = useState<any[]>([]);
    const [assets, setAssets] = useState<any[]>([]);
    const [accounts, setAccounts] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [resolution, setResolution] = useState<'daily' | 'monthly'>('monthly');

    // Account Ledger Drawer state
    const [selectedAccount, setSelectedAccount] = useState<any | null>(null);
    const [transactions, setTransactions] = useState<any[]>([]);
    const [isDrawerLoading, setIsDrawerLoading] = useState(false);
    const [txAmount, setTxAmount] = useState('');
    const [txType, setTxType] = useState('expense');
    const [txCategory, setTxCategory] = useState('');
    const [txDescription, setTxDescription] = useState('');
    const [txDate, setTxDate] = useState(new Date().toISOString().split('T')[0]);
    const [isTransferForm, setIsTransferForm] = useState(false);
    const [transferTargetId, setTransferTargetId] = useState('');
    
    // Manual Asset Form state
    const [assetType, setAssetType] = useState('Cash');
    const [assetValue, setAssetValue] = useState('');
    const [assetDescription, setAssetDescription] = useState('');

    // Account Form state
    const [accountName, setAccountName] = useState('');
    const [accountClassification, setAccountClassification] = useState('asset');
    const [accountClass, setAccountClass] = useState('cash');
    const [accountBalance, setAccountBalance] = useState('');
    const [accountCurrency, setAccountCurrency] = useState('USD');
    const [accountDescription, setAccountDescription] = useState('');
    const [exchangeRates, setExchangeRates] = useState<any>({
        USD_TO_GBP: 1.0 / 1.27,
        USD_TO_INR: 1.0 / 0.012,
        USD_TO_EUR: 1.0 / 1.08
    });

    const loadData = async (currentResolution: 'daily' | 'monthly' = resolution) => {
        try {
            const [historyData, assetsData, accountsData, ratesData] = await Promise.all([
                apiFetch(`/api/finance/net-worth-history?resolution=${currentResolution}`),
                apiFetch('/api/finance/manual-assets'),
                apiFetch('/api/finance/accounts'),
                apiFetch('/api/finance/exchange-rates')
            ]);
            setHistory(historyData);
            setAssets(assetsData);
            setAccounts(accountsData);
            setExchangeRates(ratesData);
        } catch (error) {
            console.error("Failed to load net worth data", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadData(resolution);
    }, [resolution]);

    const formatDateTick = (tickVal: string) => {
        if (!tickVal) return '';
        try {
            const date = new Date(tickVal);
            if (resolution === 'monthly') {
                return date.toLocaleDateString(undefined, { month: 'short', year: '2-digit' });
            }
            return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
        } catch {
            return tickVal;
        }
    };

    // Auto-update classification when account class changes
    const handleAccountClassChange = (selectedClass: string) => {
        setAccountClass(selectedClass);
        if (selectedClass === 'credit_card' || selectedClass === 'loan') {
            setAccountClassification('liability');
        } else {
            setAccountClassification('asset');
        }
    };

    const handleAddAsset = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await apiFetch('/api/finance/manual-assets', {
                method: 'POST',
                body: JSON.stringify({
                    asset_type: assetType,
                    value: parseFloat(assetValue),
                    description: assetDescription
                })
            });
            setAssetValue('');
            setAssetDescription('');
            loadData();
        } catch (error) {
            console.error("Failed to add asset", error);
        }
    };

    const handleDeleteAsset = async (id: number) => {
        if (!confirm("Are you sure you want to delete this asset?")) return;
        try {
            await apiFetch(`/api/finance/manual-assets/${id}`, {
                method: 'DELETE'
            });
            loadData();
        } catch (error) {
            console.error("Failed to delete asset", error);
        }
    };

    const handleAddAccount = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await apiFetch('/api/finance/accounts', {
                method: 'POST',
                body: JSON.stringify({
                    name: accountName,
                    classification: accountClassification,
                    account_class: accountClass,
                    balance: parseFloat(accountBalance),
                    currency: accountCurrency,
                    description: accountDescription
                })
            });
            setAccountName('');
            setAccountBalance('');
            setAccountDescription('');
            loadData();
        } catch (error) {
            console.error("Failed to add account", error);
        }
    };

    const handleDeleteAccount = async (id: number) => {
        if (!confirm("Are you sure you want to delete this account?")) return;
        try {
            await apiFetch(`/api/finance/accounts/${id}`, {
                method: 'DELETE'
            });
            if (selectedAccount && selectedAccount.id === id) {
                setSelectedAccount(null);
            }
            loadData();
        } catch (error) {
            console.error("Failed to delete account", error);
        }
    };

    const handleOpenLedger = async (account: any) => {
        setSelectedAccount(account);
        setIsDrawerLoading(true);
        setIsTransferForm(false);
        setTxAmount('');
        setTxCategory('');
        setTxDescription('');
        setTxDate(new Date().toISOString().split('T')[0]);
        setTransferTargetId('');
        try {
            const data = await apiFetch(`/api/finance/accounts/${account.id}/transactions`);
            setTransactions(data);
        } catch (error) {
            console.error("Failed to fetch transactions", error);
        } finally {
            setIsDrawerLoading(false);
        }
    };

    const handleAddTransaction = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedAccount) return;
        try {
            if (isTransferForm) {
                await apiFetch('/api/finance/accounts/transfer', {
                    method: 'POST',
                    body: JSON.stringify({
                        from_account_id: selectedAccount.id,
                        to_account_id: parseInt(transferTargetId),
                        amount: parseFloat(txAmount),
                        description: txDescription,
                        date: new Date(txDate).toISOString()
                    })
                });
            } else {
                const amt = parseFloat(txAmount);
                const signedAmt = txType === 'expense' ? -Math.abs(amt) : Math.abs(amt);

                await apiFetch(`/api/finance/accounts/${selectedAccount.id}/transactions`, {
                    method: 'POST',
                    body: JSON.stringify({
                        amount: signedAmt,
                        transaction_type: txType,
                        category: txCategory,
                        description: txDescription,
                        date: new Date(txDate).toISOString()
                    })
                });
            }
            setTxAmount('');
            setTxDescription('');
            setTxCategory('');
            
            const txData = await apiFetch(`/api/finance/accounts/${selectedAccount.id}/transactions`);
            setTransactions(txData);
            loadData(resolution);
            
            const updatedAccounts = await apiFetch('/api/finance/accounts');
            setAccounts(updatedAccounts);
            const updatedAcc = updatedAccounts.find((a: any) => a.id === selectedAccount.id);
            if (updatedAcc) {
                setSelectedAccount(updatedAcc);
            }
        } catch (error) {
            console.error("Failed to add transaction", error);
        }
    };

    const handleDeleteTransaction = async (txId: number) => {
        if (!selectedAccount) return;
        if (!confirm("Are you sure you want to delete this transaction? This will restore the account balance.")) return;
        try {
            await apiFetch(`/api/finance/accounts/${selectedAccount.id}/transactions/${txId}`, {
                method: 'DELETE'
            });
            const txData = await apiFetch(`/api/finance/accounts/${selectedAccount.id}/transactions`);
            setTransactions(txData);
            loadData(resolution);
            
            const updatedAccounts = await apiFetch('/api/finance/accounts');
            setAccounts(updatedAccounts);
            const updatedAcc = updatedAccounts.find((a: any) => a.id === selectedAccount.id);
            if (updatedAcc) {
                setSelectedAccount(updatedAcc);
            }
        } catch (error) {
            console.error("Failed to delete transaction", error);
        }
    };

    const getCurrencySymbol = (currency: string) => {
        switch (currency.toUpperCase()) {
            case 'INR': return '₹';
            case 'GBP': return '£';
            case 'EUR': return '€';
            default: return '$';
        }
    };

    const getAccountClassIcon = (accountClass: string) => {
        switch (accountClass) {
            case 'portfolio': return <TrendingUp size={16} style={{ color: 'var(--accent-blue)' }} />;
            case 'real_estate': return <Home size={16} style={{ color: 'var(--accent-orange)' }} />;
            case 'gold': return <Coins size={16} style={{ color: 'var(--accent-yellow)' }} />;
            case 'pension': return <Shield size={16} style={{ color: 'var(--accent-green)' }} />;
            case 'credit_card': return <CreditCard size={16} style={{ color: 'var(--accent-red)' }} />;
            case 'loan': return <Landmark size={16} style={{ color: 'var(--accent-purple)' }} />;
            default: return <Wallet size={16} style={{ color: 'var(--accent)' }} />;
        }
    };

    const getAccountClassLabel = (accountClass: string) => {
        switch (accountClass) {
            case 'real_estate': return 'Real Estate';
            case 'credit_card': return 'Credit Card';
            default: return accountClass.charAt(0).toUpperCase() + accountClass.slice(1);
        }
    };

    if (isLoading) return <div className="page-container">Loading...</div>;

    const currentNetWorth = history.length > 0 ? history[history.length - 1].net_worth : 0;

    const assetAccounts = accounts.filter(a => a.classification === 'asset');
    const liabilityAccounts = accounts.filter(a => a.classification === 'liability');

    return (
        <main className="main-content" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            <header>
                <h1 style={{ margin: 0, color: 'var(--text-primary)' }}>Net Worth</h1>
                <p style={{ color: 'var(--text-secondary)', margin: '0.5rem 0 0 0' }}>Track your total assets, liabilities, and accounts in any currency</p>
            </header>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '2rem' }}>
                {/* Left Column */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    {/* Net Worth KPI Card */}
                    <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ flex: 1 }}>
                            <h3 style={{ color: 'var(--text-secondary)', margin: '0 0 0.5rem 0', fontSize: '0.9rem' }}>Current Net Worth</h3>
                            <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
                                ${currentNetWorth.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </div>
                            <div style={{ display: 'flex', gap: '1.5rem', marginTop: '0.75rem', padding: '0.5rem 0 0 0', borderTop: '1px solid rgba(255, 255, 255, 0.05)' }}>
                                <div style={{ display: 'flex', flexDirection: 'column' }}>
                                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>GBP Equivalent</span>
                                    <span style={{ fontSize: '1.1rem', fontWeight: '600', color: 'var(--text-primary)' }}>
                                        £{(currentNetWorth * (exchangeRates?.USD_TO_GBP || 0.7874)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                    </span>
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column' }}>
                                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>INR Equivalent</span>
                                    <span style={{ fontSize: '1.1rem', fontWeight: '600', color: 'var(--text-primary)' }}>
                                        ₹{(currentNetWorth * (exchangeRates?.USD_TO_INR || 83.33)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                    </span>
                                </div>
                            </div>
                        </div>
                        <div style={{ padding: '1rem', background: 'rgba(0, 242, 254, 0.08)', borderRadius: '14px', border: '1px solid rgba(0, 242, 254, 0.15)', alignSelf: 'flex-start' }}>
                            <Landmark size={32} style={{ color: 'var(--accent)' }} />
                        </div>
                    </div>

                    {/* Chart Panel */}
                    <div className="glass-panel" style={{ padding: '1.5rem', height: '350px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                            <h3 style={{ margin: 0 }}>Net Worth Trend</h3>
                            <div style={{ 
                                display: 'flex', 
                                background: 'rgba(255, 255, 255, 0.05)', 
                                padding: '2px', 
                                borderRadius: '8px', 
                                border: '1px solid var(--glass-border)' 
                            }}>
                                <button 
                                    onClick={() => setResolution('daily')}
                                    style={{
                                        background: resolution === 'daily' ? 'rgba(0, 242, 254, 0.15)' : 'transparent',
                                        border: 'none',
                                        color: resolution === 'daily' ? 'var(--accent)' : 'var(--text-secondary)',
                                        padding: '4px 12px',
                                        borderRadius: '6px',
                                        fontSize: '0.8rem',
                                        fontWeight: '600',
                                        cursor: 'pointer',
                                        transition: 'all 0.2s'
                                    }}
                                >
                                    Daily
                                </button>
                                <button 
                                    onClick={() => setResolution('monthly')}
                                    style={{
                                        background: resolution === 'monthly' ? 'rgba(0, 242, 254, 0.15)' : 'transparent',
                                        border: 'none',
                                        color: resolution === 'monthly' ? 'var(--accent)' : 'var(--text-secondary)',
                                        padding: '4px 12px',
                                        borderRadius: '6px',
                                        fontSize: '0.8rem',
                                        fontWeight: '600',
                                        cursor: 'pointer',
                                        transition: 'all 0.2s'
                                    }}
                                >
                                    Monthly
                                </button>
                            </div>
                        </div>
                        <ResponsiveContainer width="100%" height="80%">
                            <AreaChart data={history} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="colorNw" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="var(--accent-blue)" stopOpacity={0.8}/>
                                        <stop offset="95%" stopColor="var(--accent-blue)" stopOpacity={0}/>
                                    </linearGradient>
                                </defs>
                                <XAxis dataKey="date" stroke="var(--text-secondary)" tickFormatter={formatDateTick} />
                                <YAxis stroke="var(--text-secondary)" />
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                                <Tooltip 
                                    contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '8px' }}
                                    labelFormatter={(label: string) => {
                                        try {
                                            const date = new Date(label);
                                            return date.toLocaleDateString(undefined, { dateStyle: 'medium' });
                                        } catch {
                                            return label;
                                        }
                                    }}
                                    formatter={(value: number) => [`$${value.toLocaleString()}`, 'Net Worth']}
                                />
                                <Area type="monotone" dataKey="net_worth" stroke="var(--accent-blue)" fillOpacity={1} fill="url(#colorNw)" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>

                    {/* Asset Accounts Ledger */}
                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                        <h3 style={{ margin: '0 0 1.25rem 0', color: 'var(--accent)' }}>Asset Accounts</h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                            {assetAccounts.length === 0 ? (
                                <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', textAlign: 'center', padding: '1rem' }}>
                                    No asset accounts added yet.
                                </div>
                            ) : (
                                assetAccounts.map(a => (
                                    <div 
                                        key={a.id} 
                                        onClick={() => handleOpenLedger(a)}
                                        style={{ 
                                            display: 'flex', 
                                            justifyContent: 'space-between', 
                                            alignItems: 'center', 
                                            padding: '0.75rem 1rem', 
                                            background: 'rgba(255, 255, 255, 0.015)',
                                            border: '1px solid var(--glass-border)',
                                            borderRadius: '12px',
                                            cursor: 'pointer',
                                            transition: 'background 0.2s'
                                        }}
                                        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)'}
                                        onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.015)'}
                                    >
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                            <div style={{ padding: '0.5rem', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '8px' }}>
                                                {getAccountClassIcon(a.account_class)}
                                            </div>
                                            <div>
                                                <div style={{ fontWeight: '600', color: 'var(--text-primary)', fontSize: '0.92rem' }}>{a.name}</div>
                                                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', gap: '0.4rem', marginTop: '0.15rem' }}>
                                                    <span style={{ textTransform: 'uppercase' }}>{getAccountClassLabel(a.account_class)}</span>
                                                    {a.description && <span>• {a.description}</span>}
                                                </div>
                                            </div>
                                        </div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                            <div style={{ textAlign: 'right' }}>
                                                <div style={{ fontWeight: 'bold', color: 'var(--text-primary)' }}>
                                                    {getCurrencySymbol(a.currency)}{a.balance.toLocaleString()}
                                                </div>
                                                {a.currency !== 'USD' && (
                                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                                                        ~${a.balance_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })} USD
                                                    </div>
                                                )}
                                            </div>
                                            <button 
                                                className="icon-btn icon-btn--danger" 
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDeleteAccount(a.id);
                                                }}
                                                style={{ padding: '0.4rem', borderRadius: '8px' }}
                                                title="Delete Account"
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* Liability Accounts Ledger */}
                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                        <h3 style={{ margin: '0 0 1.25rem 0', color: 'var(--accent-red)' }}>Liability Accounts</h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                            {liabilityAccounts.length === 0 ? (
                                <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', textAlign: 'center', padding: '1rem' }}>
                                    No liabilities added yet. Track loans, cards, or family debts here.
                                </div>
                            ) : (
                                liabilityAccounts.map(a => (
                                    <div 
                                        key={a.id} 
                                        onClick={() => handleOpenLedger(a)}
                                        style={{ 
                                            display: 'flex', 
                                            justifyContent: 'space-between', 
                                            alignItems: 'center', 
                                            padding: '0.75rem 1rem', 
                                            background: 'rgba(255, 255, 255, 0.015)',
                                            border: '1px solid var(--glass-border)',
                                            borderRadius: '12px',
                                            cursor: 'pointer',
                                            transition: 'background 0.2s'
                                        }}
                                        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)'}
                                        onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.015)'}
                                    >
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                            <div style={{ padding: '0.5rem', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '8px' }}>
                                                {getAccountClassIcon(a.account_class)}
                                            </div>
                                            <div>
                                                <div style={{ fontWeight: '600', color: 'var(--text-primary)', fontSize: '0.92rem' }}>{a.name}</div>
                                                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', gap: '0.4rem', marginTop: '0.15rem' }}>
                                                    <span style={{ textTransform: 'uppercase' }}>{getAccountClassLabel(a.account_class)}</span>
                                                    {a.description && <span>• {a.description}</span>}
                                                </div>
                                            </div>
                                        </div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                            <div style={{ textAlign: 'right' }}>
                                                <div style={{ fontWeight: 'bold', color: 'var(--accent-red)' }}>
                                                    -{getCurrencySymbol(a.currency)}{a.balance.toLocaleString()}
                                                </div>
                                                {a.currency !== 'USD' && (
                                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                                                        ~${a.balance_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })} USD
                                                    </div>
                                                )}
                                            </div>
                                            <button 
                                                className="icon-btn icon-btn--danger" 
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDeleteAccount(a.id);
                                                }}
                                                style={{ padding: '0.4rem', borderRadius: '8px' }}
                                                title="Delete Account"
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>

                {/* Right Column */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    {/* Add Account Form */}
                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                        <h3 style={{ margin: '0 0 1rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <Plus size={18} /> Add Financial Account
                        </h3>
                        <form onSubmit={handleAddAccount} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Account Name</label>
                                <input 
                                    type="text" 
                                    placeholder="e.g. HSBC Savings, Trading 212, Mummy Loan"
                                    required
                                    value={accountName}
                                    onChange={(e) => setAccountName(e.target.value)}
                                    style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                                />
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                    <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Class</label>
                                    <select 
                                        value={accountClass}
                                        onChange={(e) => handleAccountClassChange(e.target.value)}
                                        style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                                    >
                                        <option value="cash">Cash/Bank</option>
                                        <option value="portfolio">Stock Portfolio</option>
                                        <option value="real_estate">Real Estate</option>
                                        <option value="gold">Gold</option>
                                        <option value="pension">Pension</option>
                                        <option value="credit_card">Credit Card</option>
                                        <option value="loan">Loan/Debt</option>
                                        <option value="other">Other</option>
                                    </select>
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                    <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Type</label>
                                    <select 
                                        value={accountClassification}
                                        onChange={(e) => setAccountClassification(e.target.value)}
                                        style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                                    >
                                        <option value="asset">Asset (Adds to NW)</option>
                                        <option value="liability">Liability (Subtracts from NW)</option>
                                    </select>
                                </div>
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                    <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Currency</label>
                                    <select 
                                        value={accountCurrency}
                                        onChange={(e) => setAccountCurrency(e.target.value)}
                                        style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                                    >
                                        <option value="USD">USD ($)</option>
                                        <option value="GBP">GBP (£)</option>
                                        <option value="INR">INR (₹)</option>
                                        <option value="EUR">EUR (€)</option>
                                    </select>
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                    <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                        {accountClass === 'portfolio' ? 'Initial Cash Balance' : 'Balance'}
                                    </label>
                                    <input 
                                        type="number"
                                        step="any"
                                        placeholder="0.00"
                                        required
                                        value={accountBalance}
                                        onChange={(e) => setAccountBalance(e.target.value)}
                                        style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                                    />
                                </div>
                            </div>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Description (Optional)</label>
                                <input 
                                    type="text" 
                                    placeholder="Notes..."
                                    value={accountDescription}
                                    onChange={(e) => setAccountDescription(e.target.value)}
                                    style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                                />
                            </div>

                            <button type="submit" className="btn btn-primary" style={{ padding: '0.75rem', borderRadius: '8px', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}>
                                <Plus size={16} /> Add Account
                            </button>
                        </form>
                    </div>

                    {/* Add Manual Asset Form */}
                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                        <h3 style={{ margin: '0 0 1rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <Plus size={18} /> Add Manual Asset
                        </h3>
                        <form onSubmit={handleAddAsset} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            <select 
                                value={assetType}
                                onChange={(e) => setAssetType(e.target.value)}
                                style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                            >
                                <option>Cash</option>
                                <option>Real Estate</option>
                                <option>Vehicles</option>
                                <option>Crypto</option>
                                <option>Other</option>
                            </select>
                            <input 
                                type="number" 
                                placeholder="Value ($)"
                                required
                                value={assetValue}
                                onChange={(e) => setAssetValue(e.target.value)}
                                style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                            />
                            <input 
                                type="text" 
                                placeholder="Description (Optional)"
                                value={assetDescription}
                                onChange={(e) => setAssetDescription(e.target.value)}
                                style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                            />
                            <button type="submit" className="btn btn-primary" style={{ padding: '0.75rem', borderRadius: '8px', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}>
                                <Plus size={16} /> Add Asset
                            </button>
                        </form>
                    </div>

                    {/* Manual Assets List */}
                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                        <h3 style={{ margin: '0 0 1rem 0' }}>Manual Assets</h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                            {assets.length === 0 ? (
                                <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>No manual assets added yet.</div>
                            ) : (
                                assets.map(a => (
                                    <div key={a.id} style={{ 
                                        display: 'flex', 
                                        justifyContent: 'space-between', 
                                        alignItems: 'center',
                                        paddingBottom: '0.5rem', 
                                        borderBottom: '1px solid var(--border)' 
                                    }}>
                                        <div>
                                            <div style={{ fontWeight: '500', color: 'var(--text-primary)', fontSize: '0.9rem' }}>{a.asset_type}</div>
                                            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{a.description}</div>
                                        </div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                            <div style={{ fontWeight: 'bold', color: 'var(--text-primary)' }}>
                                                ${a.value.toLocaleString()}
                                            </div>
                                            <button 
                                                className="icon-btn icon-btn--danger" 
                                                onClick={() => handleDeleteAsset(a.id)}
                                                style={{ padding: '0.3rem', borderRadius: '6px' }}
                                                title="Delete Asset"
                                            >
                                                <Trash2 size={12} />
                                            </button>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            </div>
            
            <style>{`
                @keyframes slideIn {
                    from { transform: translateX(100%); }
                    to { transform: translateX(0); }
                }
            `}</style>

            {/* Slide-over Ledger Drawer */}
            {selectedAccount && (
                <div style={{
                    position: 'fixed',
                    top: 0,
                    right: 0,
                    width: '450px',
                    height: '100vh',
                    background: 'rgba(15, 23, 42, 0.95)',
                    backdropFilter: 'blur(20px)',
                    borderLeft: '1px solid var(--glass-border)',
                    boxShadow: '-10px 0 30px rgba(0, 0, 0, 0.5)',
                    zIndex: 1000,
                    display: 'flex',
                    flexDirection: 'column',
                    animation: 'slideIn 0.3s ease-out'
                }}>
                    {/* Drawer Header */}
                    <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                            <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>{selectedAccount.name}</h3>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                                Ledger &bull; {getAccountClassLabel(selectedAccount.account_class)}
                            </div>
                        </div>
                        <button 
                            onClick={() => setSelectedAccount(null)}
                            style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '1.25rem' }}
                        >
                            &times;
                        </button>
                    </div>

                    {/* Balance summary */}
                    <div style={{ padding: '1rem 1.5rem', background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Current Balance:</span>
                        <span style={{ fontSize: '1.25rem', fontWeight: 'bold', color: selectedAccount.classification === 'liability' ? 'var(--accent-red)' : 'var(--text-primary)' }}>
                            {selectedAccount.classification === 'liability' ? '-' : ''}{getCurrencySymbol(selectedAccount.currency)}{selectedAccount.balance.toLocaleString()}
                        </span>
                    </div>

                    {/* Scrollable transactions list & add transaction form */}
                    <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        
                        {/* Transaction Logging Form */}
                        <div className="glass-panel" style={{ padding: '1rem' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                                <h4 style={{ margin: 0, fontSize: '0.9rem' }}>Log Transaction</h4>
                                <button 
                                    type="button"
                                    onClick={() => setIsTransferForm(!isTransferForm)}
                                    style={{ background: 'transparent', border: 'none', color: 'var(--accent)', fontSize: '0.75rem', cursor: 'pointer', fontWeight: '600' }}
                                >
                                    {isTransferForm ? "Switch to standard" : "Transfer money"}
                                </button>
                            </div>
                            
                            <form onSubmit={handleAddTransaction} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                                {isTransferForm ? (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                        <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Destination Account</label>
                                        <select 
                                            required
                                            value={transferTargetId}
                                            onChange={(e) => setTransferTargetId(e.target.value)}
                                            style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.5rem', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem' }}
                                        >
                                            <option value="">-- Select Destination --</option>
                                            {accounts
                                                .filter(a => a.id !== selectedAccount.id)
                                                .map(a => (
                                                    <option key={a.id} value={a.id}>
                                                        {a.name} ({a.currency})
                                                    </option>
                                                ))
                                            }
                                        </select>
                                    </div>
                                ) : (
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                            <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Type</label>
                                            <select 
                                                value={txType}
                                                onChange={(e) => setTxType(e.target.value)}
                                                style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.5rem', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem' }}
                                            >
                                                <option value="expense">Expense/Debit</option>
                                                <option value="income">Income/Credit</option>
                                            </select>
                                        </div>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                            <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Category</label>
                                            <input 
                                                type="text" 
                                                placeholder="e.g. Salary, Food"
                                                value={txCategory}
                                                onChange={(e) => setTxCategory(e.target.value)}
                                                style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.5rem', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem' }}
                                            />
                                        </div>
                                    </div>
                                )}

                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                        <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Amount ({selectedAccount.currency})</label>
                                        <input 
                                            type="number"
                                            step="any"
                                            required
                                            placeholder="0.00"
                                            value={txAmount}
                                            onChange={(e) => setTxAmount(e.target.value)}
                                            style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.5rem', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem' }}
                                        />
                                    </div>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                        <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Date</label>
                                        <input 
                                            type="date"
                                            required
                                            value={txDate}
                                            onChange={(e) => setTxDate(e.target.value)}
                                            style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.5rem', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem' }}
                                        />
                                    </div>
                                </div>

                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                                    <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Description</label>
                                    <input 
                                        type="text" 
                                        placeholder="e.g. Weekly shop, Salary payout"
                                        value={txDescription}
                                        onChange={(e) => setTxDescription(e.target.value)}
                                        style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.5rem', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '0.8rem' }}
                                    />
                                </div>

                                <button type="submit" className="btn btn--primary" style={{ padding: '0.5rem', fontSize: '0.8rem', marginTop: '0.25rem' }}>
                                    {isTransferForm ? "Execute Transfer" : "Add Transaction"}
                                </button>
                            </form>
                        </div>

                        {/* Transactions Ledger */}
                        <div>
                            <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.9rem' }}>Transaction History</h4>
                            {isDrawerLoading ? (
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textAlign: 'center' }}>Loading ledger...</div>
                            ) : transactions.length === 0 ? (
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textAlign: 'center', padding: '1rem' }}>
                                    No transactions recorded yet.
                                </div>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                    {transactions.map(t => {
                                        const isDebit = t.amount < 0;
                                        return (
                                            <div key={t.id} style={{ 
                                                display: 'flex', 
                                                justifyContent: 'space-between', 
                                                alignItems: 'center', 
                                                padding: '0.6rem 0.75rem', 
                                                background: 'rgba(255,255,255,0.01)',
                                                border: '1px solid var(--glass-border)',
                                                borderRadius: '8px',
                                                fontSize: '0.8rem'
                                            }}>
                                                <div>
                                                    <div style={{ fontWeight: '600', color: 'var(--text-primary)' }}>{t.description || 'Transaction'}</div>
                                                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.1rem', display: 'flex', gap: '0.3rem' }}>
                                                        <span>{new Date(t.date).toLocaleDateString(undefined, { dateStyle: 'short' })}</span>
                                                        {t.category && <span>&bull; {t.category}</span>}
                                                        {t.transaction_type.startsWith('transfer') && <span style={{ color: 'var(--accent)', textTransform: 'uppercase', fontSize: '0.65rem' }}>{t.transaction_type.replace('_', ' ')}</span>}
                                                    </div>
                                                </div>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                    <span style={{ fontWeight: 'bold', color: isDebit ? 'var(--accent-red)' : 'var(--accent-green)' }}>
                                                        {isDebit ? '-' : '+'}{getCurrencySymbol(selectedAccount.currency)}{Math.abs(t.amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                                    </span>
                                                    <button 
                                                        onClick={() => handleDeleteTransaction(t.id)}
                                                        style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '0.2rem' }}
                                                        title="Delete transaction"
                                                    >
                                                        <Trash2 size={12} />
                                                    </button>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>

                    </div>
                </div>
            )}
        </main>
    );
}

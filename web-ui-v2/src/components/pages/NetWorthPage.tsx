import React, { useState, useEffect } from 'react';
import { apiFetch } from '../../utils/api';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export function NetWorthPage() {
    const [history, setHistory] = useState<any[]>([]);
    const [assets, setAssets] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    
    // Form state
    const [assetType, setAssetType] = useState('Cash');
    const [value, setValue] = useState('');
    const [description, setDescription] = useState('');

    const loadData = async () => {
        try {
            const [historyData, assetsData] = await Promise.all([
                apiFetch('/api/finance/net-worth-history'),
                apiFetch('/api/finance/manual-assets')
            ]);
            setHistory(historyData);
            setAssets(assetsData);
        } catch (error) {
            console.error("Failed to load net worth data", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    const handleAddAsset = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await apiFetch('/api/finance/manual-assets', {
                method: 'POST',
                body: JSON.stringify({
                    asset_type: assetType,
                    value: parseFloat(value),
                    description
                })
            });
            setValue('');
            setDescription('');
            loadData();
        } catch (error) {
            console.error("Failed to add asset", error);
        }
    };

    if (isLoading) return <div className="page-container">Loading...</div>;

    const currentNetWorth = history.length > 0 ? history[history.length - 1].net_worth : 0;

    return (
        <div className="page-container" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            <header>
                <h1 style={{ margin: 0, color: 'var(--text-primary)' }}>Net Worth</h1>
                <p style={{ color: 'var(--text-secondary)', margin: '0.5rem 0 0 0' }}>Track your total assets and liabilities</p>
            </header>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: '2rem' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                        <h3 style={{ color: 'var(--text-secondary)', margin: '0 0 0.5rem 0', fontSize: '0.9rem' }}>Current Net Worth</h3>
                        <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: 'var(--text-primary)' }}>
                            ${currentNetWorth.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </div>
                    </div>

                    <div className="glass-panel" style={{ padding: '1.5rem', height: '400px' }}>
                        <h3 style={{ margin: '0 0 1.5rem 0' }}>Net Worth Trend</h3>
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={history} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="colorNw" x1="0" y1="0" x2="0" y2="1">
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
                                <Area type="monotone" dataKey="net_worth" stroke="var(--accent-blue)" fillOpacity={1} fill="url(#colorNw)" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                        <h3 style={{ margin: '0 0 1rem 0' }}>Add Manual Asset</h3>
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
                                value={value}
                                onChange={(e) => setValue(e.target.value)}
                                style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                            />
                            <input 
                                type="text"
                                placeholder="Description (Optional)"
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                            />
                            <button type="submit" className="btn btn-primary" style={{ padding: '0.75rem', borderRadius: '8px' }}>
                                Add Asset
                            </button>
                        </form>
                    </div>

                    <div className="glass-panel" style={{ padding: '1.5rem' }}>
                        <h3 style={{ margin: '0 0 1rem 0' }}>Manual Assets</h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            {assets.length === 0 ? (
                                <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>No manual assets added yet.</div>
                            ) : (
                                assets.map(a => (
                                    <div key={a.id} style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.5rem', borderBottom: '1px solid var(--border)' }}>
                                        <div>
                                            <div style={{ fontWeight: '500' }}>{a.asset_type}</div>
                                            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{a.description}</div>
                                        </div>
                                        <div style={{ fontWeight: 'bold' }}>
                                            ${a.value.toLocaleString()}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

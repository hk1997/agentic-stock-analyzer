import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import './FundamentalHighlights.css';

interface FundamentalHighlightsProps {
    ticker: string;
}

type TabKey = 'story' | 'porter' | 'competitors';

export default function FundamentalHighlights({ ticker }: FundamentalHighlightsProps) {
    const [activeTab, setActiveTab] = useState<TabKey>('story');
    const [data, setData] = useState<{ [key in TabKey]?: string }>({});
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    // Reset state synchronously when ticker changes to avoid double-rendering useEffect loops
    const [prevTicker, setPrevTicker] = useState(ticker);
    if (ticker !== prevTicker) {
        setData({});
        setActiveTab('story');
        setPrevTicker(ticker);
    }

    useEffect(() => {
        let isMounted = true;

        const fetchCurrentTab = async () => {
            if (!ticker || data[activeTab]) return;

            setLoading(true);
            setError(null);
            try {
                const resp = await fetch(`http://localhost:8000/api/fundamentals/${ticker}/${activeTab}`);
                const result = await resp.json();

                if (isMounted) {
                    if (!resp.ok || result.error) {
                        setError(result.error || `HTTP Error ${resp.status}`);
                    } else {
                        setData(prev => ({ ...prev, [activeTab]: result.markdown }));
                    }
                }
            } catch (err: any) {
                if (isMounted) {
                    setError(err.message || 'Failed to fetch fundamental analysis');
                    console.error('Fundamental API Error:', err);
                }
            } finally {
                if (isMounted) {
                    setLoading(false);
                }
            }
        };

        fetchCurrentTab();

        return () => { isMounted = false; };
    }, [activeTab, ticker, data]);

    const tabs: { key: TabKey, label: string }[] = [
        { key: 'story', label: 'Business Model' },
        { key: 'porter', label: "Porter's 5 Forces" },
        { key: 'competitors', label: 'Competitors' },
    ];

    return (
        <section className="highlights-container">
            <header className="highlights-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                        <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                        <line x1="12" y1="22.08" x2="12" y2="12"></line>
                    </svg>
                    <h3 style={{ margin: 0, fontSize: '15px', color: '#fff', fontWeight: '500' }}>AI Fundamental Analysis</h3>
                </div>
            </header>

            <div className="highlights-tabs">
                {tabs.map((tab) => (
                    <button
                        key={tab.key}
                        className={`highlight-tab ${activeTab === tab.key ? 'active' : ''}`}
                        onClick={() => setActiveTab(tab.key)}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            <div className="highlights-content">
                {loading && !data[activeTab] ? (
                    <div className="highlights-loading">
                        <div className="spinner"></div>
                        <span>Evaluating fundamentals...</span>
                    </div>
                ) : error ? (
                    <div className="highlights-error">
                        ⚠️ {error}
                    </div>
                ) : (
                    <div className="markdown-body">
                        {data[activeTab] ? (
                            <ReactMarkdown>{data[activeTab]!}</ReactMarkdown>
                        ) : (
                            <span style={{ color: '#64748b' }}>No analysis generated.</span>
                        )}
                    </div>
                )}
            </div>
        </section>
    );
}

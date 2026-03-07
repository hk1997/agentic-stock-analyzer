import React, { useState } from 'react';
import { FileText, ExternalLink, Bot, AlertTriangle, ChevronRight, BarChart2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useFilings } from '../hooks/useFilings';

interface FilingsPanelProps {
    ticker: string;
}

export function FilingsPanel({ ticker }: FilingsPanelProps) {
    const { filings, mdaText, riskText, loading, loadingAI, error } = useFilings(ticker);
    const [activeTab, setActiveTab] = useState<'mda' | 'risks' | 'filings'>('mda');

    if (error) {
        return (
            <section className="chart-card glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
                <div className="chart-card__header">
                    <h3 style={{ margin: 0, fontSize: '16px', color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <FileText size={18} color="#a855f7" />
                        SEC Filings & Narrative Analysis
                    </h3>
                </div>
                <div style={{ padding: '16px', color: '#ef4444', display: 'flex', gap: '8px' }}>
                    <AlertTriangle size={16} />
                    <span style={{ fontSize: '13px' }}>{error}</span>
                </div>
            </section>
        );
    }

    return (
        <section className="chart-card glass-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '500px' }}>
            <div className="chart-card__header" style={{ marginBottom: '16px', flexShrink: 0 }}>
                <h3 style={{ margin: 0, fontSize: '16px', color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <FileText size={18} color="#a855f7" />
                    SEC Filings & Narrative Analysis
                </h3>
                <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: '#a0a5b9' }}>10-K/10-Q SEC Extracts for {ticker}</p>

                {/* Tabs */}
                <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
                    <button
                        onClick={() => setActiveTab('mda')}
                        style={{ background: activeTab === 'mda' ? 'rgba(168, 85, 247, 0.2)' : 'transparent', color: activeTab === 'mda' ? '#a855f7' : '#a0a5b9', border: '1px solid', borderColor: activeTab === 'mda' ? 'rgba(168, 85, 247, 0.4)' : 'rgba(255,255,255,0.1)', padding: '6px 12px', borderRadius: '4px', fontSize: '12px', cursor: 'pointer', transition: '0.2s', display: 'flex', alignItems: 'center', gap: '6px' }}
                    >
                        <BarChart2 size={14} /> MD&A (Item 7)
                    </button>
                    <button
                        onClick={() => setActiveTab('risks')}
                        style={{ background: activeTab === 'risks' ? 'rgba(239, 68, 68, 0.2)' : 'transparent', color: activeTab === 'risks' ? '#ef4444' : '#a0a5b9', border: '1px solid', borderColor: activeTab === 'risks' ? 'rgba(239, 68, 68, 0.4)' : 'rgba(255,255,255,0.1)', padding: '6px 12px', borderRadius: '4px', fontSize: '12px', cursor: 'pointer', transition: '0.2s', display: 'flex', alignItems: 'center', gap: '6px' }}
                    >
                        <AlertTriangle size={14} /> Risk Factors (Item 1A)
                    </button>
                    <button
                        onClick={() => setActiveTab('filings')}
                        style={{ background: activeTab === 'filings' ? 'rgba(59, 130, 246, 0.2)' : 'transparent', color: activeTab === 'filings' ? '#3b82f6' : '#a0a5b9', border: '1px solid', borderColor: activeTab === 'filings' ? 'rgba(59, 130, 246, 0.4)' : 'rgba(255,255,255,0.1)', padding: '6px 12px', borderRadius: '4px', fontSize: '12px', cursor: 'pointer', transition: '0.2s', display: 'flex', alignItems: 'center', gap: '6px' }}
                    >
                        <FileText size={14} /> All Filings
                    </button>
                </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', flex: 1, overflowY: 'auto', paddingRight: '4px' }}>
                {loading ? (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100px' }}>
                        <div className="loading-spinner"></div>
                    </div>
                ) : (
                    <>
                        {/* Filings List Tab */}
                        {activeTab === 'filings' && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                {filings.map((f, i) => (
                                    <a key={i} href={f.document} target="_blank" rel="noopener noreferrer" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', textDecoration: 'none', border: '1px solid rgba(255,255,255,0.02)' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                            <div style={{ background: 'rgba(59, 130, 246, 0.2)', color: '#3b82f6', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold', width: '40px', textAlign: 'center' }}>
                                                {f.form}
                                            </div>
                                            <div>
                                                <div style={{ fontSize: '14px', color: '#fff' }}>Accession: {f.acc_num}</div>
                                                <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>{f.date}</div>
                                            </div>
                                        </div>
                                        <ExternalLink size={16} color="#64748b" />
                                    </a>
                                ))}
                                {filings.length === 0 && <p style={{ fontSize: '13px', color: '#a0a5b9', fontStyle: 'italic' }}>No recent filings found.</p>}
                            </div>
                        )}

                        {/* MD&A AI Summary Tab */}
                        {activeTab === 'mda' && (
                            <div className="markdown-prose" style={{ background: 'rgba(20, 25, 40, 0.4)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(168, 85, 247, 0.1)' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '12px' }}>
                                    <Bot size={16} color="#a855f7" />
                                    <span style={{ fontSize: '14px', color: '#a855f7', fontWeight: 'bold' }}>AI Extracted Management's Discussion & Analysis</span>
                                </div>
                                {loadingAI && !mdaText ? (
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#a0a5b9' }}>
                                        <div className="loading-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                                        <span style={{ fontSize: '13px' }}>Synthesizing Item 7 from the latest 10-K...</span>
                                    </div>
                                ) : mdaText ? (
                                    <ReactMarkdown>{mdaText}</ReactMarkdown>
                                ) : (
                                    <p style={{ margin: 0, fontSize: '13px', color: '#a0a5b9' }}>No MD&A Summary available.</p>
                                )}
                            </div>
                        )}

                        {/* Risk Factors AI Summary Tab */}
                        {activeTab === 'risks' && (
                            <div className="markdown-prose" style={{ background: 'rgba(69, 10, 10, 0.2)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '12px' }}>
                                    <AlertTriangle size={16} color="#ef4444" />
                                    <span style={{ fontSize: '14px', color: '#ef4444', fontWeight: 'bold' }}>AI Extracted Critical Risk Factors</span>
                                </div>
                                {loadingAI && !riskText ? (
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#a0a5b9' }}>
                                        <div className="loading-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                                        <span style={{ fontSize: '13px' }}>Synthesizing Item 1A structurally from the latest 10-K...</span>
                                    </div>
                                ) : riskText ? (
                                    <ReactMarkdown>{riskText}</ReactMarkdown>
                                ) : (
                                    <p style={{ margin: 0, fontSize: '13px', color: '#a0a5b9' }}>No Risk Factors Summary available.</p>
                                )}
                            </div>
                        )}
                    </>
                )}
            </div>
        </section>
    );
}

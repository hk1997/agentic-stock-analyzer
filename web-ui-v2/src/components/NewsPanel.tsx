import React from 'react';
import { Newspaper, ExternalLink, Bot, AlertTriangle } from 'lucide-react';
import { useNews } from '../hooks/useNews';

interface NewsPanelProps {
    ticker: string;
}

export function NewsPanel({ ticker }: NewsPanelProps) {
    const { news, loading, error } = useNews(ticker);

    if (error) {
        return (
            <section className="chart-card glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
                <div className="chart-card__header">
                    <h3 style={{ margin: 0, fontSize: '16px', color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Newspaper size={18} color="#f59e0b" />
                        Latest News & Sentiment
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
        <section className="chart-card glass-panel" style={{ display: 'flex', flexDirection: 'column', maxHeight: '500px' }}>
            <div className="chart-card__header" style={{ marginBottom: '16px', flexShrink: 0 }}>
                <h3 style={{ margin: 0, fontSize: '16px', color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Newspaper size={18} color="#f59e0b" />
                    Latest News & Sentiment
                </h3>
                <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: '#a0a5b9' }}>Real-time news and AI sentiment for {ticker}</p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', flex: 1, overflowY: 'auto', paddingRight: '4px' }}>
                {loading && !news ? (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100px' }}>
                        <div className="loading-spinner"></div>
                    </div>
                ) : (
                    <>
                        {/* Sentiment Summary Box */}
                        <div style={{ background: 'rgba(20, 25, 40, 0.4)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                                <Bot size={14} color="#a855f7" />
                                <span style={{ fontSize: '12px', color: '#a855f7', fontWeight: 'bold' }}>AI Sentiment Analysis</span>
                            </div>

                            {news?.sentiment_summary ? (
                                <p style={{ margin: 0, fontSize: '14px', color: '#fff', lineHeight: 1.5 }}>
                                    {news.sentiment_summary}
                                </p>
                            ) : (
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <div className="loading-spinner" style={{ width: 12, height: 12, borderWidth: 2 }} />
                                    <span style={{ fontSize: '13px', color: '#a0a5b9' }}>Synthesizing sentiment...</span>
                                </div>
                            )}
                        </div>

                        {/* Article List */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {news?.articles.map((article, i) => (
                                <a
                                    key={i}
                                    href={article.link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{
                                        display: 'flex', flexDirection: 'column', gap: '4px',
                                        padding: '12px', background: 'rgba(0,0,0,0.2)',
                                        borderRadius: '8px', textDecoration: 'none',
                                        border: '1px solid rgba(255,255,255,0.02)',
                                        transition: 'background 0.2s'
                                    }}
                                >
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                                        <h4 style={{ margin: 0, fontSize: '14px', color: '#fff', lineHeight: 1.4 }}>{article.title}</h4>
                                        <ExternalLink size={14} color="#64748b" style={{ flexShrink: 0, marginTop: '2px' }} />
                                    </div>
                                    <p style={{ margin: 0, fontSize: '12px', color: '#a0a5b9', lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                                        {article.snippet}
                                    </p>
                                </a>
                            ))}
                            {news?.articles.length === 0 && (
                                <p style={{ fontSize: '13px', color: '#a0a5b9', fontStyle: 'italic' }}>No recent news found.</p>
                            )}
                        </div>
                    </>
                )}
            </div>
        </section>
    );
}

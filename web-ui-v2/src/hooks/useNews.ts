import { useState, useEffect } from 'react';

export interface NewsArticle {
    title: string;
    link: string;
    snippet: string;
}

export interface NewsResponse {
    ticker: string;
    news_raw: string; // The raw duckduckgo string format
    articles: NewsArticle[];
    sentiment_summary: string | null;
}

export function useNews(ticker: string) {
    const [news, setNews] = useState<NewsResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!ticker) return;

        let isMounted = true;
        const fetchNews = async () => {
            setLoading(true);
            setError(null);
            try {
                // Fetch raw news first for speed
                const newsRes = await fetch(`http://localhost:8000/api/news/${ticker}`);
                const newsData = await newsRes.json();

                if (newsData.error) throw new Error(newsData.error);

                // Parse duckduckgo string format: [snippet: ..., title: ..., link: ...], [...]
                const rawString = newsData.news_raw || '';
                const articles: NewsArticle[] = [];

                // Simple regex to parse the DDG format
                const regex = /\[snippet:\s*(.*?),\s*title:\s*(.*?),\s*link:\s*(.*?)\]/g;
                let match;
                while ((match = regex.exec(rawString)) !== null) {
                    articles.push({
                        snippet: match[1],
                        title: match[2],
                        link: match[3]
                    });
                }

                if (isMounted) {
                    setNews({
                        ticker,
                        news_raw: newsData.news_raw,
                        articles,
                        sentiment_summary: null
                    });
                }

                // In background, fetch the LLM sentiment summary
                const sentimentRes = await fetch(`http://localhost:8000/api/news/${ticker}/sentiment`);
                const sentimentData = await sentimentRes.json();

                if (!sentimentData.error && isMounted) {
                    setNews(prev => prev ? {
                        ...prev,
                        sentiment_summary: sentimentData.sentiment_summary
                    } : null);
                }

            } catch (err) {
                if (isMounted) {
                    setError(err instanceof Error ? err.message : 'Failed to fetch news');
                }
            } finally {
                if (isMounted) setLoading(false);
            }
        };

        fetchNews();
        return () => { isMounted = false; };
    }, [ticker]);

    return { news, loading, error };
}

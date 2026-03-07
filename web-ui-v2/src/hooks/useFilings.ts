import { useState, useEffect } from 'react';

export interface Filing {
    form: string;
    date: string;
    acc_num: string;
    document: string;
}

export function useFilings(ticker: string) {
    const [filings, setFilings] = useState<Filing[]>([]);
    const [mdaText, setMdaText] = useState<string | null>(null);
    const [riskText, setRiskText] = useState<string | null>(null);

    const [loading, setLoading] = useState(false);
    const [loadingAI, setLoadingAI] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!ticker) return;

        let isMounted = true;
        const fetchAll = async () => {
            setLoading(true);
            setLoadingAI(true);
            setError(null);

            // 1. Fetch fast metadata
            try {
                const metaRes = await fetch(`http://localhost:8000/api/filings/${ticker}`);
                const metaData = await metaRes.json();
                if (metaData.error) throw new Error(metaData.error);
                if (isMounted) setFilings(metaData.filings || []);
            } catch (err) {
                if (isMounted) setError(err instanceof Error ? err.message : 'Failed to fetch SEC filings');
            } finally {
                if (isMounted) setLoading(false);
            }

            // 2. Fetch slower AI extracted content (MD&A and Risks)
            try {
                const [mdaRes, riskRes] = await Promise.all([
                    fetch(`http://localhost:8000/api/filings/${ticker}/mda`),
                    fetch(`http://localhost:8000/api/filings/${ticker}/risks`)
                ]);

                const mdaData = await mdaRes.json();
                const riskData = await riskRes.json();

                if (isMounted) {
                    if (!mdaData.error) setMdaText(mdaData.markdown);
                    if (!riskData.error) setRiskText(riskData.markdown);
                }
            } catch (err) {
                console.error("AI Filings extraction failed", err);
            } finally {
                if (isMounted) setLoadingAI(false);
            }
        };

        fetchAll();
        return () => { isMounted = false; };
    }, [ticker]);

    return { filings, mdaText, riskText, loading, loadingAI, error };
}

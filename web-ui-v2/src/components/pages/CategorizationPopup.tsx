import React, { useState, useEffect } from 'react';
import { X, Check } from 'lucide-react';
import { apiFetch } from '../../utils/api';

interface UncategorizedExpense {
    id: number;
    date: string;
    amount: number;
    description: string;
    is_joint?: number;
}

interface Props {
    expenses: UncategorizedExpense[];
    onClose: () => void;
    onComplete: () => void;
}

const getSuggestedRegex = (desc: string) => {
    if (!desc) return '';
    const words = desc.split(/[\s*_\-#]/).map(w => w.replace(/[^a-zA-Z0-9]/g, '').trim()).filter(Boolean);
    if (words.length > 0) {
        const word = words.find(w => w.length > 2) || words[0];
        return `.*${word}.*`;
    }
    return `.*${desc.replace(/[^a-zA-Z0-9]/g, '')}.*`;
};

export function CategorizationPopup({ expenses, onClose, onComplete }: Props) {
    const [localExpenses, setLocalExpenses] = useState<UncategorizedExpense[]>(expenses);
    const [skippedIds, setSkippedIds] = useState<Set<number>>(new Set());
    const [currentIndex, setCurrentIndex] = useState(0);
    const [category, setCategory] = useState('');
    const [regexPattern, setRegexPattern] = useState('');
    const [isRule, setIsRule] = useState(true);
    const [isJoint, setIsJoint] = useState(false);

    const remainingExpenses = localExpenses.filter(e => !skippedIds.has(e.id));
    const currentExpense = remainingExpenses[currentIndex];

    // Update regex when expense changes
    useEffect(() => {
        if (currentExpense) {
            setRegexPattern(getSuggestedRegex(currentExpense.description));
            setCategory('');
            setIsJoint(currentExpense.is_joint === 1);
        }
    }, [currentExpense]);

    if (!currentExpense) return null;

    const handleSaveRule = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            if (isRule) {
                await apiFetch('/api/finance/category-rules', {
                    method: 'POST',
                    body: JSON.stringify({
                        regex_pattern: regexPattern,
                        category_name: category
                    })
                });
            }
            
            // Always update current expense to apply its category and joint status
            await apiFetch(`/api/finance/expenses/${currentExpense.id}`, {
                method: 'PATCH',
                body: JSON.stringify({
                    category: category,
                    is_joint: isJoint
                })
            });
            
            // Fetch updated list of uncategorized expenses
            const freshUncategorized = await apiFetch('/api/finance/expenses/uncategorized');
            setLocalExpenses(freshUncategorized);
            
            // Check remaining
            const freshRemaining = freshUncategorized.filter((e: any) => !skippedIds.has(e.id));
            if (freshRemaining.length === 0) {
                onComplete();
            } else {
                setCurrentIndex(0);
                setCategory('');
            }
        } catch (error) {
            console.error("Failed to save categorization", error);
        }
    };

    const handleSkip = () => {
        const nextSkipped = new Set(skippedIds);
        nextSkipped.add(currentExpense.id);
        setSkippedIds(nextSkipped);
        
        const freshRemaining = localExpenses.filter(e => !nextSkipped.has(e.id));
        if (freshRemaining.length === 0) {
            onComplete();
        } else {
            setCurrentIndex(0);
            setCategory('');
        }
    };

    const handleExclude = async () => {
        try {
            await apiFetch(`/api/finance/expenses/${currentExpense.id}`, {
                method: 'DELETE'
            });
            
            // Fetch updated list of uncategorized expenses
            const freshUncategorized = await apiFetch('/api/finance/expenses/uncategorized');
            setLocalExpenses(freshUncategorized);
            
            // Check remaining
            const freshRemaining = freshUncategorized.filter((e: any) => !skippedIds.has(e.id));
            if (freshRemaining.length === 0) {
                onComplete();
            } else {
                setCurrentIndex(0);
                setCategory('');
            }
        } catch (error) {
            console.error("Failed to exclude transaction", error);
        }
    };

    return (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
            <div className="glass-panel" style={{ width: '500px', padding: '2rem', position: 'relative', background: 'var(--bg-card)' }}>
                <button onClick={onClose} style={{ position: 'absolute', top: '1rem', right: '1rem', background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                    <X size={20} />
                </button>
                
                <h3 style={{ margin: '0 0 1rem 0', color: 'var(--text-primary)' }}>
                    {currentExpense.amount < 0 ? 'Credit Transaction / Refund' : 'Categorize Expense'}
                </h3>
                {currentExpense.amount < 0 ? (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                        We detected a credit transaction/refund of <span style={{ color: 'var(--accent-green)', fontWeight: 'bold' }}>${Math.abs(currentExpense.amount).toLocaleString(undefined, {minimumFractionDigits: 2})}</span>. Add it to expenses as a negative refund?
                        <br />
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.25rem', display: 'inline-block' }}>
                            ({expenses.length - remainingExpenses.length + currentIndex + 1} of {expenses.length})
                        </span>
                    </p>
                ) : (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                        We found an uncategorized expense. Categorize it one-time or create a rule to automatically categorize it in the future.
                        <br />
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.25rem', display: 'inline-block' }}>
                            ({expenses.length - remainingExpenses.length + currentIndex + 1} of {expenses.length})
                        </span>
                    </p>
                )}

                <div style={{ background: 'var(--bg-main)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', border: '1px solid var(--border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Date:</span>
                        <span style={{ color: 'var(--text-primary)' }}>{new Date(currentExpense.date).toLocaleDateString()}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Amount:</span>
                        <span style={{ fontWeight: 'bold', color: currentExpense.amount < 0 ? 'var(--accent-green)' : 'var(--text-primary)' }}>
                            {currentExpense.amount < 0 ? '-' : ''}${Math.abs(currentExpense.amount).toLocaleString(undefined, {minimumFractionDigits: 2})}
                        </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>Description:</span>
                        <span style={{ textAlign: 'right', color: 'var(--text-primary)' }}>{currentExpense.description}</span>
                    </div>
                </div>

                <form onSubmit={handleSaveRule} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '0.25rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <input 
                                type="checkbox" 
                                id="create-rule-checkbox" 
                                checked={isRule} 
                                onChange={e => setIsRule(e.target.checked)} 
                                style={{ cursor: 'pointer' }}
                            />
                            <label htmlFor="create-rule-checkbox" style={{ fontSize: '0.9rem', color: 'var(--text-primary)', cursor: 'pointer', userSelect: 'none' }}>
                                Create automatic rule for future matches
                            </label>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <input 
                                type="checkbox" 
                                id="is-joint-checkbox" 
                                checked={isJoint} 
                                onChange={e => setIsJoint(e.target.checked)} 
                                style={{ cursor: 'pointer' }}
                            />
                            <label htmlFor="is-joint-checkbox" style={{ fontSize: '0.9rem', color: 'var(--text-primary)', cursor: 'pointer', userSelect: 'none' }}>
                                Mark as Joint Expense
                            </label>
                        </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                        <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Category Name</label>
                        <input type="text" placeholder="e.g. Groceries" required value={category} onChange={e => setCategory(e.target.value)} style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }} />
                    </div>

                    {isRule && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Regex Match Rule (Verify/Edit)</label>
                            <input type="text" required value={regexPattern} onChange={e => setRegexPattern(e.target.value)} style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }} />
                        </div>
                    )}

                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
                        <button type="button" onClick={handleSkip} className="btn" style={{ background: 'var(--bg-main)', border: '1px solid var(--border)', color: 'var(--text-primary)', padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer', flex: 1 }}>
                            Skip
                        </button>
                        {currentExpense.amount < 0 && (
                            <button type="button" onClick={handleExclude} className="btn" style={{ background: 'rgba(255, 69, 58, 0.15)', border: '1px solid var(--accent-red)', color: 'var(--accent-red)', padding: '0.75rem 1rem', borderRadius: '8px', cursor: 'pointer', flex: 1.2 }}>
                                Exclude & Discard
                            </button>
                        )}
                        <button type="submit" className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '0.75rem 1.5rem', borderRadius: '8px', cursor: 'pointer', flex: 1.5 }}>
                            <Check size={18} /> {currentExpense.amount < 0 ? (isRule ? 'Save Refund Rule' : 'Save Refund') : (isRule ? 'Save Rule' : 'Save One-Time')}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

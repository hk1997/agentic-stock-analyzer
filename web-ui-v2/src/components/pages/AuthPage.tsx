import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { apiFetch } from '../../utils/api';
import { Activity } from 'lucide-react';

export function AuthPage() {
    const { login } = useAuth();
    const [isLogin, setIsLogin] = useState(true);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [name, setName] = useState('');
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        try {
            if (isLogin) {
                // OAuth2PasswordRequestForm expects form data
                const formData = new FormData();
                formData.append('username', email);
                formData.append('password', password);

                const data = await apiFetch('/api/auth/login', {
                    method: 'POST',
                    body: formData,
                });
                
                login(data.access_token, data.user);
            } else {
                // Register
                await apiFetch('/api/auth/register', {
                    method: 'POST',
                    body: JSON.stringify({ email, password, name }),
                });
                // Auto-login after register
                const formData = new FormData();
                formData.append('username', email);
                formData.append('password', password);
                const data = await apiFetch('/api/auth/login', {
                    method: 'POST',
                    body: formData,
                });
                login(data.access_token, data.user);
            }
        } catch (err: any) {
            setError(err.message || 'Authentication failed');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="auth-container" style={{
            display: 'flex', 
            justifyContent: 'center', 
            alignItems: 'center', 
            height: '100vh', 
            width: '100vw',
            background: 'var(--bg-main)'
        }}>
            <div className="glass-panel" style={{ width: '400px', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'center', color: 'var(--accent-blue)' }}>
                    <Activity size={48} />
                </div>
                <h2 style={{ textAlign: 'center', margin: 0, color: 'var(--text-primary)' }}>
                    {isLogin ? 'Welcome Back' : 'Create Account'}
                </h2>
                
                {error && <div style={{ color: 'var(--accent-red)', fontSize: '0.9rem', textAlign: 'center', background: 'rgba(255, 59, 48, 0.1)', padding: '0.5rem', borderRadius: '4px' }}>{error}</div>}
                
                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {!isLogin && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            <label style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Name</label>
                            <input 
                                type="text" 
                                value={name} 
                                onChange={(e) => setName(e.target.value)}
                                style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                            />
                        </div>
                    )}
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        <label style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Email</label>
                        <input 
                            type="email" 
                            required 
                            value={email} 
                            onChange={(e) => setEmail(e.target.value)}
                            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                        />
                    </div>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        <label style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Password</label>
                        <input 
                            type="password" 
                            required 
                            value={password} 
                            onChange={(e) => setPassword(e.target.value)}
                            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                        />
                    </div>
                    
                    <button 
                        type="submit" 
                        disabled={isLoading}
                        style={{ 
                            background: 'var(--accent-blue)', 
                            color: 'white', 
                            padding: '0.75rem', 
                            borderRadius: '8px', 
                            border: 'none', 
                            marginTop: '1rem',
                            cursor: isLoading ? 'not-allowed' : 'pointer',
                            fontWeight: 'bold',
                            opacity: isLoading ? 0.7 : 1
                        }}
                    >
                        {isLoading ? 'Processing...' : (isLogin ? 'Login' : 'Sign Up')}
                    </button>
                </form>
                
                <div style={{ textAlign: 'center', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                    {isLogin ? "Don't have an account? " : "Already have an account? "}
                    <span 
                        onClick={() => setIsLogin(!isLogin)} 
                        style={{ color: 'var(--accent-blue)', cursor: 'pointer' }}
                    >
                        {isLogin ? 'Sign up' : 'Login'}
                    </span>
                </div>
            </div>
        </div>
    );
}

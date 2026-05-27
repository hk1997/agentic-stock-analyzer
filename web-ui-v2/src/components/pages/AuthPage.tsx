import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { apiFetch } from '../../utils/api';
import { Activity } from 'lucide-react';

export function AuthPage() {
    const { login } = useAuth();
    const [isLogin, setIsLogin] = useState(true);
    const [isForgotPassword, setIsForgotPassword] = useState(false);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [name, setName] = useState('');
    const [secretKey, setSecretKey] = useState('');
    const [error, setError] = useState('');
    const [successMessage, setSuccessMessage] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setSuccessMessage('');
        setIsLoading(true);

        try {
            if (isForgotPassword) {
                const data = await apiFetch('/api/auth/reset-password', {
                    method: 'POST',
                    body: JSON.stringify({ email, new_password: password, secret_key: secretKey }),
                });
                setSuccessMessage(data.message || 'Password reset successfully. You can now login.');
                setIsForgotPassword(false);
                setIsLogin(true);
                setPassword('');
                setSecretKey('');
            } else if (isLogin) {
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
                    {isForgotPassword ? 'Reset Password' : (isLogin ? 'Welcome Back' : 'Create Account')}
                </h2>
                
                {error && <div style={{ color: 'var(--accent-red)', fontSize: '0.9rem', textAlign: 'center', background: 'rgba(255, 59, 48, 0.1)', padding: '0.5rem', borderRadius: '4px' }}>{error}</div>}
                {successMessage && <div style={{ color: 'var(--accent-green)', fontSize: '0.9rem', textAlign: 'center', background: 'rgba(48, 209, 88, 0.1)', padding: '0.5rem', borderRadius: '4px' }}>{successMessage}</div>}
                
                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {!isLogin && !isForgotPassword && (
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
                        <label style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                            {isForgotPassword ? 'New Password' : 'Password'}
                        </label>
                        <input 
                            type="password" 
                            required 
                            value={password} 
                            onChange={(e) => setPassword(e.target.value)}
                            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                        />
                    </div>

                    {isForgotPassword && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            <label style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Admin Secret Key</label>
                            <input 
                                type="password" 
                                required 
                                value={secretKey} 
                                onChange={(e) => setSecretKey(e.target.value)}
                                placeholder="Enter server secret key"
                                style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '8px', color: 'var(--text-primary)' }}
                            />
                        </div>
                    )}

                    {isLogin && !isForgotPassword && (
                        <div style={{ textAlign: 'right', marginTop: '-0.25rem' }}>
                            <span 
                                onClick={() => {
                                    setIsForgotPassword(true);
                                    setError('');
                                    setSuccessMessage('');
                                }} 
                                style={{ color: 'var(--accent-blue)', cursor: 'pointer', fontSize: '0.85rem' }}
                            >
                                Forgot password?
                            </span>
                        </div>
                    )}
                    
                    <button 
                        type="submit" 
                        disabled={isLoading}
                        style={{ 
                            background: 'var(--accent-blue)', 
                            color: 'white', 
                            padding: '0.75rem', 
                            borderRadius: '8px', 
                            border: 'none', 
                            marginTop: '0.5rem',
                            cursor: isLoading ? 'not-allowed' : 'pointer',
                            fontWeight: 'bold',
                            opacity: isLoading ? 0.7 : 1
                        }}
                    >
                        {isLoading ? 'Processing...' : (isForgotPassword ? 'Reset Password' : (isLogin ? 'Login' : 'Sign Up'))}
                    </button>
                </form>
                
                <div style={{ textAlign: 'center', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                    {isForgotPassword ? (
                        <span 
                            onClick={() => {
                                setIsForgotPassword(false);
                                setIsLogin(true);
                                setError('');
                                setSuccessMessage('');
                            }} 
                            style={{ color: 'var(--accent-blue)', cursor: 'pointer' }}
                        >
                            Back to Login
                        </span>
                    ) : (
                        <>
                            {isLogin ? "Don't have an account? " : "Already have an account? "}
                            <span 
                                onClick={() => {
                                    setIsLogin(!isLogin);
                                    setError('');
                                    setSuccessMessage('');
                                }} 
                                style={{ color: 'var(--accent-blue)', cursor: 'pointer' }}
                            >
                                {isLogin ? 'Sign up' : 'Login'}
                            </span>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

import React, { useState } from 'react'
import { Activity, LayoutDashboard, DollarSign, BarChart3, Settings, LogOut, Target } from 'lucide-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { apiFetch } from '../../utils/api'

export function Sidebar() {
    const navigate = useNavigate()
    const location = useLocation()
    const { logout } = useAuth()

    const [isModalOpen, setIsModalOpen] = useState(false)
    const [currentPassword, setCurrentPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [confirmNewPassword, setConfirmNewPassword] = useState('')
    const [error, setError] = useState('')
    const [successMessage, setSuccessMessage] = useState('')
    const [isLoading, setIsLoading] = useState(false)

    const handleCloseModal = () => {
        setIsModalOpen(false)
        setCurrentPassword('')
        setNewPassword('')
        setConfirmNewPassword('')
        setError('')
        setSuccessMessage('')
    }

    const handleChangePassword = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')
        setSuccessMessage('')

        if (newPassword !== confirmNewPassword) {
            setError('New passwords do not match')
            return
        }

        setIsLoading(true)
        try {
            await apiFetch('/api/auth/change-password', {
                method: 'POST',
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword
                })
            })
            setSuccessMessage('Password changed successfully')
            setCurrentPassword('')
            setNewPassword('')
            setConfirmNewPassword('')
        } catch (err: any) {
            setError(err.message || 'Failed to change password')
        } finally {
            setIsLoading(false)
        }
    }

    const isActive = (path: string) => location.pathname === path

    return (
        <aside className="sidebar">
            <div className="sidebar__logo">
                <Activity size={28} />
            </div>

            <nav className="sidebar__nav">
                <button
                    className={`sidebar__btn ${isActive('/') ? 'sidebar__btn--active' : ''}`}
                    title="Dashboard"
                    onClick={() => navigate('/')}
                >
                    <LayoutDashboard size={20} />
                </button>
                <button
                    className={`sidebar__btn ${isActive('/goals') ? 'sidebar__btn--active' : ''}`}
                    title="Goals"
                    onClick={() => navigate('/goals')}
                >
                    <Target size={20} />
                </button>
                <button
                    className={`sidebar__btn ${isActive('/portfolio') ? 'sidebar__btn--active' : ''}`}
                    title="Portfolio"
                    onClick={() => navigate('/portfolio')}
                >
                    <DollarSign size={20} />
                </button>
                <button
                    className={`sidebar__btn ${isActive('/analysis') ? 'sidebar__btn--active' : ''}`}
                    title="Analysis"
                    onClick={() => navigate('/analysis')}
                >
                    <BarChart3 size={20} />
                </button>
                <button
                    className={`sidebar__btn ${isActive('/expenses') ? 'sidebar__btn--active' : ''}`}
                    title="Expenses"
                    onClick={() => navigate('/expenses')}
                >
                    <DollarSign size={20} />
                </button>
                <button
                    className={`sidebar__btn ${isActive('/net-worth') ? 'sidebar__btn--active' : ''}`}
                    title="Net Worth"
                    onClick={() => navigate('/net-worth')}
                >
                    <Activity size={20} />
                </button>
            </nav>

            <div className="sidebar__bottom" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <button className="sidebar__btn" title="Settings" onClick={() => setIsModalOpen(true)}>
                    <Settings size={20} />
                </button>
                <button 
                    className="sidebar__btn" 
                    title="Logout"
                    onClick={logout}
                    style={{ color: 'var(--accent-red)' }}
                >
                    <LogOut size={20} />
                </button>
            </div>

            {isModalOpen && (
                <div className="modal-overlay" onClick={handleCloseModal}>
                    <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: '400px' }}>
                        <div className="modal__header">
                            <h3 style={{ margin: 0 }}>Change Password</h3>
                            <button className="icon-btn" onClick={handleCloseModal} style={{ fontSize: '1.2rem', lineHeight: 1 }}>&times;</button>
                        </div>
                        <form onSubmit={handleChangePassword}>
                            <div className="modal__body">
                                {error && (
                                    <div style={{ color: 'var(--accent-red)', fontSize: '0.85rem', background: 'rgba(255, 59, 48, 0.1)', padding: '0.5rem', borderRadius: '4px' }}>
                                        {error}
                                    </div>
                                )}
                                {successMessage && (
                                    <div style={{ color: 'var(--accent-green)', fontSize: '0.85rem', background: 'rgba(48, 209, 88, 0.1)', padding: '0.5rem', borderRadius: '4px' }}>
                                        {successMessage}
                                    </div>
                                )}
                                
                                <label>
                                    Current Password
                                    <input 
                                        type="password" 
                                        required 
                                        value={currentPassword}
                                        onChange={(e) => setCurrentPassword(e.target.value)}
                                        style={{ marginTop: '0.25rem' }}
                                    />
                                </label>

                                <label>
                                    New Password
                                    <input 
                                        type="password" 
                                        required 
                                        value={newPassword}
                                        onChange={(e) => setNewPassword(e.target.value)}
                                        style={{ marginTop: '0.25rem' }}
                                    />
                                </label>

                                <label>
                                    Confirm New Password
                                    <input 
                                        type="password" 
                                        required 
                                        value={confirmNewPassword}
                                        onChange={(e) => setConfirmNewPassword(e.target.value)}
                                        style={{ marginTop: '0.25rem' }}
                                    />
                                </label>
                            </div>
                            <div className="modal__footer">
                                <button type="button" className="btn btn-secondary" onClick={handleCloseModal}>
                                    Cancel
                                </button>
                                <button type="submit" className="btn btn-primary" disabled={isLoading}>
                                    {isLoading ? 'Saving...' : 'Change Password'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </aside>
    )
}


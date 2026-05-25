import { Activity, LayoutDashboard, DollarSign, BarChart3, Settings, LogOut } from 'lucide-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'

export function Sidebar() {
    const navigate = useNavigate()
    const location = useLocation()
    const { logout } = useAuth()

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
                <button className="sidebar__btn" title="Settings">
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
        </aside>
    )
}

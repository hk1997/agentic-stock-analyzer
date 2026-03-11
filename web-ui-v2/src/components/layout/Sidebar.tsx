import { Activity, LayoutDashboard, DollarSign, BarChart3, Settings } from 'lucide-react'
import { useNavigate, useLocation } from 'react-router-dom'

export function Sidebar() {
    const navigate = useNavigate()
    const location = useLocation()

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
                <button className="sidebar__btn" title="Analysis">
                    <BarChart3 size={20} />
                </button>
            </nav>

            <div className="sidebar__bottom">
                <button className="sidebar__btn" title="Settings">
                    <Settings size={20} />
                </button>
            </div>
        </aside>
    )
}

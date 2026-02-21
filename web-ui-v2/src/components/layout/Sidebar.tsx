import { Activity, LayoutDashboard, DollarSign, BarChart3, Settings } from 'lucide-react'

export function Sidebar() {
    return (
        <aside className="sidebar">
            <div className="sidebar__logo">
                <Activity size={28} />
            </div>

            <nav className="sidebar__nav">
                <button className="sidebar__btn sidebar__btn--active" title="Dashboard">
                    <LayoutDashboard size={20} />
                </button>
                <button className="sidebar__btn" title="Portfolio">
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

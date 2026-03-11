import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Sidebar } from './components/layout/Sidebar'
import { DashboardPage } from './components/pages/DashboardPage'
import { PortfolioPage } from './components/pages/PortfolioPage'

function App() {
    return (
        <BrowserRouter>
            <Sidebar />
            <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/portfolio" element={<PortfolioPage />} />
            </Routes>
        </BrowserRouter>
    )
}

export default App

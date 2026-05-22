import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Sidebar } from './components/layout/Sidebar'
import { DashboardPage } from './components/pages/DashboardPage'
import { AnalysisPage } from './components/pages/AnalysisPage'
import { PortfolioPage } from './components/pages/PortfolioPage'
import { ExpensesPage } from './components/pages/ExpensesPage'
import { NetWorthPage } from './components/pages/NetWorthPage'
import { AuthProvider, useAuth } from './hooks/useAuth'
import { AuthPage } from './components/pages/AuthPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
    const { isAuthenticated, isLoading } = useAuth();
    
    if (isLoading) {
        return <div style={{ display: 'flex', height: '100vh', justifyContent: 'center', alignItems: 'center', color: 'white' }}>Loading...</div>;
    }
    
    if (!isAuthenticated) {
        return <AuthPage />;
    }
    
    return <>{children}</>;
}

function App() {
    return (
        <AuthProvider>
            <BrowserRouter>
                <ProtectedRoute>
                    <Sidebar />
                    <Routes>
                        <Route path="/" element={<DashboardPage />} />
                        <Route path="/analysis" element={<AnalysisPage />} />
                        <Route path="/portfolio" element={<PortfolioPage />} />
                        <Route path="/expenses" element={<ExpensesPage />} />
                        <Route path="/net-worth" element={<NetWorthPage />} />
                        <Route path="*" element={<Navigate to="/" replace />} />
                    </Routes>
                </ProtectedRoute>
            </BrowserRouter>
        </AuthProvider>
    )
}

export default App

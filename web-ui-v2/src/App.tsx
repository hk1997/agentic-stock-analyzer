import React, { useState } from 'react'
import { Sidebar } from './components/layout/Sidebar'
import { Header } from './components/layout/Header'
import { StockChart } from './components/chart/StockChart'
import { StatsRow } from './components/stats/StatCard'
import { ChatPanel } from './components/chat/ChatPanel'
import { useChat } from './hooks/useChat'
import { useStockData } from './hooks/useStockData'
import { useIndicators } from './hooks/useIndicators'

function App() {
    const { messages, isStreaming, sendMessage } = useChat()
    const [activeTicker, setActiveTicker] = useState('AAPL')
    const [period, setPeriod] = useState('1mo')
    const { data: stockData, loading: stockLoading } = useStockData(activeTicker, period)
    const { indicators, loading: indLoading } = useIndicators(activeTicker, period)

    return (
        <>
            <Sidebar />
            <main className="main-content">
                <Header ticker={activeTicker} setActiveTicker={setActiveTicker} />

                <div className="dashboard">
                    <StockChart
                        ticker={stockData?.ticker || activeTicker}
                        price={stockData?.price || 0}
                        change={stockData?.change || 0}
                        changePct={stockData?.changePct || 0}
                        history={stockData?.history || []}
                        indicators={indicators}
                        loading={stockLoading || !stockData || indLoading}
                        period={period}
                        onPeriodChange={setPeriod}
                    />

                    <StatsRow
                        peRatio={stockData?.peRatio}
                        marketCap={stockData?.marketCap}
                        fiftyTwoWeekHigh={stockData?.fiftyTwoWeekHigh}
                        fiftyTwoWeekLow={stockData?.fiftyTwoWeekLow}
                        loading={stockLoading || !stockData}
                    />

                    <ChatPanel
                        messages={messages}
                        isStreaming={isStreaming}
                        onSend={sendMessage}
                    />
                </div>
            </main>
        </>
    )
}

export default App

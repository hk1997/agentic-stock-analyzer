import React, { useState } from 'react'
import { Sidebar } from './components/layout/Sidebar'
import { Header } from './components/layout/Header'
import { StockChart } from './components/chart/StockChart'
import { StatsRow } from './components/stats/StatCard'
import { ChatPanel } from './components/chat/ChatPanel'
import { StrategyBuilder } from './components/StrategyBuilder'
import FundamentalHighlights from './components/FundamentalHighlights'
import { NewsPanel } from './components/NewsPanel'
import { FilingsPanel } from './components/FilingsPanel'
import { useChat } from './hooks/useChat'
import { useStockData } from './hooks/useStockData'
import { useIndicators } from './hooks/useIndicators'
import type { BacktestResult } from './hooks/useBacktest'

function App() {
    const { messages, isStreaming, sendMessage } = useChat()
    const [activeTicker, setActiveTicker] = useState('AAPL')
    const [period, setPeriod] = useState('1mo')
    const { data: stockData, loading: stockLoading } = useStockData(activeTicker, period)
    const { indicators, loading: indLoading } = useIndicators(activeTicker, period)
    const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null)

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
                        backtestResult={backtestResult}
                        loading={stockLoading || !stockData || indLoading}
                        period={period}
                        onPeriodChange={setPeriod}
                    />

                    <FundamentalHighlights ticker={activeTicker} />

                    <StatsRow
                        peRatio={stockData?.peRatio}
                        marketCap={stockData?.marketCap}
                        fiftyTwoWeekHigh={stockData?.fiftyTwoWeekHigh}
                        fiftyTwoWeekLow={stockData?.fiftyTwoWeekLow}
                        loading={stockLoading || !stockData}
                    />

                    <NewsPanel ticker={stockData?.ticker || activeTicker} />

                    <FilingsPanel ticker={stockData?.ticker || activeTicker} />

                    <StrategyBuilder
                        ticker={stockData?.ticker || activeTicker}
                        onResult={setBacktestResult}
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

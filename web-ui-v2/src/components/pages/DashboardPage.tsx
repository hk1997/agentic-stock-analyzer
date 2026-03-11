import React, { useState } from 'react'
import { StockChart } from '../chart/StockChart'
import { StatsRow } from '../stats/StatCard'
import { ChatPanel } from '../chat/ChatPanel'
import { StrategyBuilder } from '../StrategyBuilder'
import FundamentalHighlights from '../FundamentalHighlights'
import { NewsPanel } from '../NewsPanel'
import { FilingsPanel } from '../FilingsPanel'
import { Header } from '../layout/Header'
import { useChat } from '../../hooks/useChat'
import { useStockData } from '../../hooks/useStockData'
import { useIndicators } from '../../hooks/useIndicators'
import type { BacktestResult } from '../../hooks/useBacktest'

export function DashboardPage() {
    const { messages, isStreaming, sendMessage } = useChat()
    const [activeTicker, setActiveTicker] = useState('AAPL')
    const [period, setPeriod] = useState('1mo')
    const { data: stockData, loading: stockLoading } = useStockData(activeTicker, period)
    const { indicators, loading: indLoading } = useIndicators(activeTicker, period)
    const [backtestResult, setBacktestResult] = useState<BacktestResult[] | null>(null)

    return (
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

                <StrategyBuilder
                    ticker={stockData?.ticker || activeTicker}
                    onResult={setBacktestResult}
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

                <ChatPanel
                    messages={messages}
                    isStreaming={isStreaming}
                    onSend={sendMessage}
                />
            </div>
        </main>
    )
}

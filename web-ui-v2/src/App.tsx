import { Sidebar } from './components/layout/Sidebar'
import { Header } from './components/layout/Header'
import { StockChart } from './components/chart/StockChart'
import { StatsRow } from './components/stats/StatCard'
import { ChatPanel } from './components/chat/ChatPanel'
import { useChat } from './hooks/useChat'
import { useStockData } from './hooks/useStockData'

function App() {
    const { messages, isStreaming, detectedTicker, sendMessage } = useChat()
    const { data: stockData, loading: stockLoading } = useStockData(detectedTicker)

    return (
        <>
            <Sidebar />
            <main className="main-content">
                <Header ticker={detectedTicker || undefined} />

                <div className="dashboard">
                    <StockChart
                        ticker={stockData?.ticker || detectedTicker || 'AAPL'}
                        price={stockData?.price || 0}
                        change={stockData?.change || 0}
                        changePct={stockData?.changePct || 0}
                        history={stockData?.history || []}
                        loading={stockLoading || (!stockData && !!detectedTicker)}
                    />

                    <StatsRow
                        peRatio={stockData?.peRatio}
                        marketCap={stockData?.marketCap}
                        fiftyTwoWeekHigh={stockData?.fiftyTwoWeekHigh}
                        fiftyTwoWeekLow={stockData?.fiftyTwoWeekLow}
                        loading={stockLoading || (!stockData && !!detectedTicker)}
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

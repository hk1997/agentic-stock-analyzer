interface HeaderProps {
    ticker?: string
    setActiveTicker: (ticker: string) => void
}

import React, { useState } from 'react'
import { Search } from 'lucide-react'

interface HeaderProps {
    ticker?: string
    setActiveTicker: (ticker: string) => void
}

export function Header({ ticker, setActiveTicker }: HeaderProps) {
    const [inputValue, setInputValue] = useState(ticker || '')

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        if (inputValue.trim()) {
            setActiveTicker(inputValue.trim().toUpperCase())
        }
    }

    return (
        <header className="header">
            <div>
                <h1 className="header__title">
                    {ticker ? `Analyzing ${ticker}` : 'Stock Analyzer'}
                </h1>
                <p className="header__subtitle">AI-powered multi-agent analysis</p>
            </div>

            <form className="header__search" onSubmit={handleSubmit}>
                <div className="header__search-input-wrapper">
                    <Search className="header__search-icon" size={18} />
                    <input
                        type="text"
                        className="header__search-input"
                        placeholder="Search ticker (e.g. AAPL)"
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value.toUpperCase())}
                    />
                </div>
            </form>

            <div className="header__avatar">U</div>
        </header>
    )
}

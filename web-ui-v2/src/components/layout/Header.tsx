interface HeaderProps {
    ticker?: string
}

export function Header({ ticker }: HeaderProps) {
    return (
        <header className="header">
            <div>
                <h1 className="header__title">
                    {ticker ? `Analyzing ${ticker}` : 'Stock Analyzer'}
                </h1>
                <p className="header__subtitle">AI-powered multi-agent analysis</p>
            </div>
            <div className="header__avatar">U</div>
        </header>
    )
}

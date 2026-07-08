-- AIFXBOT Database Schema
-- Supabase PostgreSQL schema for trade entries, market data, and analysis

-- ============================================
-- 1. ENTRIES: User trading/investment entries
-- ============================================
CREATE TABLE IF NOT EXISTS entries (
    id              SERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    
    -- Entry details
    symbol          TEXT NOT NULL,           -- e.g., AAPL, 600519.SH, BTC-USD
    name            TEXT,                     -- Company/asset name
    market          TEXT DEFAULT 'US',      -- US, CN, HK, CRYPTO, FOREX
    entry_type      TEXT DEFAULT 'stock',    -- stock, crypto, forex, option, etf
    
    -- Trade details
    direction       TEXT DEFAULT 'long',     -- long, short
    entry_price     NUMERIC(18, 8) NOT NULL,
    quantity        NUMERIC(18, 8) NOT NULL DEFAULT 1,
    entry_date      DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Strategy & analysis
    strategy        TEXT,                     -- e.g., momentum, value, swing
    timeframe       TEXT DEFAULT 'daily',   -- intraday, daily, weekly, monthly
    stop_loss       NUMERIC(18, 8),
    take_profit     NUMERIC(18, 8),
    risk_pct        NUMERIC(5, 2),           -- % of portfolio risked
    
    -- Metadata
    notes           TEXT,
    tags            TEXT[],                  -- Array of tags
    status          TEXT DEFAULT 'active',   -- active, closed, paused
    user_id         UUID REFERENCES auth.users(id) ON DELETE SET NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_entries_symbol ON entries(symbol);
CREATE INDEX IF NOT EXISTS idx_entries_status ON entries(status);
CREATE INDEX IF NOT EXISTS idx_entries_user ON entries(user_id);

-- ============================================
-- 2. MARKET_DATA: Cached live market snapshots
-- ============================================
CREATE TABLE IF NOT EXISTS market_data (
    id              SERIAL PRIMARY KEY,
    fetched_at      TIMESTAMPTZ DEFAULT NOW(),
    
    symbol          TEXT NOT NULL,
    market          TEXT DEFAULT 'US',
    
    -- Price data
    current_price   NUMERIC(18, 8),
    previous_close  NUMERIC(18, 8),
    open_price      NUMERIC(18, 8),
    high_price      NUMERIC(18, 8),
    low_price       NUMERIC(18, 8),
    
    -- Change metrics
    change_abs      NUMERIC(18, 8),
    change_pct      NUMERIC(10, 4),
    
    -- Volume & liquidity
    volume          BIGINT,
    avg_volume      BIGINT,
    market_cap      NUMERIC(20, 2),
    
    -- Technical (from Yahoo Finance)
    fifty_two_week_high     NUMERIC(18, 8),
    fifty_two_week_low      NUMERIC(18, 8),
    fifty_day_ma            NUMERIC(18, 8),
    two_hundred_day_ma      NUMERIC(18, 8),
    
    -- Valuation
    pe_ratio        NUMERIC(10, 2),
    eps             NUMERIC(18, 4),
    
    -- Metadata
    currency        TEXT DEFAULT 'USD',
    exchange        TEXT,
    is_market_open  BOOLEAN,
    
    -- Keep only latest per symbol (optional optimization)
    UNIQUE(symbol)
);

CREATE INDEX IF NOT EXISTS idx_market_symbol ON market_data(symbol);
CREATE INDEX IF NOT EXISTS idx_market_fetched ON market_data(fetched_at);

-- ============================================
-- 3. ANALYSIS_LOGS: Computed analysis for each entry
-- ============================================
CREATE TABLE IF NOT EXISTS analysis_logs (
    id              SERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    entry_id        INTEGER REFERENCES entries(id) ON DELETE CASCADE,
    
    -- P&L Calculation
    unrealized_pnl  NUMERIC(18, 8),          -- (current - entry) * qty
    realized_pnl    NUMERIC(18, 8) DEFAULT 0, -- When position is closed
    return_pct      NUMERIC(10, 4),           -- % return
    
    -- Risk metrics
    risk_reward_ratio       NUMERIC(10, 4),
    distance_to_stop        NUMERIC(18, 8),
    distance_to_target      NUMERIC(18, 8),
    max_drawdown_pct        NUMERIC(10, 4),
    
    -- Market context
    market_trend    TEXT,                     -- bullish, bearish, neutral, volatile
    vs_50d_ma       NUMERIC(10, 4),          -- % above/below 50-day MA
    vs_200d_ma      NUMERIC(10, 4),          -- % above/below 200-day MA
    vs_52w_high     NUMERIC(10, 4),          -- % from 52-week high
    vs_52w_low      NUMERIC(10, 4),          -- % from 52-week low
    
    -- AI Recommendation
    recommendation TEXT,                     -- strong_buy, buy, hold, reduce, sell, strong_sell
    confidence       NUMERIC(5, 2),            -- 0-100 confidence score
    reasoning        TEXT,                     -- Detailed reasoning
    
    -- Next action
    suggested_action TEXT,                   -- add, hold, trim, exit, set_alert
    alert_price    NUMERIC(18, 8),           -- Price to watch for next action
    
    -- Metadata
    data_freshness_hours NUMERIC(5, 2)       -- How stale the market data is
);

CREATE INDEX IF NOT EXISTS idx_analysis_entry ON analysis_logs(entry_id);
CREATE INDEX IF NOT EXISTS idx_analysis_created ON analysis_logs(created_at);

-- ============================================
-- 4. Row Level Security (RLS) - Enable per-user isolation
-- ============================================
ALTER TABLE entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_logs ENABLE ROW LEVEL SECURITY;

-- Policies for entries
CREATE POLICY "Users can view own entries" ON entries
    FOR SELECT USING (auth.uid() = user_id OR user_id IS NULL);
CREATE POLICY "Users can insert own entries" ON entries
    FOR INSERT WITH CHECK (auth.uid() = user_id OR user_id IS NULL);
CREATE POLICY "Users can update own entries" ON entries
    FOR UPDATE USING (auth.uid() = user_id OR user_id IS NULL);
CREATE POLICY "Users can delete own entries" ON entries
    FOR DELETE USING (auth.uid() = user_id OR user_id IS NULL);

-- Market data is public within the app
CREATE POLICY "Market data readable by all" ON market_data
    FOR SELECT USING (true);
CREATE POLICY "Only service can write market data" ON market_data
    FOR INSERT WITH CHECK (false); -- Use service key or edge function

-- Analysis logs follow entries
CREATE POLICY "Users can view own analysis" ON analysis_logs
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM entries e 
            WHERE e.id = analysis_logs.entry_id 
            AND (e.user_id = auth.uid() OR e.user_id IS NULL)
        )
    );

-- ============================================
-- 5. Helper Functions
-- ============================================

-- Auto-update updated_at on entries
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_entries_updated_at
    BEFORE UPDATE ON entries
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- View: Latest analysis with entry details
CREATE OR REPLACE VIEW v_entry_analysis AS
SELECT 
    e.id AS entry_id,
    e.symbol,
    e.name,
    e.market,
    e.entry_type,
    e.direction,
    e.entry_price,
    e.quantity,
    e.entry_date,
    e.strategy,
    e.stop_loss,
    e.take_profit,
    e.status,
    e.notes,
    m.current_price,
    m.change_pct AS daily_change_pct,
    m.market_cap,
    m.pe_ratio,
    a.id AS analysis_id,
    a.unrealized_pnl,
    a.return_pct,
    a.risk_reward_ratio,
    a.market_trend,
    a.vs_50d_ma,
    a.vs_200d_ma,
    a.recommendation,
    a.confidence,
    a.reasoning,
    a.suggested_action,
    a.alert_price,
    a.created_at AS analysis_time
FROM entries e
LEFT JOIN market_data m ON e.symbol = m.symbol
LEFT JOIN LATERAL (
    SELECT * FROM analysis_logs 
    WHERE entry_id = e.id 
    ORDER BY created_at DESC 
    LIMIT 1
) a ON true
WHERE e.status = 'active';

-- ============================================
-- 6. Sample Data (Optional - remove in production)
-- ============================================
INSERT INTO entries (symbol, name, market, entry_price, quantity, entry_date, strategy, stop_loss, take_profit, notes, tags)
VALUES 
    ('AAPL', 'Apple Inc.', 'US', 185.50, 10, '2025-06-15', 'momentum', 170.00, 210.00, 'Tech sector momentum play', ARRAY['tech', 'momentum']),
    ('BTC-USD', 'Bitcoin', 'CRYPTO', 65000.00, 0.5, '2025-05-01', 'swing', 55000.00, 80000.00, 'Crypto diversification', ARRAY['crypto', 'swing']),
    ('NVDA', 'NVIDIA Corp.', 'US', 120.00, 25, '2025-06-20', 'growth', 100.00, 160.00, 'AI infrastructure bet', ARRAY['tech', 'AI', 'growth'])
ON CONFLICT DO NOTHING;

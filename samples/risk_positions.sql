-- Risk Positions table — BCBS 239 compliant risk data
-- Source: Front Office Risk System (FORS) → Risk Data Aggregation Layer
-- Retention: 7 years per Basel IV requirements
-- Classification: RESTRICTED — contains counterparty and instrument-level risk data

CREATE TABLE risk.trading_positions (
    position_id         VARCHAR(36)     NOT NULL,   -- UUID primary key
    as_of_date          DATE            NOT NULL,   -- Risk date (T)
    book_id             VARCHAR(20)     NOT NULL,   -- Trading book identifier (foreign key: books.book_id)
    desk_id             VARCHAR(20)     NOT NULL,   -- Trading desk identifier
    trader_id           VARCHAR(20),               -- Individual trader assigned (nullable for automated strategies)
    counterparty_id     VARCHAR(20)     NOT NULL,   -- LEI or internal counterparty ID (foreign key: counterparties.counterparty_id)
    instrument_id       VARCHAR(50)     NOT NULL,   -- Internal instrument identifier
    instrument_type     VARCHAR(30)     NOT NULL,   -- EQUITY, FX_SPOT, FX_FORWARD, IR_SWAP, CDS, BOND, OPTION, FUTURE
    isin                VARCHAR(12),               -- ISO 6166 ISIN (nullable for OTC instruments)
    cusip               VARCHAR(9),                -- CUSIP for US instruments (nullable)
    notional_amount     DECIMAL(20,4)   NOT NULL,   -- Notional in trade currency
    notional_currency   VARCHAR(3)      NOT NULL,   -- ISO 4217 currency code
    market_value        DECIMAL(20,4),             -- Mark-to-market value in reporting currency
    market_value_currency VARCHAR(3)    NOT NULL,   -- Reporting currency (typically GBP)
    book_value          DECIMAL(20,4),             -- Accrual/book value
    unrealised_pnl      DECIMAL(20,4),             -- Unrealised P&L vs. previous close
    realised_pnl_ytd    DECIMAL(20,4),             -- Realised P&L year-to-date
    var_1d_99           DECIMAL(15,4),             -- 1-day 99% Value at Risk (historical simulation)
    var_10d_99          DECIMAL(15,4),             -- 10-day 99% VaR (scaled, Basel III regulatory capital)
    stressed_var        DECIMAL(15,4),             -- Stressed VaR (12-month stressed period)
    expected_shortfall  DECIMAL(15,4),             -- Expected Shortfall / CVaR (99% confidence)
    delta               DECIMAL(15,8),             -- Price sensitivity (delta, DV01 for IR)
    gamma               DECIMAL(15,8),             -- Second-order price sensitivity
    vega                DECIMAL(15,8),             -- Sensitivity to implied volatility
    theta               DECIMAL(15,8),             -- Time decay
    rho                 DECIMAL(15,8),             -- Interest rate sensitivity
    maturity_date       DATE,                      -- Instrument maturity / expiry date
    trade_date          DATE,                      -- Original trade execution date
    settlement_date     DATE,                      -- Settlement date
    risk_factor_id      VARCHAR(50),               -- Primary market risk factor identifier
    asset_class         VARCHAR(20)     NOT NULL,   -- EQUITY, RATES, CREDIT, FX, COMMODITY
    sub_asset_class     VARCHAR(30),               -- More granular classification
    hedge_designation   VARCHAR(20),               -- FVTPL, FVOCI, AMORTISED_COST, FAIR_VALUE_HEDGE
    regulatory_flag     VARCHAR(10),               -- FRTB_TB (Trading Book), FRTB_BB (Banking Book)
    netting_set_id      VARCHAR(30),               -- ISDA netting set for counterparty credit risk
    collateral_amount   DECIMAL(15,4),             -- Collateral posted/received for the netting set
    credit_exposure     DECIMAL(15,4),             -- Net counterparty credit exposure after netting
    is_internal_trade   BOOLEAN         NOT NULL DEFAULT FALSE, -- True for interdesk/intragroup trades
    data_quality_flag   VARCHAR(10),               -- CLEAN, ESTIMATED, OVERRIDE, MISSING
    source_system       VARCHAR(30)     NOT NULL DEFAULT 'FORS', -- Source system for BCBS 239 lineage
    load_timestamp      TIMESTAMP       NOT NULL,   -- When record was loaded into risk warehouse
    last_updated        TIMESTAMP       NOT NULL,   -- Last modification timestamp

    CONSTRAINT pk_risk_positions PRIMARY KEY (position_id, as_of_date),
    CONSTRAINT fk_book FOREIGN KEY (book_id) REFERENCES books(book_id),
    CONSTRAINT fk_counterparty FOREIGN KEY (counterparty_id) REFERENCES counterparties(counterparty_id),
    CONSTRAINT chk_asset_class CHECK (asset_class IN ('EQUITY','RATES','CREDIT','FX','COMMODITY','OTHER')),
    CONSTRAINT chk_data_quality CHECK (data_quality_flag IN ('CLEAN','ESTIMATED','OVERRIDE','MISSING') OR data_quality_flag IS NULL)
);

CREATE INDEX idx_risk_as_of_date ON risk.trading_positions(as_of_date);
CREATE INDEX idx_risk_book_date ON risk.trading_positions(book_id, as_of_date);
CREATE INDEX idx_risk_counterparty ON risk.trading_positions(counterparty_id, as_of_date);
CREATE INDEX idx_risk_asset_class ON risk.trading_positions(asset_class, as_of_date);

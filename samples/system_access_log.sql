-- System access and data export audit log
-- Captures all authenticated user interactions with core banking applications
-- Feeds the SIEM platform and is the primary source for access control reviews

CREATE TABLE system_access_log (
    log_id           BIGSERIAL        PRIMARY KEY,
    event_ts         TIMESTAMPTZ      NOT NULL,
    session_id       VARCHAR(64),
    user_id          VARCHAR(50)      NOT NULL,
    ip_addr          VARCHAR(45),
    user_agent       VARCHAR(500),
    action_cd        VARCHAR(30)      NOT NULL,
    resource_type    VARCHAR(50),
    resource_id      VARCHAR(100),
    outcome_cd       VARCHAR(10)      NOT NULL DEFAULT 'OK',
    error_cd         VARCHAR(20),
    duration_ms      INTEGER,
    bytes_xfer       BIGINT,
    geo_country      CHAR(2),
    geo_city         VARCHAR(100),
    mfa_used         BOOLEAN          NOT NULL DEFAULT FALSE,
    risk_score       SMALLINT,
    dept_cd          VARCHAR(20),
    app_name         VARCHAR(100)     NOT NULL,
    app_version      VARCHAR(20),
    data_accessed    TEXT,
    export_flag      BOOLEAN          NOT NULL DEFAULT FALSE,
    sensitive_flag   BOOLEAN          NOT NULL DEFAULT FALSE,
    prev_action_cd   VARCHAR(30),
    time_since_prev  INTEGER,
    retention_days   INTEGER          NOT NULL DEFAULT 2555
);

CREATE INDEX idx_sal_event_ts  ON system_access_log (event_ts DESC);
CREATE INDEX idx_sal_user_id   ON system_access_log (user_id, event_ts DESC);
CREATE INDEX idx_sal_outcome   ON system_access_log (outcome_cd) WHERE outcome_cd != 'OK';
CREATE INDEX idx_sal_export    ON system_access_log (export_flag, event_ts DESC) WHERE export_flag = TRUE;

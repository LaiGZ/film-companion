-- ============================================================
-- 胶片伴侣 AI - 数据库初始化
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. 会话表
CREATE TABLE IF NOT EXISTS chat_session (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT NOT NULL DEFAULT 'default',
    title           VARCHAR(255),
    platform        VARCHAR(50) DEFAULT 'cli',
    status          VARCHAR(20) DEFAULT 'active',
    meta            JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    last_activity   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_session_user ON chat_session(user_id);
CREATE INDEX idx_session_activity ON chat_session(last_activity DESC);

-- 2. 消息表
CREATE TABLE IF NOT EXISTS chat_message (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL DEFAULT 'default',
    role            VARCHAR(20) NOT NULL,
    content         TEXT NOT NULL,
    content_type    VARCHAR(20) DEFAULT 'text',
    turn_index      INTEGER NOT NULL,
    parent_id       UUID REFERENCES chat_message(id),
    meta            JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_msg_session ON chat_message(session_id, turn_index);
CREATE INDEX idx_msg_user ON chat_message(user_id);
CREATE INDEX idx_msg_created ON chat_message(created_at);

-- 3. 胶卷表
CREATE TABLE IF NOT EXISTS film (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT NOT NULL DEFAULT 'default',
    name            VARCHAR(255) NOT NULL,
    film_type       VARCHAR(50),
    iso             INTEGER,
    format          VARCHAR(50) DEFAULT '135',
    quantity        INTEGER DEFAULT 0,
    unit            VARCHAR(20) DEFAULT '卷',
    purchase_date   DATE,
    expiry_date     DATE,
    price           DECIMAL(10,2),
    currency        VARCHAR(10) DEFAULT 'CNY',
    storage_location VARCHAR(255),
    status          VARCHAR(20) DEFAULT '未使用',
    meta            JSONB DEFAULT '{}'::jsonb,
    embedding       vector(1536),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_quantity CHECK (quantity >= 0)
);

CREATE INDEX idx_film_user ON film(user_id);
CREATE INDEX idx_film_type ON film(film_type);
CREATE INDEX idx_film_status ON film(status);
CREATE INDEX idx_film_expiry ON film(expiry_date);
CREATE INDEX idx_film_meta_gin ON film USING GIN (meta);

-- 4. 设备表
CREATE TABLE IF NOT EXISTS gear (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT NOT NULL DEFAULT 'default',
    name            VARCHAR(255) NOT NULL,
    gear_type       VARCHAR(50) NOT NULL,
    brand           VARCHAR(100),
    model           VARCHAR(100),
    nickname        VARCHAR(100),
    serial_number   VARCHAR(100),
    purchase_date   DATE,
    price           DECIMAL(10,2),
    currency        VARCHAR(10) DEFAULT 'CNY',
    condition       VARCHAR(50),
    status          VARCHAR(20) DEFAULT '在用',
    storage_location VARCHAR(255),
    meta            JSONB DEFAULT '{}'::jsonb,
    embedding       vector(1536),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_gear_user ON gear(user_id);
CREATE INDEX idx_gear_type ON gear(gear_type);
CREATE INDEX idx_gear_status ON gear(status);
CREATE INDEX idx_gear_meta_gin ON gear USING GIN (meta);

-- 5. 消息-实体关联表
CREATE TABLE IF NOT EXISTS message_entity_link (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id      UUID NOT NULL REFERENCES chat_message(id) ON DELETE CASCADE,
    entity_type     VARCHAR(100) NOT NULL,
    entity_id       UUID NOT NULL,
    action          VARCHAR(50) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_link_message ON message_entity_link(message_id);
CREATE INDEX idx_link_entity ON message_entity_link(entity_type, entity_id);

-- 6. 审计日志表
CREATE TABLE IF NOT EXISTS data_audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT NOT NULL DEFAULT 'default',
    session_id      UUID,
    message_id      UUID,
    entity_link_id  UUID,
    operation       VARCHAR(50) NOT NULL,
    entity_type     VARCHAR(100) NOT NULL,
    entity_id       UUID,
    sql_text        TEXT NOT NULL,
    sql_params      JSONB DEFAULT '{}'::jsonb,
    data_before     JSONB,
    data_after      JSONB,
    rows_affected   INTEGER DEFAULT 0,
    tool_name       VARCHAR(100),
    tool_args       JSONB DEFAULT '{}'::jsonb,
    status          VARCHAR(20) DEFAULT 'success',
    error_message   TEXT,
    duration_ms     INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON data_audit_log(user_id);
CREATE INDEX idx_audit_entity ON data_audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_time ON data_audit_log(created_at DESC);

-- 7. 长期记忆表
CREATE TABLE IF NOT EXISTS long_term_memory (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT NOT NULL DEFAULT 'default',
    memory_type     VARCHAR(50) NOT NULL,
    category        VARCHAR(50),
    content         TEXT NOT NULL,
    source          TEXT,
    confidence      DECIMAL(3,2) DEFAULT 0.8,
    tags            TEXT[],
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_memory_user ON long_term_memory(user_id);
CREATE INDEX idx_memory_type ON long_term_memory(memory_type);
CREATE INDEX idx_memory_active ON long_term_memory(is_active);

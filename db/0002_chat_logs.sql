-- MiCA Compliance Copilot — conversation log (added v2.1)
--
-- Append-only record of each user question + the agent's answer, for quality monitoring and
-- debugging. IMPORTANT: this table is deliberately OUTSIDE the agent's reach — no tool, no
-- retrieval path, and no context builder reads from it. The assistant cannot see past
-- conversations; only the request handler writes here. It is never embedded or searched.

CREATE TABLE IF NOT EXISTS chat_logs (
    id          bigserial   PRIMARY KEY,
    created_at  timestamptz NOT NULL DEFAULT now(),
    question    text        NOT NULL,
    answer      text        NOT NULL DEFAULT '',
    grounded    boolean     NOT NULL DEFAULT false,
    model       text,
    citations   jsonb       NOT NULL DEFAULT '[]'::jsonb,
    tool_events jsonb       NOT NULL DEFAULT '[]'::jsonb,
    usage       jsonb       NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS chat_logs_created_idx ON chat_logs (created_at DESC);

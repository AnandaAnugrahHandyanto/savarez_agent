-- Canonical memory schema for VPS 1
-- Postgres 16+
-- Append-only event log; derived memory tables referenced back to sources.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS memory_sources (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type     text NOT NULL,               -- telegram, api, manual, webhook, system
    source_ref      text NOT NULL,               -- chat id, file path, URL, job id, etc.
    title          text,
    metadata       jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_type, source_ref)
);

CREATE TABLE IF NOT EXISTS memory_entities (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type     text NOT NULL,               -- person, project, system, machine, org, topic
    canonical_name  text NOT NULL,
    external_ref    text,
    metadata       jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (entity_type, canonical_name)
);

CREATE TABLE IF NOT EXISTS memory_event_log (
    id              bigserial PRIMARY KEY,
    occurred_at     timestamptz NOT NULL DEFAULT now(),
    actor_type      text NOT NULL,               -- user, agent, system, job
    actor_id        text,
    entity_id       uuid REFERENCES memory_entities(id) ON DELETE SET NULL,
    event_type      text NOT NULL,               -- message, note, state_change, decision, observation
    payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_id       uuid NOT NULL REFERENCES memory_sources(id) ON DELETE RESTRICT,
    checksum       text,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_event_log_occurred_at ON memory_event_log (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_event_log_entity_id ON memory_event_log (entity_id);
CREATE INDEX IF NOT EXISTS idx_memory_event_log_event_type ON memory_event_log (event_type);
CREATE INDEX IF NOT EXISTS idx_memory_event_log_payload_gin ON memory_event_log USING GIN (payload);

CREATE TABLE IF NOT EXISTS memory_facts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_entity_id uuid REFERENCES memory_entities(id) ON DELETE SET NULL,
    fact_key       text NOT NULL,
    fact_value     jsonb NOT NULL,
    confidence     numeric(4,3) NOT NULL DEFAULT 1.000,
    valid_from     timestamptz,
    valid_to       timestamptz,
    source_event_id bigint NOT NULL REFERENCES memory_event_log(id) ON DELETE RESTRICT,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (subject_entity_id, fact_key, source_event_id)
);

CREATE INDEX IF NOT EXISTS idx_memory_facts_subject ON memory_facts (subject_entity_id);
CREATE INDEX IF NOT EXISTS idx_memory_facts_key ON memory_facts (fact_key);
CREATE INDEX IF NOT EXISTS idx_memory_facts_value_gin ON memory_facts USING GIN (fact_value);

CREATE TABLE IF NOT EXISTS memory_decisions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_key   text NOT NULL,
    title          text NOT NULL,
    decision_text  text NOT NULL,
    rationale      text,
    status         text NOT NULL DEFAULT 'active', -- active, superseded, revoked
    decided_at     timestamptz NOT NULL DEFAULT now(),
    decided_by     text,
    source_event_id bigint NOT NULL REFERENCES memory_event_log(id) ON DELETE RESTRICT,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (decision_key, source_event_id)
);

CREATE INDEX IF NOT EXISTS idx_memory_decisions_key ON memory_decisions (decision_key);
CREATE INDEX IF NOT EXISTS idx_memory_decisions_status ON memory_decisions (status);

CREATE TABLE IF NOT EXISTS memory_episodes (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       uuid REFERENCES memory_entities(id) ON DELETE SET NULL,
    title          text NOT NULL,
    summary        text,
    started_at     timestamptz NOT NULL,
    ended_at       timestamptz,
    source_start_event_id bigint REFERENCES memory_event_log(id) ON DELETE SET NULL,
    source_end_event_id bigint REFERENCES memory_event_log(id) ON DELETE SET NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_episodes_entity ON memory_episodes (entity_id);
CREATE INDEX IF NOT EXISTS idx_memory_episodes_started_at ON memory_episodes (started_at DESC);

CREATE TABLE IF NOT EXISTS memory_summaries (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type     text NOT NULL,               -- entity, episode, time_window, project
    scope_id       uuid,
    summary        text NOT NULL,
    source_range   jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_summaries_scope ON memory_summaries (scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_memory_summaries_source_range_gin ON memory_summaries USING GIN (source_range);

-- Append-only guardrails
CREATE OR REPLACE FUNCTION memory_block_event_log_mutations()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'memory_event_log is append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_memory_event_log_no_update ON memory_event_log;
CREATE TRIGGER trg_memory_event_log_no_update
BEFORE UPDATE OR DELETE ON memory_event_log
FOR EACH ROW
EXECUTE FUNCTION memory_block_event_log_mutations();

-- Updated-at helper
CREATE OR REPLACE FUNCTION memory_touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_memory_entities_updated_at ON memory_entities;
CREATE TRIGGER trg_memory_entities_updated_at
BEFORE UPDATE ON memory_entities
FOR EACH ROW EXECUTE FUNCTION memory_touch_updated_at();

DROP TRIGGER IF EXISTS trg_memory_facts_updated_at ON memory_facts;
CREATE TRIGGER trg_memory_facts_updated_at
BEFORE UPDATE ON memory_facts
FOR EACH ROW EXECUTE FUNCTION memory_touch_updated_at();

DROP TRIGGER IF EXISTS trg_memory_decisions_updated_at ON memory_decisions;
CREATE TRIGGER trg_memory_decisions_updated_at
BEFORE UPDATE ON memory_decisions
FOR EACH ROW EXECUTE FUNCTION memory_touch_updated_at();

DROP TRIGGER IF EXISTS trg_memory_episodes_updated_at ON memory_episodes;
CREATE TRIGGER trg_memory_episodes_updated_at
BEFORE UPDATE ON memory_episodes
FOR EACH ROW EXECUTE FUNCTION memory_touch_updated_at();

DROP TRIGGER IF EXISTS trg_memory_summaries_updated_at ON memory_summaries;
CREATE TRIGGER trg_memory_summaries_updated_at
BEFORE UPDATE ON memory_summaries
FOR EACH ROW EXECUTE FUNCTION memory_touch_updated_at();

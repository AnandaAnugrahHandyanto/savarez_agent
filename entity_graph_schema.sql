-- Entity Graph Schema for Hermes Session Relationship Tracking
-- Add this to existing state.db or use separately

-- Entities table: stores extracted entities (projects, files, skills, tools, preferences, decisions)
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,           -- project, file, skill, tool, preference, decision
    name TEXT NOT NULL,            -- original name as seen
    normalized_name TEXT NOT NULL, -- lowercase for matching
    first_seen REAL NOT NULL,     -- timestamp when first seen
    last_seen REAL NOT NULL,      -- timestamp when last seen
    occurrence_count INTEGER DEFAULT 1,
    metadata TEXT,                -- JSON for extra data
    UNIQUE(type, normalized_name)
);

-- Session-Entity links: connects entities to sessions
CREATE TABLE IF NOT EXISTS session_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,     -- references sessions.id in state.db
    entity_id INTEGER NOT NULL,   -- references entities.id
    first_linked REAL NOT NULL,
    last_linked REAL NOT NULL,
    context_snippet TEXT,         -- context where entity was found
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    UNIQUE(session_id, entity_id)
);

-- Entity relationships: bidirectional links between entities
CREATE TABLE IF NOT EXISTS entity_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_a INTEGER NOT NULL,   -- references entities.id
    entity_b INTEGER NOT NULL,   -- references entities.id
    relationship_type TEXT NOT NULL, -- relates_to, part_of, uses, depends_on
    first_connected REAL NOT NULL,
    last_connected REAL NOT NULL,
    weight INTEGER DEFAULT 1,    -- stronger = more frequently related
    FOREIGN KEY (entity_a) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_b) REFERENCES entities(id) ON DELETE CASCADE,
    UNIQUE(entity_a, entity_b, relationship_type)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(normalized_name);
CREATE INDEX IF NOT EXISTS idx_session_entities_session ON session_entities(session_id);
CREATE INDEX IF NOT EXISTS idx_session_entities_entity ON session_entities(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_a ON entity_relationships(entity_a);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_b ON entity_relationships(entity_b);

-- Entity type values:
--   project   - Named projects or work areas
--   file      - File paths or names mentioned
--   skill     - Skills or capabilities
--   tool      - Tools (code, CLI, etc.) used
--   preference - User preferences expressed
--   decision  - Decisions made during session

-- Relationship type values:
--   relates_to  - Generic relationship
--   part_of     - Entity is part of another
--   uses        - Entity uses another
--   depends_on  - Entity depends on another
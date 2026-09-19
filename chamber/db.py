"""SQLite schema and connection. Invariants that SQLite can enforce live here, not in Python."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

LEVELS = ('FACT', 'COACH_GOLD', 'CONSENSUS', 'PRO_LINE', 'SIMULATION', 'HEURISTIC', 'UNKNOWN')
# Only these levels may decide whether an answer was correct. PRO_LINE/SIMULATION/HEURISTIC never grade.
GRADING_LEVELS = ('FACT', 'COACH_GOLD', 'CONSENSUS')
SKILLS = ('planning', 'sequencing', 'prize_mapping', 'board_bench_discipline', 'resource_management',
          'damage_allocation', 'opponent_modeling', 'endgame')
FAMILIES = ('setup', 'search', 'discard', 'attach', 'evolve', 'switch', 'bench', 'supporter', 'attack',
            'damage_target', 'effect_target', 'other')
SOURCE_TYPES = ('ptcgl_log', 'pro_match', 'coach_note', 'manual', 'tcgmasters_link', 'prizemap_link', 'other')
COMPLETENESS = ('EXHAUSTIVE', 'PARTIAL', 'PLAUSIBLE', 'UNKNOWN')
# exact/high = reconstruction trustworthy enough to carry FACT evidence.
RECONSTRUCTION = ('exact', 'high', 'medium', 'low', 'unknown')
PLAN_FIELDS = ('objective', 'prize_map', 'opponent_plan', 'preserve')

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS deck_versions (
  hash TEXT PRIMARY KEY,
  deck_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  cards TEXT NOT NULL,              -- JSON [[qty, name, set, number], ...] sorted
  source TEXT NOT NULL,
  format TEXT NOT NULL DEFAULT '',
  date TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  UNIQUE (deck_id, version)
);
CREATE TRIGGER IF NOT EXISTS deck_versions_immutable BEFORE UPDATE ON deck_versions
BEGIN SELECT RAISE(ABORT, 'deck versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS deck_versions_no_delete BEFORE DELETE ON deck_versions
BEGIN SELECT RAISE(ABORT, 'deck versions are immutable'); END;

CREATE TABLE IF NOT EXISTS raw_sources (
  id INTEGER PRIMARY KEY,
  source_type TEXT NOT NULL CHECK (source_type IN {SOURCE_TYPES}),
  content TEXT NOT NULL DEFAULT '',
  url TEXT NOT NULL DEFAULT '',
  sha256 TEXT NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{{}}',
  deck_hash TEXT REFERENCES deck_versions(hash),
  matchup TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS raw_sources_no_update BEFORE UPDATE ON raw_sources
BEGIN SELECT RAISE(ABORT, 'raw sources are immutable'); END;
CREATE TRIGGER IF NOT EXISTS raw_sources_no_delete BEFORE DELETE ON raw_sources
BEGIN SELECT RAISE(ABORT, 'raw sources are immutable'); END;

CREATE TABLE IF NOT EXISTS candidate_cases (
  id INTEGER PRIMARY KEY,
  source_id INTEGER REFERENCES raw_sources(id),
  data TEXT NOT NULL,               -- untrusted draft, same keys as a DecisionCase
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'promoted', 'rejected')),
  case_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS concepts (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  definition TEXT NOT NULL,
  skill TEXT NOT NULL CHECK (skill IN {SKILLS}),
  notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'retired')),
  fsrs_card TEXT,                   -- py-fsrs Card.to_json(); NULL = never reviewed
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_cases (
  id TEXT PRIMARY KEY,
  version INTEGER NOT NULL DEFAULT 1,
  source_id INTEGER REFERENCES raw_sources(id),
  deck_hash TEXT REFERENCES deck_versions(hash),
  format TEXT NOT NULL DEFAULT '',
  date TEXT NOT NULL DEFAULT '',
  matchup TEXT NOT NULL DEFAULT '',
  observed_state TEXT NOT NULL,     -- only what the player could know at decision time
  full_record TEXT NOT NULL DEFAULT '',  -- may contain hindsight: never in the player view
  unknown_fields TEXT NOT NULL DEFAULT '[]',
  prompt TEXT NOT NULL,
  requires TEXT NOT NULL DEFAULT '[]',   -- subset of PLAN_FIELDS to commit before answering
  hint TEXT NOT NULL DEFAULT '',
  decision_family TEXT NOT NULL CHECK (decision_family IN {FAMILIES}),
  criticality INTEGER NOT NULL CHECK (criticality BETWEEN 0 AND 4),
  criticality_source TEXT NOT NULL,
  choices TEXT NOT NULL DEFAULT '[]',    -- [{{"key": "A", "text": "..."}}]
  completeness TEXT NOT NULL CHECK (completeness IN {COMPLETENESS}),
  symptom_tags TEXT NOT NULL DEFAULT '[]',
  root_cause_tags TEXT NOT NULL DEFAULT '[]',
  difficulty INTEGER NOT NULL DEFAULT 2 CHECK (difficulty BETWEEN 1 AND 3),
  transfer_level TEXT NOT NULL DEFAULT 'L2' CHECK (transfer_level IN ('L0', 'L1', 'L2', 'L3')),
  variant_of TEXT REFERENCES decision_cases(id),
  reconstruction TEXT NOT NULL CHECK (reconstruction IN {RECONSTRUCTION}),
  synthetic INTEGER NOT NULL CHECK (synthetic IN (0, 1)),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'stale', 'retired')),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_concepts (
  case_id TEXT NOT NULL REFERENCES decision_cases(id),
  concept_id TEXT NOT NULL REFERENCES concepts(id),
  PRIMARY KEY (case_id, concept_id)
);

-- Append-only: disagreement is preserved, never overwritten.
CREATE TABLE IF NOT EXISTS evidence (
  id INTEGER PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES decision_cases(id),
  level TEXT NOT NULL CHECK (level IN {LEVELS}),
  claim TEXT NOT NULL CHECK (claim <> ''),
  choice TEXT,                      -- the choice key the claim is about, if any
  verdict TEXT CHECK (verdict IN ('good', 'bad')),
  source_ref TEXT NOT NULL DEFAULT '',
  reviewer TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  CHECK (level <> 'PRO_LINE' OR verdict IS NULL),          -- a pro's choice is not a verdict
  CHECK (level NOT IN ('UNKNOWN', 'SIMULATION') OR verdict IS NULL),
  CHECK (level <> 'COACH_GOLD' OR reviewer <> ''),         -- gold needs an identified reviewer
  CHECK (level <> 'CONSENSUS' OR source_ref <> ''),
  CHECK (verdict IS NULL OR choice IS NOT NULL)
);
CREATE TRIGGER IF NOT EXISTS evidence_no_update BEFORE UPDATE ON evidence
BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END;
CREATE TRIGGER IF NOT EXISTS evidence_no_delete BEFORE DELETE ON evidence
BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END;
CREATE TRIGGER IF NOT EXISTS evidence_fact_needs_reconstruction BEFORE INSERT ON evidence
WHEN NEW.level = 'FACT'
 AND (SELECT reconstruction FROM decision_cases WHERE id = NEW.case_id) NOT IN ('exact', 'high')
BEGIN SELECT RAISE(ABORT, 'FACT evidence requires exact/high reconstruction'); END;

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  plan TEXT NOT NULL DEFAULT '[]',
  summary TEXT NOT NULL DEFAULT '{{}}'
);

CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY,
  case_id TEXT REFERENCES decision_cases(id),   -- NULL for a real-game (L4) opportunity
  case_version INTEGER,
  target_concept_id TEXT REFERENCES concepts(id),  -- the ONE concept this rep trains (FSRS updates only it)
  session_id INTEGER REFERENCES sessions(id),
  created_at TEXT NOT NULL,
  plan TEXT NOT NULL DEFAULT '{{}}',
  plan_locked_at TEXT,
  answered_at TEXT,
  choice TEXT,
  other_text TEXT NOT NULL DEFAULT '',
  reasoning TEXT NOT NULL DEFAULT '',
  hint_used INTEGER NOT NULL DEFAULT 0,
  retries INTEGER NOT NULL DEFAULT 0,
  latency_ms INTEGER,
  seen_before INTEGER NOT NULL DEFAULT 0,
  transfer_level TEXT NOT NULL CHECK (transfer_level IN ('L0', 'L1', 'L2', 'L3', 'L4')),
  difficulty INTEGER,
  criticality INTEGER,
  correct INTEGER CHECK (correct IN (0, 1)),     -- only from GRADING_LEVELS evidence
  outcome TEXT CHECK (outcome IN ('ok', 'error')),
  outcome_source TEXT CHECK (outcome_source IN ('evidence', 'self')),
  error_tags TEXT NOT NULL DEFAULT '[]',
  feedback_evidence TEXT NOT NULL DEFAULT '[]',  -- snapshot of the evidence shown
  coach TEXT,
  note TEXT NOT NULL DEFAULT '',
  real_source_id INTEGER REFERENCES raw_sources(id)
);

CREATE TABLE IF NOT EXISTS attempt_concepts (
  attempt_id INTEGER NOT NULL REFERENCES attempts(id),
  concept_id TEXT NOT NULL REFERENCES concepts(id),
  recall INTEGER CHECK (recall BETWEEN 1 AND 4),
  error_relevant INTEGER CHECK (error_relevant IN (0, 1)),
  PRIMARY KEY (attempt_id, concept_id)
);

CREATE TABLE IF NOT EXISTS concept_reviews (
  id INTEGER PRIMARY KEY,
  concept_id TEXT NOT NULL REFERENCES concepts(id),
  attempt_id INTEGER REFERENCES attempts(id),
  rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 4),
  reviewed_at TEXT NOT NULL,
  log TEXT NOT NULL                 -- py-fsrs ReviewLog.to_json(), kept for a future optimizer
);
"""


def default_path() -> Path:
    if os.environ.get('CHAMBER_DB'):
        return Path(os.environ['CHAMBER_DB'])
    base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
    return base / 'dragapult-time-chamber' / 'chamber.db'


def connect(path=None) -> sqlite3.Connection:
    path = Path(path or default_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.executescript(SCHEMA)
    # Tiny forward migration for pre-hardening databases. CREATE TABLE IF NOT EXISTS
    # does not add columns to an existing table.
    cols = {r[1] for r in conn.execute('PRAGMA table_info(attempt_concepts)')}
    if 'error_relevant' not in cols:
        conn.execute('ALTER TABLE attempt_concepts ADD COLUMN error_relevant INTEGER '
                     'CHECK (error_relevant IN (0, 1))')
        conn.commit()
    cols = {r[1] for r in conn.execute('PRAGMA table_info(attempts)')}
    if 'target_concept_id' not in cols:
        # Old attempts keep NULL: they predate the one-target-concept rule and are read as "unknown target".
        conn.execute('ALTER TABLE attempts ADD COLUMN target_concept_id TEXT REFERENCES concepts(id)')
        conn.commit()
    return conn


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def dumps(v) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True)


def row(r) -> dict | None:
    return dict(r) if r is not None else None

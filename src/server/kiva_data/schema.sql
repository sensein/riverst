PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS kiva_person (
  person_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'inactive'))
);

CREATE TABLE IF NOT EXISTS kiva_role (
  role_code TEXT PRIMARY KEY
    CHECK (role_code IN ('learner', 'guardian', 'instructor', 'tester', 'developer')),
  display_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS kiva_person_role (
  person_id TEXT NOT NULL REFERENCES kiva_person(person_id) ON DELETE CASCADE,
  role_code TEXT NOT NULL REFERENCES kiva_role(role_code) ON DELETE RESTRICT,
  PRIMARY KEY (person_id, role_code)
);

CREATE TABLE IF NOT EXISTS kiva_account (
  account_id TEXT PRIMARY KEY,
  person_id TEXT NOT NULL REFERENCES kiva_person(person_id) ON DELETE CASCADE,
  auth_subject TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'inactive'))
);

CREATE INDEX IF NOT EXISTS kiva_idx_account_person
  ON kiva_account(person_id);

CREATE TABLE IF NOT EXISTS kiva_person_profile_value (
  person_id TEXT NOT NULL REFERENCES kiva_person(person_id) ON DELETE CASCADE,
  field_key TEXT NOT NULL,
  value_json TEXT NOT NULL CHECK (json_valid(value_json)),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (person_id, field_key)
);

CREATE TABLE IF NOT EXISTS kiva_study (
  study_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  definition_json TEXT NOT NULL CHECK (json_valid(definition_json)),
  definition_version INTEGER NOT NULL DEFAULT 1 CHECK (definition_version > 0),
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'active', 'closed')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kiva_application (
  application_id TEXT PRIMARY KEY,
  application_key TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'inactive'))
);

CREATE TABLE IF NOT EXISTS kiva_study_application (
  study_id TEXT NOT NULL REFERENCES kiva_study(study_id) ON DELETE CASCADE,
  application_id TEXT NOT NULL REFERENCES kiva_application(application_id) ON DELETE RESTRICT,
  config_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(config_json)),
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  PRIMARY KEY (study_id, application_id)
);

CREATE TABLE IF NOT EXISTS kiva_study_material (
  material_id TEXT PRIMARY KEY,
  study_id TEXT NOT NULL REFERENCES kiva_study(study_id) ON DELETE CASCADE,
  application_id TEXT REFERENCES kiva_application(application_id) ON DELETE SET NULL,
  material_json TEXT NOT NULL CHECK (json_valid(material_json)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS kiva_idx_study_material_study
  ON kiva_study_material(study_id);

CREATE TABLE IF NOT EXISTS kiva_study_enrollment (
  enrollment_id TEXT PRIMARY KEY,
  person_id TEXT NOT NULL REFERENCES kiva_person(person_id) ON DELETE RESTRICT,
  study_id TEXT NOT NULL REFERENCES kiva_study(study_id) ON DELETE RESTRICT,
  enrolled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'inactive', 'withdrawn')),
  UNIQUE (person_id, study_id)
);

CREATE INDEX IF NOT EXISTS kiva_idx_study_enrollment_study
  ON kiva_study_enrollment(study_id, status);

CREATE TABLE IF NOT EXISTS kiva_guardian_learner (
  guardian_person_id TEXT NOT NULL REFERENCES kiva_person(person_id) ON DELETE RESTRICT,
  learner_person_id TEXT NOT NULL REFERENCES kiva_person(person_id) ON DELETE RESTRICT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'inactive')),
  PRIMARY KEY (guardian_person_id, learner_person_id),
  CHECK (guardian_person_id <> learner_person_id)
);

CREATE INDEX IF NOT EXISTS kiva_idx_guardian_learner_learner
  ON kiva_guardian_learner(learner_person_id, status);

CREATE TABLE IF NOT EXISTS kiva_session (
  session_id TEXT PRIMARY KEY,
  study_id TEXT NOT NULL,
  application_id TEXT NOT NULL,
  subject_person_id TEXT NOT NULL REFERENCES kiva_person(person_id) ON DELETE RESTRICT,
  actor_account_id TEXT NOT NULL REFERENCES kiva_account(account_id) ON DELETE RESTRICT,
  actor_person_id TEXT NOT NULL REFERENCES kiva_person(person_id) ON DELETE RESTRICT,
  started_at TEXT,
  ended_at TEXT,
  status TEXT NOT NULL DEFAULT 'created'
    CHECK (status IN ('created', 'running', 'completed', 'abandoned', 'failed')),
  config_snapshot_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(config_snapshot_json)),
  data_location TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (study_id, application_id)
    REFERENCES kiva_study_application(study_id, application_id)
    ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS kiva_idx_session_subject
  ON kiva_session(subject_person_id, started_at);

CREATE INDEX IF NOT EXISTS kiva_idx_session_actor
  ON kiva_session(actor_person_id, started_at);

CREATE INDEX IF NOT EXISTS kiva_idx_session_study
  ON kiva_session(study_id, started_at);

CREATE TABLE IF NOT EXISTS kiva_audit_event (
  event_id TEXT PRIMARY KEY,
  actor_person_id TEXT REFERENCES kiva_person(person_id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  before_json TEXT CHECK (before_json IS NULL OR json_valid(before_json)),
  after_json TEXT CHECK (after_json IS NULL OR json_valid(after_json)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS kiva_idx_audit_entity
  ON kiva_audit_event(entity_type, entity_id, created_at);

INSERT OR IGNORE INTO kiva_role (role_code, display_name) VALUES
  ('learner', 'Learner'),
  ('guardian', 'Guardian'),
  ('instructor', 'Instructor'),
  ('tester', 'Tester'),
  ('developer', 'Developer');

-- Problem tracker (version-aware tester feedback; see docs/PROBLEM_TRACKER_DESIGN.md) ---------

CREATE TABLE IF NOT EXISTS kiva_drop (
  version TEXT NOT NULL,
  env TEXT NOT NULL CHECK (env IN ('local', 'sandbox', 'prod')),
  deployed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  notes TEXT,
  PRIMARY KEY (version, env)
);

CREATE TABLE IF NOT EXISTS kiva_problem (
  problem_id TEXT PRIMARY KEY,
  reporter_person_id TEXT NOT NULL REFERENCES kiva_person(person_id) ON DELETE RESTRICT,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  severity TEXT NOT NULL DEFAULT 'normal'
    CHECK (severity IN ('blocker', 'major', 'normal', 'minor')),
  area TEXT,
  session_id TEXT,
  reported_version TEXT NOT NULL,
  reported_env TEXT NOT NULL CHECK (reported_env IN ('local', 'sandbox', 'prod')),
  client_info TEXT,
  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'fixed_pending_retest', 'reopened', 'closed',
                      'closed_wontfix', 'closed_duplicate', 'closed_notabug')),
  assignee_person_id TEXT REFERENCES kiva_person(person_id) ON DELETE SET NULL,
  fixed_in_version TEXT,
  related_problem_id TEXT REFERENCES kiva_problem(problem_id) ON DELETE SET NULL,
  reported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_problem_status ON kiva_problem(status);
CREATE INDEX IF NOT EXISTS ix_problem_version ON kiva_problem(reported_version, reported_env);
CREATE INDEX IF NOT EXISTS ix_problem_reporter ON kiva_problem(reporter_person_id);

CREATE TABLE IF NOT EXISTS kiva_problem_event (
  event_id TEXT PRIMARY KEY,
  problem_id TEXT NOT NULL REFERENCES kiva_problem(problem_id) ON DELETE CASCADE,
  actor_person_id TEXT NOT NULL REFERENCES kiva_person(person_id) ON DELETE RESTRICT,
  event_type TEXT NOT NULL CHECK (event_type IN
    ('reported', 'assigned', 'marked_fixed', 'retest_requested',
     'confirmed_fixed', 'still_broken', 'reopened', 'closed', 'commented')),
  from_status TEXT,
  to_status TEXT,
  version TEXT,
  note TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_problem_event ON kiva_problem_event(problem_id, created_at);

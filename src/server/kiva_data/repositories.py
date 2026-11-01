from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any, Iterable

from .database import KivaDatabase
from .errors import ConflictError, NotFoundError, ValidationError


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class Repository:
    def __init__(self, database: KivaDatabase):
        self.database = database

    @staticmethod
    def _require(connection: sqlite3.Connection, table: str, key: str, value: str) -> dict[str, Any]:
        row = connection.execute(f"SELECT * FROM {table} WHERE {key} = ?", (value,)).fetchone()
        if row is None:
            raise NotFoundError(f"{table} with {key}={value} was not found")
        return dict(row)

    @staticmethod
    def _audit(
        connection: sqlite3.Connection, action: str, entity_type: str, entity_id: str,
        actor_person_id: str | None = None, before: Any = None, after: Any = None,
    ) -> None:
        connection.execute(
            """INSERT INTO kiva_audit_event
               (event_id, actor_person_id, action, entity_type, entity_id, before_json, after_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (_id(), actor_person_id, action, entity_type, entity_id,
             _json(before) if before is not None else None,
             _json(after) if after is not None else None, _now()),
        )


class PeopleRepository(Repository):
    VALID_ROLES = {"learner", "guardian", "instructor", "tester", "developer"}

    def create(
        self, roles: Iterable[str] = (), profile: dict[str, Any] | None = None,
        actor_person_id: str | None = None, person_id: str | None = None,
    ) -> dict[str, Any]:
        roles = set(roles)
        if unknown := roles - self.VALID_ROLES:
            raise ValidationError(f"Unknown roles: {sorted(unknown)}")
        person_id = person_id or _id()
        with self.database.transaction() as connection:
            connection.execute("INSERT INTO kiva_person (person_id) VALUES (?)", (person_id,))
            connection.executemany(
                "INSERT INTO kiva_person_role (person_id, role_code) VALUES (?, ?)",
                [(person_id, role) for role in sorted(roles)],
            )
            for field_key, value in (profile or {}).items():
                self._write_profile(connection, person_id, field_key, value)
            result = self._read(connection, person_id)
            self._audit(connection, "person.create", "person", person_id, actor_person_id, after=result)
            return result

    def get(self, person_id: str) -> dict[str, Any]:
        with self.database.transaction() as connection:
            return self._read(connection, person_id)

    def find(self, *, person_ids: Iterable[str] | None = None, role: str | None = None,
             study_id: str | None = None, status: str | None = "active") -> list[dict[str, Any]]:
        clauses, params = ["1=1"], []
        if status:
            clauses.append("p.status = ?")
            params.append(status)
        joins = []
        if person_ids is not None:
            values = list(person_ids)
            if not values:
                return []
            clauses.append(f"p.person_id IN ({','.join('?' for _ in values)})")
            params.extend(values)
        if role:
            joins.append("JOIN kiva_person_role pr ON pr.person_id = p.person_id")
            clauses.append("pr.role_code = ?")
            params.append(role)
        if study_id:
            joins.append("JOIN kiva_study_enrollment se ON se.person_id = p.person_id")
            clauses.extend(["se.study_id = ?", "se.status = 'active'"])
            params.append(study_id)
        query = f"SELECT DISTINCT p.person_id FROM kiva_person p {' '.join(joins)} WHERE {' AND '.join(clauses)} ORDER BY p.created_at"
        with self.database.transaction() as connection:
            return [self._read(connection, row["person_id"]) for row in connection.execute(query, params)]

    def update(self, person_id: str, *, profile_patch: dict[str, Any] | None = None,
               roles: Iterable[str] | None = None, status: str | None = None,
               actor_person_id: str | None = None) -> dict[str, Any]:
        if status and status not in {"active", "inactive"}:
            raise ValidationError("Invalid person status")
        if roles is not None and (unknown := set(roles) - self.VALID_ROLES):
            raise ValidationError(f"Unknown roles: {sorted(unknown)}")
        with self.database.transaction() as connection:
            before = self._read(connection, person_id)
            if status:
                connection.execute("UPDATE kiva_person SET status = ? WHERE person_id = ?", (status, person_id))
            if roles is not None:
                connection.execute("DELETE FROM kiva_person_role WHERE person_id = ?", (person_id,))
                connection.executemany("INSERT INTO kiva_person_role (person_id, role_code) VALUES (?, ?)",
                                       [(person_id, role) for role in sorted(set(roles))])
            for field_key, value in (profile_patch or {}).items():
                if value is None:
                    connection.execute("DELETE FROM kiva_person_profile_value WHERE person_id = ? AND field_key = ?", (person_id, field_key))
                else:
                    self._write_profile(connection, person_id, field_key, value)
            after = self._read(connection, person_id)
            self._audit(connection, "person.update", "person", person_id, actor_person_id, before, after)
            return after

    def link_account(self, person_id: str, auth_subject: str, email: str,
                     actor_person_id: str | None = None) -> dict[str, Any]:
        with self.database.transaction() as connection:
            self._require(connection, "kiva_person", "person_id", person_id)
            try:
                account_id = _id()
                connection.execute(
                    "INSERT INTO kiva_account (account_id, person_id, auth_subject, email) VALUES (?, ?, ?, ?)",
                    (account_id, person_id, auth_subject, email.lower()),
                )
            except sqlite3.IntegrityError as error:
                raise ConflictError("Account auth subject or email is already linked") from error
            result = _decode(connection.execute("SELECT * FROM kiva_account WHERE account_id = ?", (account_id,)).fetchone())
            self._audit(connection, "account.link", "account", account_id, actor_person_id, after=result)
            return result

    def resolve_account(self, *, auth_subject: str | None = None, email: str | None = None) -> dict[str, Any]:
        if not auth_subject and not email:
            raise ValidationError("auth_subject or email is required")
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM kiva_account WHERE auth_subject = ? OR email = ?", (auth_subject, (email or "").lower())
            ).fetchone()
            if row is None:
                raise NotFoundError("Account was not found")
            return dict(row)

    def profile_slice(self, person_id: str, field_keys: Iterable[str]) -> dict[str, Any]:
        field_keys = list(field_keys)
        if not field_keys:
            return {}
        with self.database.transaction() as connection:
            self._require(connection, "kiva_person", "person_id", person_id)
            placeholders = ",".join("?" for _ in field_keys)
            rows = connection.execute(
                f"SELECT field_key, value_json FROM kiva_person_profile_value WHERE person_id = ? AND field_key IN ({placeholders})",
                [person_id, *field_keys],
            )
            return {row["field_key"]: json.loads(row["value_json"]) for row in rows}

    def _read(self, connection: sqlite3.Connection, person_id: str) -> dict[str, Any]:
        person = self._require(connection, "kiva_person", "person_id", person_id)
        person["roles"] = [row["role_code"] for row in connection.execute(
            "SELECT role_code FROM kiva_person_role WHERE person_id = ? ORDER BY role_code", (person_id,))]
        person["profile"] = {row["field_key"]: json.loads(row["value_json"]) for row in connection.execute(
            "SELECT field_key, value_json FROM kiva_person_profile_value WHERE person_id = ?", (person_id,))}
        person["accounts"] = [_decode(row) for row in connection.execute(
            "SELECT * FROM kiva_account WHERE person_id = ? ORDER BY created_at", (person_id,))]
        return person

    @staticmethod
    def _write_profile(connection: sqlite3.Connection, person_id: str, field_key: str, value: Any) -> None:
        if not field_key.strip():
            raise ValidationError("Profile field key cannot be empty")
        connection.execute(
            """INSERT INTO kiva_person_profile_value (person_id, field_key, value_json, updated_at)
               VALUES (?, ?, ?, ?) ON CONFLICT(person_id, field_key)
               DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at""",
            (person_id, field_key, _json(value), _now()),
        )


class StudyRepository(Repository):
    def create(self, name: str, definition: dict[str, Any], *, status: str = "draft",
               actor_person_id: str | None = None, study_id: str | None = None) -> dict[str, Any]:
        if status not in {"draft", "active", "closed"}:
            raise ValidationError("Invalid study status")
        study_id = study_id or _id()
        with self.database.transaction() as connection:
            connection.execute("INSERT INTO kiva_study (study_id, name, definition_json, status) VALUES (?, ?, ?, ?)",
                               (study_id, name, _json(definition), status))
            result = self._read(connection, study_id)
            self._audit(connection, "study.create", "study", study_id, actor_person_id, after=result)
            return result

    def get(self, study_id: str) -> dict[str, Any]:
        with self.database.transaction() as connection:
            return self._read(connection, study_id)

    def list(self, *, status: str | None = "active") -> list[dict[str, Any]]:
        query, params = "SELECT study_id FROM kiva_study", []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY name"
        with self.database.transaction() as connection:
            return [self._read(connection, row["study_id"]) for row in connection.execute(query, params)]

    def update(self, study_id: str, *, name: str | None = None, definition: dict[str, Any] | None = None,
               status: str | None = None, actor_person_id: str | None = None) -> dict[str, Any]:
        if status and status not in {"draft", "active", "closed"}:
            raise ValidationError("Invalid study status")
        with self.database.transaction() as connection:
            before = self._read(connection, study_id)
            if name is not None:
                connection.execute("UPDATE kiva_study SET name = ?, updated_at = ? WHERE study_id = ?", (name, _now(), study_id))
            if definition is not None:
                connection.execute("""UPDATE kiva_study SET definition_json = ?, definition_version = definition_version + 1,
                                      updated_at = ? WHERE study_id = ?""", (_json(definition), _now(), study_id))
            if status is not None:
                connection.execute("UPDATE kiva_study SET status = ?, updated_at = ? WHERE study_id = ?", (status, _now(), study_id))
            after = self._read(connection, study_id)
            self._audit(connection, "study.update", "study", study_id, actor_person_id, before, after)
            return after

    def save_application(self, application_key: str, name: str, *, status: str = "active") -> dict[str, Any]:
        if status not in {"active", "inactive"}:
            raise ValidationError("Invalid application status")
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM kiva_application WHERE application_key = ?", (application_key,)).fetchone()
            if row:
                connection.execute("UPDATE kiva_application SET name = ?, status = ? WHERE application_key = ?", (name, status, application_key))
            else:
                connection.execute("INSERT INTO kiva_application (application_id, application_key, name, status) VALUES (?, ?, ?, ?)",
                                   (_id(), application_key, name, status))
            return _decode(connection.execute("SELECT * FROM kiva_application WHERE application_key = ?", (application_key,)).fetchone())

    def list_applications(self, *, status: str | None = None) -> list[dict[str, Any]]:
        query, params = "SELECT * FROM kiva_application", []
        if status is not None:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY name, application_key"
        with self.database.transaction() as connection:
            return [_decode(row) for row in connection.execute(query, params)]

    def set_study_application(self, study_id: str, application_key: str, *, config: dict[str, Any] | None = None,
                              enabled: bool = True, actor_person_id: str | None = None) -> dict[str, Any]:
        with self.database.transaction() as connection:
            self._require(connection, "kiva_study", "study_id", study_id)
            app = connection.execute("SELECT * FROM kiva_application WHERE application_key = ?", (application_key,)).fetchone()
            if app is None:
                raise NotFoundError(f"Application {application_key} was not found")
            connection.execute(
                """INSERT INTO kiva_study_application (study_id, application_id, config_json, enabled) VALUES (?, ?, ?, ?)
                   ON CONFLICT(study_id, application_id) DO UPDATE SET config_json = excluded.config_json, enabled = excluded.enabled""",
                (study_id, app["application_id"], _json(config or {}), int(enabled)),
            )
            result = dict(connection.execute("""SELECT sa.*, a.application_key, a.name FROM kiva_study_application sa
                                                JOIN kiva_application a ON a.application_id = sa.application_id
                                                WHERE sa.study_id = ? AND sa.application_id = ?""", (study_id, app["application_id"])).fetchone())
            self._audit(connection, "study_application.set", "study_application", f"{study_id}:{app['application_id']}", actor_person_id, after=result)
            return result

    def replace_materials(self, study_id: str, materials: list[dict[str, Any]], *, actor_person_id: str | None = None) -> list[dict[str, Any]]:
        with self.database.transaction() as connection:
            self._require(connection, "kiva_study", "study_id", study_id)
            before = [_decode(row) for row in connection.execute("SELECT * FROM kiva_study_material WHERE study_id = ?", (study_id,))]
            connection.execute("DELETE FROM kiva_study_material WHERE study_id = ?", (study_id,))
            result = []
            for material in materials:
                app_id = None
                if application_key := material.get("application_key"):
                    app = connection.execute("SELECT application_id FROM kiva_application WHERE application_key = ?", (application_key,)).fetchone()
                    if app is None:
                        raise NotFoundError(f"Application {application_key} was not found")
                    app_id = app["application_id"]
                material_id = material.get("material_id", _id())
                payload = material.get("material", material.get("material_json", {}))
                connection.execute("INSERT INTO kiva_study_material (material_id, study_id, application_id, material_json) VALUES (?, ?, ?, ?)",
                                   (material_id, study_id, app_id, _json(payload)))
                result.append(_decode(connection.execute("SELECT * FROM kiva_study_material WHERE material_id = ?", (material_id,)).fetchone()))
            self._audit(connection, "study_material.replace", "study", study_id, actor_person_id, before, result)
            return result

    def _read(self, connection: sqlite3.Connection, study_id: str) -> dict[str, Any]:
        study = self._require(connection, "kiva_study", "study_id", study_id)
        study["definition"] = json.loads(study.pop("definition_json"))
        study["applications"] = [dict(row) for row in connection.execute("""SELECT a.application_key, a.name, sa.config_json, sa.enabled
            FROM kiva_study_application sa JOIN kiva_application a ON a.application_id = sa.application_id WHERE sa.study_id = ? ORDER BY a.name""", (study_id,))]
        study["materials"] = [dict(row) for row in connection.execute("SELECT * FROM kiva_study_material WHERE study_id = ?", (study_id,))]
        return study


class SessionRepository(Repository):
    def create(self, *, study_id: str, application_key: str, subject_person_id: str, actor_account_id: str,
               config_snapshot: dict[str, Any], metadata: dict[str, Any] | None = None,
               session_id: str | None = None) -> dict[str, Any]:
        session_id = session_id or _id()
        with self.database.transaction() as connection:
            account = self._require(connection, "kiva_account", "account_id", actor_account_id)
            self._require(connection, "kiva_person", "person_id", subject_person_id)
            app = connection.execute("SELECT application_id FROM kiva_application WHERE application_key = ?", (application_key,)).fetchone()
            if app is None:
                raise NotFoundError(f"Application {application_key} was not found")
            pair = connection.execute("SELECT enabled FROM kiva_study_application WHERE study_id = ? AND application_id = ?", (study_id, app["application_id"])).fetchone()
            if pair is None or not pair["enabled"]:
                raise ValidationError("Application is not enabled for this study")
            connection.execute(
                """INSERT INTO kiva_session
                   (session_id, study_id, application_id, subject_person_id, actor_account_id, actor_person_id, config_snapshot_json, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, study_id, app["application_id"], subject_person_id, actor_account_id, account["person_id"],
                 _json(config_snapshot), _json(metadata or {})),
            )
            result = self._read(connection, session_id)
            self._audit(connection, "session.create", "session", session_id, account["person_id"], after=result)
            return result

    def update(self, session_id: str, *, status: str | None = None, data_location: str | None = None,
               metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if status and status not in {"created", "running", "completed", "abandoned", "failed"}:
            raise ValidationError("Invalid session status")
        with self.database.transaction() as connection:
            before = self._read(connection, session_id)
            if status and status != before["status"]:
                allowed = {
                    "created": {"running", "abandoned", "failed"},
                    "running": {"completed", "abandoned", "failed"},
                    "completed": set(),
                    "abandoned": set(),
                    "failed": set(),
                }
                if status not in allowed[before["status"]]:
                    raise ValidationError(
                        f"Invalid session transition: {before['status']} -> {status}"
                    )
            fields, values = [], []
            if status and status != before["status"]:
                fields.append("status = ?"); values.append(status)
                if status == "running": fields.append("started_at = COALESCE(started_at, ?)"); values.append(_now())
                if status in {"completed", "abandoned", "failed"}:
                    fields.append("ended_at = COALESCE(ended_at, ?)"); values.append(_now())
            if data_location is not None: fields.append("data_location = ?"); values.append(data_location)
            if metadata is not None: fields.append("metadata_json = ?"); values.append(_json(metadata))
            if fields:
                connection.execute(f"UPDATE kiva_session SET {', '.join(fields)} WHERE session_id = ?", [*values, session_id])
            after = self._read(connection, session_id)
            self._audit(connection, "session.update", "session", session_id, after["actor_person_id"], before, after)
            return after

    def delete(self, session_id: str) -> dict[str, Any]:
        """Hard-delete a session row (no dependent FK rows reference kiva_session). Returns the
        record as it was, so the caller can clean up the matching on-disk artifacts."""
        with self.database.transaction() as connection:
            before = self._read(connection, session_id)
            connection.execute("DELETE FROM kiva_session WHERE session_id = ?", (session_id,))
            self._audit(connection, "session.delete", "session", session_id, before["actor_person_id"], before, None)
            return before

    def get(self, session_id: str) -> dict[str, Any]:
        with self.database.transaction() as connection:
            return self._read(connection, session_id)

    def list(self, *, subject_person_id: str | None = None, actor_person_id: str | None = None,
             study_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        clauses, params = ["1=1"], []
        for column, value in (("subject_person_id", subject_person_id), ("actor_person_id", actor_person_id), ("study_id", study_id), ("status", status)):
            if value is not None: clauses.append(f"{column} = ?"); params.append(value)
        with self.database.transaction() as connection:
            rows = connection.execute(f"SELECT session_id FROM kiva_session WHERE {' AND '.join(clauses)} ORDER BY created_at DESC", params)
            return [self._read(connection, row["session_id"]) for row in rows]

    def _read(self, connection: sqlite3.Connection, session_id: str) -> dict[str, Any]:
        row = self._require(connection, "kiva_session", "session_id", session_id)
        row["config_snapshot"] = json.loads(row.pop("config_snapshot_json"))
        row["metadata"] = json.loads(row.pop("metadata_json"))
        row["application_key"] = connection.execute("SELECT application_key FROM kiva_application WHERE application_id = ?", (row["application_id"],)).fetchone()[0]
        return row


def _display_name(connection: sqlite3.Connection, person_id: str | None) -> str | None:
    if not person_id:
        return None
    row = connection.execute(
        "SELECT value_json FROM kiva_person_profile_value WHERE person_id = ? AND field_key = 'display_name'",
        (person_id,),
    ).fetchone()
    return json.loads(row["value_json"]) if row else None


class ProblemRepository(Repository):
    """Version-aware problem reports + their event thread. State-machine guard lives here
    (read-current → validate → update + event, all in one transaction)."""

    SEVERITIES = {"blocker", "major", "normal", "minor"}
    ENVS = {"local", "sandbox", "prod"}
    OPEN_STATUSES = {"open", "reopened"}
    CLOSED_STATUSES = {"closed", "closed_wontfix", "closed_duplicate", "closed_notabug"}

    def report(self, *, reporter_person_id: str, title: str, description: str = "",
               severity: str = "normal", area: str | None = None, session_id: str | None = None,
               reported_version: str, reported_env: str, client_info: str | None = None,
               related_problem_id: str | None = None) -> dict[str, Any]:
        if not (title or "").strip():
            raise ValidationError("A problem title is required")
        if severity not in self.SEVERITIES:
            raise ValidationError(f"Invalid severity: {severity}")
        if reported_env not in self.ENVS:
            raise ValidationError(f"Invalid env: {reported_env}")
        problem_id = _id()
        with self.database.transaction() as connection:
            self._require(connection, "kiva_person", "person_id", reporter_person_id)
            connection.execute(
                """INSERT INTO kiva_problem
                   (problem_id, reporter_person_id, title, description, severity, area, session_id,
                    reported_version, reported_env, client_info, related_problem_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (problem_id, reporter_person_id, title.strip(), description or "", severity, area, session_id,
                 reported_version, reported_env, client_info, related_problem_id),
            )
            self._event(connection, problem_id, reporter_person_id, "reported",
                        to_status="open", version=reported_version)
            self._audit(connection, "problem.report", "problem", problem_id, reporter_person_id,
                        after={"title": title.strip(), "severity": severity, "version": reported_version})
            return self._read(connection, problem_id)

    def get(self, problem_id: str) -> dict[str, Any]:
        with self.database.transaction() as connection:
            return self._read(connection, problem_id)

    def list(self, *, status: str | None = None, reported_version: str | None = None,
             reported_env: str | None = None, area: str | None = None,
             reporter_person_id: str | None = None) -> list[dict[str, Any]]:
        clauses, params = ["1=1"], []
        if status == "open":
            clauses.append("status IN ('open','reopened')")
        elif status == "closed":
            clauses.append("status IN ('closed','closed_wontfix','closed_duplicate','closed_notabug')")
        elif status:
            clauses.append("status = ?"); params.append(status)
        for column, value in (("reported_version", reported_version), ("reported_env", reported_env),
                              ("area", area), ("reporter_person_id", reporter_person_id)):
            if value:
                clauses.append(f"{column} = ?"); params.append(value)
        with self.database.transaction() as connection:
            rows = connection.execute(
                f"SELECT problem_id FROM kiva_problem WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC", params)
            return [self._read(connection, row["problem_id"], with_events=False) for row in rows]

    def apply(self, problem_id: str, *, actor_person_id: str, event_type: str,
              to_status: str | None = None, expect_status: Iterable[str] | None = None,
              version: str | None = None, note: str | None = None,
              set_fields: dict[str, Any] | None = None) -> dict[str, Any]:
        """Atomic, idempotent transition: validate current status, update fields, write the event."""
        with self.database.transaction() as connection:
            before = self._require(connection, "kiva_problem", "problem_id", problem_id)
            if expect_status is not None and before["status"] not in set(expect_status):
                raise ConflictError(
                    f"Problem is '{before['status']}'; this action needs one of {sorted(set(expect_status))}")
            fields, values = [], []
            if to_status is not None and to_status != before["status"]:
                fields.append("status = ?"); values.append(to_status)
            for key, val in (set_fields or {}).items():
                fields.append(f"{key} = ?"); values.append(val)
            fields.append("updated_at = ?"); values.append(_now())
            connection.execute(f"UPDATE kiva_problem SET {', '.join(fields)} WHERE problem_id = ?",
                               [*values, problem_id])
            self._event(connection, problem_id, actor_person_id, event_type,
                        from_status=before["status"], to_status=to_status or before["status"],
                        version=version, note=note)
            return self._read(connection, problem_id)

    def comment(self, problem_id: str, *, actor_person_id: str, note: str) -> dict[str, Any]:
        if not (note or "").strip():
            raise ValidationError("A comment cannot be empty")
        with self.database.transaction() as connection:
            self._require(connection, "kiva_problem", "problem_id", problem_id)
            self._event(connection, problem_id, actor_person_id, "commented", note=note.strip())
            return self._read(connection, problem_id)

    @staticmethod
    def _event(connection: sqlite3.Connection, problem_id: str, actor_person_id: str, event_type: str, *,
               from_status: str | None = None, to_status: str | None = None,
               version: str | None = None, note: str | None = None) -> None:
        connection.execute(
            """INSERT INTO kiva_problem_event
               (event_id, problem_id, actor_person_id, event_type, from_status, to_status, version, note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (_id(), problem_id, actor_person_id, event_type, from_status, to_status, version, note, _now()),
        )

    def _read(self, connection: sqlite3.Connection, problem_id: str, *, with_events: bool = True) -> dict[str, Any]:
        problem = self._require(connection, "kiva_problem", "problem_id", problem_id)
        problem["reporter_name"] = _display_name(connection, problem["reporter_person_id"])
        problem["assignee_name"] = _display_name(connection, problem["assignee_person_id"])
        if with_events:
            events = []
            for row in connection.execute(
                "SELECT * FROM kiva_problem_event WHERE problem_id = ? ORDER BY created_at", (problem_id,)):
                event = dict(row)
                event["actor_name"] = _display_name(connection, event["actor_person_id"])
                events.append(event)
            problem["events"] = events
        return problem


class DropRepository(Repository):
    """Known releases per environment — records what version is deployed where."""

    def register(self, version: str, env: str, notes: str | None = None) -> dict[str, Any]:
        if env not in {"local", "sandbox", "prod"}:
            raise ValidationError(f"Invalid env: {env}")
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO kiva_drop (version, env, notes) VALUES (?, ?, ?)
                   ON CONFLICT(version, env) DO UPDATE SET notes = COALESCE(excluded.notes, kiva_drop.notes)""",
                (version, env, notes),
            )
            return dict(connection.execute(
                "SELECT * FROM kiva_drop WHERE version = ? AND env = ?", (version, env)).fetchone())

    def list(self, *, env: str | None = None) -> list[dict[str, Any]]:
        query, params = "SELECT * FROM kiva_drop", []
        if env:
            query += " WHERE env = ?"; params.append(env)
        query += " ORDER BY deployed_at DESC"
        with self.database.transaction() as connection:
            return [dict(row) for row in connection.execute(query, params)]

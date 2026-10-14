from __future__ import annotations

from typing import Any, Iterable

from .database import KivaDatabase
from .errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from .repositories import DropRepository, PeopleRepository, ProblemRepository, SessionRepository, StudyRepository


class EnrollmentService:
    """Study membership and global guardian/learner links."""

    def __init__(self, database: KivaDatabase):
        self.database = database
        self.people = PeopleRepository(database)

    def set_enrollment(self, person_id: str, study_id: str, *, status: str = "active",
                       actor_person_id: str | None = None) -> dict[str, Any]:
        if status not in {"active", "inactive", "withdrawn"}:
            raise ValidationError("Invalid enrollment status")
        with self.database.transaction() as connection:
            self.people._require(connection, "kiva_person", "person_id", person_id)
            self.people._require(connection, "kiva_study", "study_id", study_id)
            connection.execute("""INSERT INTO kiva_study_enrollment (enrollment_id, person_id, study_id, status)
                VALUES (lower(hex(randomblob(16))), ?, ?, ?)
                ON CONFLICT(person_id, study_id) DO UPDATE SET status = excluded.status""", (person_id, study_id, status))
            row = dict(connection.execute("SELECT * FROM kiva_study_enrollment WHERE person_id = ? AND study_id = ?", (person_id, study_id)).fetchone())
            self.people._audit(connection, "enrollment.set", "study_enrollment", row["enrollment_id"], actor_person_id, after=row)
            return row

    def list_enrollments(self, *, study_id: str | None = None, person_id: str | None = None,
                         role: str | None = None, status: str = "active") -> list[dict[str, Any]]:
        clauses, params, joins = ["se.status = ?"], [status], []
        if study_id: clauses.append("se.study_id = ?"); params.append(study_id)
        if person_id: clauses.append("se.person_id = ?"); params.append(person_id)
        if role: joins.append("JOIN kiva_person_role pr ON pr.person_id = se.person_id"); clauses.append("pr.role_code = ?"); params.append(role)
        with self.database.transaction() as connection:
            return [dict(row) for row in connection.execute(f"SELECT DISTINCT se.* FROM kiva_study_enrollment se {' '.join(joins)} WHERE {' AND '.join(clauses)}", params)]

    def set_guardian_link(self, guardian_person_id: str, learner_person_id: str, *, status: str = "active",
                          actor_person_id: str | None = None) -> dict[str, Any]:
        if guardian_person_id == learner_person_id:
            raise ValidationError("A person cannot be their own guardian")
        with self.database.transaction() as connection:
            guardian = self.people._read(connection, guardian_person_id)
            learner = self.people._read(connection, learner_person_id)
            if "guardian" not in guardian["roles"] or "learner" not in learner["roles"]:
                raise ValidationError("Guardian and learner roles are required before linking")
            connection.execute("""INSERT INTO kiva_guardian_learner (guardian_person_id, learner_person_id, status)
                VALUES (?, ?, ?) ON CONFLICT(guardian_person_id, learner_person_id) DO UPDATE SET status = excluded.status""",
                (guardian_person_id, learner_person_id, status))
            row = dict(connection.execute("SELECT * FROM kiva_guardian_learner WHERE guardian_person_id = ? AND learner_person_id = ?", (guardian_person_id, learner_person_id)).fetchone())
            self.people._audit(connection, "guardian_link.set", "guardian_learner", f"{guardian_person_id}:{learner_person_id}", actor_person_id, after=row)
            return row

    def guardians_for(self, learner_person_id: str) -> list[dict[str, Any]]:
        with self.database.transaction() as connection:
            rows = connection.execute("SELECT guardian_person_id FROM kiva_guardian_learner WHERE learner_person_id = ? AND status = 'active'", (learner_person_id,))
            return [self.people._read(connection, row["guardian_person_id"]) for row in rows]

    def learners_for(self, guardian_person_id: str) -> list[dict[str, Any]]:
        with self.database.transaction() as connection:
            rows = connection.execute("SELECT learner_person_id FROM kiva_guardian_learner WHERE guardian_person_id = ? AND status = 'active'", (guardian_person_id,))
            return [self.people._read(connection, row["learner_person_id"]) for row in rows]


class AccessService:
    """Resolves subject, study, application, and intake access from the agreed rules."""

    def __init__(self, database: KivaDatabase):
        self.database = database
        self.people = PeopleRepository(database)
        self.studies = StudyRepository(database)

    def intake(self, person_id: str, study_id: str, roles: Iterable[str]) -> dict[str, list[dict[str, Any]]]:
        study = self.studies.get(study_id)
        requested = [field for role in roles for field in study["definition"].get("intake", {}).get(role, [])]
        fields = {field["field_key"]: field for field in requested}
        values = self.people.profile_slice(person_id, fields)
        missing = [field for key, field in fields.items() if field.get("required") and key not in values]
        return {"required_missing": missing, "optional": [f for f in fields.values() if not f.get("required")], "values": values}

    def available_subjects(self, actor_person_id: str) -> list[dict[str, Any]]:
        with self.database.transaction() as connection:
            actor = self.people._read(connection, actor_person_id)
            if actor["status"] != "active":
                raise AuthorizationError("Inactive people cannot start or supervise sessions")
            subject_ids = set()
            if "learner" in actor["roles"]:
                subject_ids.add(actor_person_id)
            subject_ids.update(row["learner_person_id"] for row in connection.execute(
                "SELECT learner_person_id FROM kiva_guardian_learner WHERE guardian_person_id = ? AND status = 'active'", (actor_person_id,)))
            if "instructor" in actor["roles"]:
                subject_ids.update(row["person_id"] for row in connection.execute("""SELECT DISTINCT learner_enrollment.person_id
                    FROM kiva_study_enrollment instructor_enrollment
                    JOIN kiva_study_enrollment learner_enrollment ON learner_enrollment.study_id = instructor_enrollment.study_id
                    JOIN kiva_person_role learner_role ON learner_role.person_id = learner_enrollment.person_id
                    WHERE instructor_enrollment.person_id = ? AND instructor_enrollment.status = 'active'
                    AND learner_enrollment.status = 'active' AND learner_role.role_code = 'learner'""", (actor_person_id,)))
            return [person for person_id in sorted(subject_ids)
                    if (person := self.people._read(connection, person_id))["status"] == "active"]

    def available_studies(self, actor_person_id: str, subject_person_id: str) -> list[dict[str, Any]]:
        self._assert_subject_access(actor_person_id, subject_person_id)
        with self.database.transaction() as connection:
            rows = connection.execute("""SELECT s.study_id FROM kiva_study s JOIN kiva_study_enrollment se ON se.study_id = s.study_id
                WHERE se.person_id = ? AND se.status = 'active' AND s.status = 'active' ORDER BY s.name""", (subject_person_id,))
            return [self.studies._read(connection, row["study_id"]) for row in rows]

    def available_applications(self, actor_person_id: str, subject_person_id: str, study_id: str) -> list[dict[str, Any]]:
        if study_id not in {study["study_id"] for study in self.available_studies(actor_person_id, subject_person_id)}:
            raise AuthorizationError("Actor cannot access this subject in the requested study")
        study = self.studies.get(study_id)
        return [app for app in study["applications"] if app["enabled"]]

    def assert_launch(self, actor_person_id: str, subject_person_id: str, study_id: str, application_key: str) -> None:
        apps = self.available_applications(actor_person_id, subject_person_id, study_id)
        if application_key not in {app["application_key"] for app in apps}:
            raise AuthorizationError("Application is not available in this launch context")

    def _assert_subject_access(self, actor_person_id: str, subject_person_id: str) -> None:
        if subject_person_id not in {person["person_id"] for person in self.available_subjects(actor_person_id)}:
            raise AuthorizationError("Actor cannot select this subject")


class OnboardingService:
    """Atomic learner onboarding: person, enrollment, required intake, and guardians."""

    def __init__(self, database: KivaDatabase):
        self.database = database
        self.people = PeopleRepository(database)
        self.enrollments = EnrollmentService(database)
        self.access = AccessService(database)

    def onboard_learner(self, study_id: str, *, learner_person_id: str | None = None,
                        profile_patch: dict[str, Any] | None = None, guardian_person_ids: Iterable[str] = (),
                        actor_person_id: str | None = None) -> dict[str, Any]:
        # This workflow deliberately uses one transaction: learner creation/update,
        # enrollment, and guardian assignment either all succeed or all roll back.
        with self.database.transaction() as connection:
            self.people._require(connection, "kiva_study", "study_id", study_id)
            if learner_person_id is None:
                from .repositories import _id
                learner_person_id = _id()
                connection.execute("INSERT INTO kiva_person (person_id) VALUES (?)", (learner_person_id,))
                connection.execute("INSERT INTO kiva_person_role (person_id, role_code) VALUES (?, 'learner')", (learner_person_id,))
                action = "person.create"
            else:
                self.people._require(connection, "kiva_person", "person_id", learner_person_id)
                connection.execute("INSERT OR IGNORE INTO kiva_person_role (person_id, role_code) VALUES (?, 'learner')", (learner_person_id,))
                action = "person.update"
            for field_key, value in (profile_patch or {}).items():
                self.people._write_profile(connection, learner_person_id, field_key, value)
            connection.execute("""INSERT INTO kiva_study_enrollment (enrollment_id, person_id, study_id, status)
                VALUES (lower(hex(randomblob(16))), ?, ?, 'active')
                ON CONFLICT(person_id, study_id) DO UPDATE SET status = 'active'""", (learner_person_id, study_id))
            for guardian_person_id in guardian_person_ids:
                guardian = self.people._read(connection, guardian_person_id)
                if "guardian" not in guardian["roles"]:
                    raise ValidationError("Guardian role is required before assignment")
                connection.execute("""INSERT INTO kiva_guardian_learner (guardian_person_id, learner_person_id, status)
                    VALUES (?, ?, 'active') ON CONFLICT(guardian_person_id, learner_person_id) DO UPDATE SET status = 'active'""",
                    (guardian_person_id, learner_person_id))
            learner = self.people._read(connection, learner_person_id)
            enrollment = dict(connection.execute("SELECT * FROM kiva_study_enrollment WHERE person_id = ? AND study_id = ?", (learner_person_id, study_id)).fetchone())
            self.people._audit(connection, action, "person", learner_person_id, actor_person_id, after=learner)
            self.people._audit(connection, "enrollment.set", "study_enrollment", enrollment["enrollment_id"], actor_person_id, after=enrollment)
        return {"learner": self.people.get(learner_person_id), "enrollment": enrollment,
                "intake": self.access.intake(learner_person_id, study_id, roles=["learner"])}


class SessionService:
    def __init__(self, database: KivaDatabase):
        self.database = database
        self.people = PeopleRepository(database)
        self.access = AccessService(database)
        self.sessions = SessionRepository(database)

    def create(self, *, actor_account_id: str, subject_person_id: str, study_id: str, application_key: str,
               config_snapshot: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.database.transaction() as connection:
            account = self.people._require(connection, "kiva_account", "account_id", actor_account_id)
            if account["status"] != "active":
                raise AuthorizationError("Inactive accounts cannot create sessions")
        self.access.assert_launch(account["person_id"], subject_person_id, study_id, application_key)
        return self.sessions.create(study_id=study_id, application_key=application_key, subject_person_id=subject_person_id,
                                    actor_account_id=actor_account_id, config_snapshot=config_snapshot, metadata=metadata)

    def update(self, actor_account_id: str, session_id: str, *, status: str) -> dict[str, Any]:
        """Update lifecycle only for the account that created the session."""
        with self.database.transaction() as connection:
            account = self.people._require(connection, "kiva_account", "account_id", actor_account_id)
        if account["status"] != "active":
            raise AuthorizationError("Inactive accounts cannot update sessions")
        session = self.sessions.get(session_id)
        if session["actor_account_id"] != actor_account_id:
            raise AuthorizationError("Only the session's supervising account can update it")
        return self.sessions.update(
            session_id,
            status=status,
            data_location=f"sessions/{session_id}" if status in {"completed", "abandoned", "failed"} else None,
        )

    def mark_disconnected(self, session_id: str) -> dict[str, Any]:
        """Finalize a runtime session as abandoned on transport disconnect.

        This is an internal server lifecycle hook, not a user-facing update path.
        Terminal states remain immutable so a late disconnect cannot downgrade a
        completed lesson.
        """
        session = self.sessions.get(session_id)
        if session["status"] not in {"created", "running"}:
            return session
        return self.sessions.update(
            session_id,
            status="abandoned",
            data_location=f"sessions/{session_id}",
        )

    def mark_running(self, session_id: str) -> dict[str, Any]:
        """Internal runtime hook: the session's client connected — mark it running (sets started_at)."""
        session = self.sessions.get(session_id)
        if session["status"] != "created":
            return session
        return self.sessions.update(session_id, status="running")

    def finalize(self, session_id: str, *, completed: bool) -> dict[str, Any]:
        """Internal runtime hook: client disconnected — mark the session terminal. ``completed`` when the
        flow reached a terminal node, else abandoned. Terminal states are preserved (idempotent)."""
        session = self.sessions.get(session_id)
        if session["status"] not in {"created", "running"}:
            return session
        if completed:
            if session["status"] == "created":
                self.sessions.update(session_id, status="running")
            return self.sessions.update(session_id, status="completed", data_location=f"sessions/{session_id}")
        return self.sessions.update(session_id, status="abandoned", data_location=f"sessions/{session_id}")


class ProblemService:
    """Problem tracker: report, the state machine (report → fixed → re-test → close/reopen),
    the per-problem Q&A thread, and the re-test queue. Role gating is enforced one layer up
    (the backend facade); this layer owns the transitions + invariants."""

    def __init__(self, database: KivaDatabase):
        self.database = database
        self.problems = ProblemRepository(database)
        self.drops = DropRepository(database)

    def report(self, *, reporter_person_id: str, title: str, description: str = "",
               severity: str = "normal", area: str | None = None, session_id: str | None = None,
               reported_version: str, reported_env: str, client_info: str | None = None) -> dict[str, Any]:
        return self.problems.report(
            reporter_person_id=reporter_person_id, title=title, description=description,
            severity=severity, area=area, session_id=session_id, reported_version=reported_version,
            reported_env=reported_env, client_info=client_info)

    def get(self, problem_id: str) -> dict[str, Any]:
        return self.problems.get(problem_id)

    def list(self, **filters: Any) -> list[dict[str, Any]]:
        return self.problems.list(**filters)

    def assign(self, problem_id: str, *, actor_person_id: str, assignee_person_id: str) -> dict[str, Any]:
        return self.problems.apply(problem_id, actor_person_id=actor_person_id, event_type="assigned",
                                   expect_status=self.problems.OPEN_STATUSES,
                                   set_fields={"assignee_person_id": assignee_person_id})

    def mark_fixed(self, problem_id: str, *, actor_person_id: str, version: str,
                   note: str | None = None) -> dict[str, Any]:
        if not (version or "").strip():
            raise ValidationError("A fix version (drop) is required")
        return self.problems.apply(problem_id, actor_person_id=actor_person_id, event_type="marked_fixed",
                                   expect_status=self.problems.OPEN_STATUSES, to_status="fixed_pending_retest",
                                   version=version.strip(), note=note,
                                   set_fields={"fixed_in_version": version.strip()})

    def close(self, problem_id: str, *, actor_person_id: str, reason: str,
              related_problem_id: str | None = None, note: str | None = None) -> dict[str, Any]:
        reasons = {"wontfix": "closed_wontfix", "duplicate": "closed_duplicate", "notabug": "closed_notabug"}
        if reason not in reasons:
            raise ValidationError(f"Invalid close reason: {reason}")
        set_fields = {"related_problem_id": related_problem_id} if related_problem_id else None
        return self.problems.apply(problem_id, actor_person_id=actor_person_id, event_type="closed",
                                   expect_status=self.problems.OPEN_STATUSES | {"fixed_pending_retest"},
                                   to_status=reasons[reason], note=note, set_fields=set_fields)

    def retest(self, problem_id: str, *, actor_person_id: str, result: str, version: str,
               note: str | None = None) -> dict[str, Any]:
        problem = self.problems.get(problem_id)
        if problem["reporter_person_id"] != actor_person_id:
            raise AuthorizationError("Only the reporter can re-test this problem")
        if problem["status"] != "fixed_pending_retest":
            raise ConflictError(f"Problem is '{problem['status']}', not awaiting re-test")
        if result == "confirmed":
            return {"problem": self.problems.apply(problem_id, actor_person_id=actor_person_id,
                    event_type="confirmed_fixed", expect_status={"fixed_pending_retest"},
                    to_status="closed", version=version, note=note)}
        if result == "still_broken":
            return {"problem": self.problems.apply(problem_id, actor_person_id=actor_person_id,
                    event_type="still_broken", expect_status={"fixed_pending_retest"},
                    to_status="reopened", version=version, note=note)}
        if result == "new":
            closed = self.problems.apply(problem_id, actor_person_id=actor_person_id,
                    event_type="confirmed_fixed", expect_status={"fixed_pending_retest"}, to_status="closed",
                    version=version, note="Original fix verified; behaves differently now — see linked regression")
            created = self.problems.report(reporter_person_id=actor_person_id,
                    title=(note or f"Regression after: {problem['title']}")[:200], description=note or "",
                    severity=problem["severity"], area=problem["area"], session_id=problem["session_id"],
                    reported_version=version, reported_env=problem["reported_env"],
                    related_problem_id=problem_id)
            return {"problem": closed, "new_problem": created}
        raise ValidationError(f"Invalid re-test result: {result}")

    def comment(self, problem_id: str, *, actor_person_id: str, note: str) -> dict[str, Any]:
        return self.problems.comment(problem_id, actor_person_id=actor_person_id, note=note)

    def retests_for(self, person_id: str) -> list[dict[str, Any]]:
        return self.problems.list(status="fixed_pending_retest", reporter_person_id=person_id)

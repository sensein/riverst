"""Backend-facing KIVA operations built on the repository/service layer."""
from __future__ import annotations

from typing import Any, Iterable

from .database import KivaDatabase
from .errors import AuthorizationError, ConflictError
from .repositories import DropRepository, PeopleRepository, StudyRepository
from .services import AccessService, EnrollmentService, OnboardingService, ProblemService, SessionService


class KivaBackend:
    """Small authenticated operation surface for a future FastAPI router."""

    def __init__(self, database: KivaDatabase):
        self.database = database
        self.people = PeopleRepository(database)
        self.studies = StudyRepository(database)
        self.enrollments = EnrollmentService(database)
        self.access = AccessService(database)
        self.onboarding = OnboardingService(database)
        self.sessions = SessionService(database)
        self.problems = ProblemService(database)
        self.drops = DropRepository(database)

    def login(self, auth_subject: str, email: str, name: str | None = None) -> dict[str, Any]:
        """Resolve an existing account or create an unroled person for an authorized login."""
        try:
            account = self.people.resolve_account(auth_subject=auth_subject, email=email)
        except Exception:
            person = self.people.create(profile={"display_name": name or email})
            account = self.people.link_account(person["person_id"], auth_subject, email)
        return {"account": account, "person": self.people.get(account["person_id"])}

    def ensure_instructor(self, actor_account_id: str) -> dict[str, Any]:
        """Idempotently grant the instructor role. Authorized KIVA users (authorized_emails /
        local bypass) are seeded as instructors on login — there is no self-service bootstrap."""
        actor = self._actor(actor_account_id)
        if "instructor" in actor["roles"]:
            return self.people.get(actor["person_id"])
        return self.people.update(actor["person_id"], roles={*actor["roles"], "instructor"}, actor_person_id=actor["person_id"])

    def create_study(self, actor_account_id: str, name: str, definition: dict[str, Any]) -> dict[str, Any]:
        actor = self._require_instructor(actor_account_id)
        study = self.studies.create(name, definition, status="draft", actor_person_id=actor["person_id"])
        self.enrollments.set_enrollment(actor["person_id"], study["study_id"], actor_person_id=actor["person_id"])
        return study

    def update_study(self, actor_account_id: str, study_id: str, **changes: Any) -> dict[str, Any]:
        actor = self._require_study_instructor(actor_account_id, study_id)
        return self.studies.update(study_id, actor_person_id=actor["person_id"], **changes)

    def set_study_application(self, actor_account_id: str, study_id: str, application_key: str,
                              config: dict[str, Any] | None = None, enabled: bool = True) -> dict[str, Any]:
        actor = self._require_study_instructor(actor_account_id, study_id)
        return self.studies.set_study_application(study_id, application_key, config=config, enabled=enabled,
                                                  actor_person_id=actor["person_id"])

    def save_application(self, actor_account_id: str, application_key: str, name: str) -> dict[str, Any]:
        self._require_instructor(actor_account_id)
        return self.studies.save_application(application_key, name)

    def list_people(self, actor_account_id: str, *, role: str | None = None,
                    status: str | None = "active") -> list[dict[str, Any]]:
        self._require_instructor(actor_account_id)
        return self.people.find(role=role, status=status)

    def update_person(self, actor_account_id: str, person_id: str, *,
                      profile_patch: dict[str, Any] | None = None,
                      roles: Iterable[str] | None = None,
                      status: str | None = None) -> dict[str, Any]:
        actor = self._require_instructor(actor_account_id)
        return self.people.update(person_id, profile_patch=profile_patch, roles=roles,
                                  status=status, actor_person_id=actor["person_id"])

    def link_guardian_learner(self, actor_account_id: str, guardian_person_id: str,
                              learner_person_id: str, *, status: str = "active") -> dict[str, Any]:
        actor = self._require_instructor(actor_account_id)
        return self.enrollments.set_guardian_link(guardian_person_id, learner_person_id,
                                                   status=status, actor_person_id=actor["person_id"])

    def list_studies(self, actor_account_id: str) -> list[dict[str, Any]]:
        actor = self._require_instructor(actor_account_id)
        enrollment_rows = self.enrollments.list_enrollments(person_id=actor["person_id"])
        return [self.studies.get(row["study_id"]) for row in enrollment_rows]

    def list_applications(self, actor_account_id: str, *,
                          status: str | None = None) -> list[dict[str, Any]]:
        self._require_instructor(actor_account_id)
        return self.studies.list_applications(status=status)

    def update_application(self, actor_account_id: str, application_key: str, *,
                           name: str, status: str = "active") -> dict[str, Any]:
        self._require_instructor(actor_account_id)
        return self.studies.save_application(application_key, name, status=status)

    def create_person(self, actor_account_id: str, *, roles: Iterable[str], profile: dict[str, Any]) -> dict[str, Any]:
        """Create a guardian or learner through an instructor-led onboarding flow."""
        actor = self._require_instructor(actor_account_id)
        return self.people.create(roles=roles, profile=profile, actor_person_id=actor["person_id"])

    def onboard_learner(self, actor_account_id: str, study_id: str, *, learner_person_id: str | None = None,
                        profile_patch: dict[str, Any] | None = None, guardian_person_ids: Iterable[str] = ()) -> dict[str, Any]:
        actor = self._require_study_instructor(actor_account_id, study_id)
        return self.onboarding.onboard_learner(study_id, learner_person_id=learner_person_id,
                                               profile_patch=profile_patch, guardian_person_ids=guardian_person_ids,
                                               actor_person_id=actor["person_id"])

    def launch_menu(self, actor_account_id: str) -> dict[str, Any]:
        actor = self._actor(actor_account_id)
        subjects = self.access.available_subjects(actor["person_id"])
        return {"actor": actor, "subjects": [{
            "person": subject,
            "studies": self.access.available_studies(actor["person_id"], subject["person_id"]),
        } for subject in subjects]}

    def applications_for(self, actor_account_id: str, subject_person_id: str, study_id: str) -> list[dict[str, Any]]:
        actor = self._actor(actor_account_id)
        return self.access.available_applications(actor["person_id"], subject_person_id, study_id)

    def create_session(self, actor_account_id: str, subject_person_id: str, study_id: str,
                       application_key: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        apps = self.applications_for(actor_account_id, subject_person_id, study_id)
        app = next((item for item in apps if item["application_key"] == application_key), None)
        if app is None:
            raise AuthorizationError("Application is unavailable in this launch context")
        import json
        return self.sessions.create(actor_account_id=actor_account_id, subject_person_id=subject_person_id,
                                    study_id=study_id, application_key=application_key,
                                    config_snapshot=json.loads(app["config_json"]), metadata=metadata)

    def update_session(self, actor_account_id: str, session_id: str, *, status: str) -> dict[str, Any]:
        return self.sessions.update(actor_account_id, session_id, status=status)

    def mark_disconnected_session(self, session_id: str) -> dict[str, Any]:
        """Internal transport hook: abandon unfinished sessions without downgrading terminal ones."""
        return self.sessions.mark_disconnected(session_id)

    # Problem tracker -----------------------------------------------------------------------------
    # Reporting / reading / commenting / re-testing are open to any active account; the
    # developer-only triage actions (assign / mark-fixed / close) require the `developer` role.

    def report_problem(self, actor_account_id: str, **fields: Any) -> dict[str, Any]:
        actor = self._actor(actor_account_id)
        return self.problems.report(reporter_person_id=actor["person_id"], **fields)

    def list_problems(self, actor_account_id: str, **filters: Any) -> list[dict[str, Any]]:
        self._actor(actor_account_id)
        return self.problems.list(**filters)

    def get_problem(self, actor_account_id: str, problem_id: str) -> dict[str, Any]:
        self._actor(actor_account_id)
        return self.problems.get(problem_id)

    def assign_problem(self, actor_account_id: str, problem_id: str, assignee_person_id: str) -> dict[str, Any]:
        actor = self._require_role(actor_account_id, "developer")
        return self.problems.assign(problem_id, actor_person_id=actor["person_id"], assignee_person_id=assignee_person_id)

    def mark_problem_fixed(self, actor_account_id: str, problem_id: str, version: str,
                           note: str | None = None) -> dict[str, Any]:
        actor = self._require_role(actor_account_id, "developer")
        return self.problems.mark_fixed(problem_id, actor_person_id=actor["person_id"], version=version, note=note)

    def close_problem(self, actor_account_id: str, problem_id: str, reason: str,
                      related_problem_id: str | None = None, note: str | None = None) -> dict[str, Any]:
        actor = self._require_role(actor_account_id, "developer")
        return self.problems.close(problem_id, actor_person_id=actor["person_id"], reason=reason,
                                   related_problem_id=related_problem_id, note=note)

    def retest_problem(self, actor_account_id: str, problem_id: str, result: str, version: str,
                       note: str | None = None) -> dict[str, Any]:
        actor = self._actor(actor_account_id)
        return self.problems.retest(problem_id, actor_person_id=actor["person_id"], result=result,
                                    version=version, note=note)

    def comment_problem(self, actor_account_id: str, problem_id: str, note: str) -> dict[str, Any]:
        actor = self._actor(actor_account_id)
        return self.problems.comment(problem_id, actor_person_id=actor["person_id"], note=note)

    def my_retests(self, actor_account_id: str) -> list[dict[str, Any]]:
        actor = self._actor(actor_account_id)
        return self.problems.retests_for(actor["person_id"])

    def list_drops(self, actor_account_id: str, env: str | None = None) -> list[dict[str, Any]]:
        self._actor(actor_account_id)
        return self.drops.list(env=env)

    def register_drop(self, version: str, env: str, notes: str | None = None) -> dict[str, Any]:
        """Internal: record the running build as a known drop (called at server boot)."""
        return self.drops.register(version, env, notes)

    def _actor(self, account_id: str) -> dict[str, Any]:
        with self.database.transaction() as connection:
            account = self.people._require(connection, "kiva_account", "account_id", account_id)
        if account["status"] != "active":
            raise AuthorizationError("Inactive account")
        return self.people.get(account["person_id"])

    def _require_instructor(self, account_id: str) -> dict[str, Any]:
        return self._require_role(account_id, "instructor")

    def _require_role(self, account_id: str, role: str) -> dict[str, Any]:
        actor = self._actor(account_id)
        if role not in actor["roles"]:
            raise AuthorizationError(f"{role.capitalize()} role required")
        return actor

    def _require_study_instructor(self, account_id: str, study_id: str) -> dict[str, Any]:
        actor = self._require_instructor(account_id)
        active = self.enrollments.list_enrollments(study_id=study_id, person_id=actor["person_id"])
        if not active:
            raise AuthorizationError("Active instructor enrollment in this study is required")
        return actor

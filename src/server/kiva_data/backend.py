"""Backend-facing KIVA operations built on the repository/service layer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .database import KivaDatabase
from .errors import AuthorizationError, ConflictError, ValidationError
from .repositories import DropRepository, PeopleRepository, StudyRepository
from .services import AccessService, EnrollmentService, OnboardingService, ProblemService, SessionService

# Per-activity DEFAULT config comes from the original session_config.json files. A tutor's personal
# override is stored on their person profile under "app_config.<application_key>". Effective launch
# config = the tutor's saved config if present, else the file default (one config per tutor, for all
# their studies).
_ACTIVITY_DIR = Path(__file__).resolve().parent.parent / "activities"
_APP_ACTIVITY = {"vocabulary": "vocab-tutoring", "esl": "esl-vocab-tutoring", "isl": "isl-vocab-tutoring"}
_APP_CONFIG_PREFIX = "app_config."
_DEFAULT_CONFIG_CACHE: dict[str, dict[str, Any]] = {}


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
        actor = self._actor(actor_account_id)
        apps = self.applications_for(actor_account_id, subject_person_id, study_id)
        app = next((item for item in apps if item["application_key"] == application_key), None)
        if app is None:
            raise AuthorizationError("Application is unavailable in this launch context")
        # Guard: surfaced activities without lesson content (no flow_config.json) can't run a session.
        activity = _APP_ACTIVITY.get(application_key)
        if activity and not (_ACTIVITY_DIR / activity / "flow_config.json").exists():
            raise ValidationError(f"The '{application_key}' activity has no lesson content yet.")
        # Runtime config = the launching tutor's effective config (their saved config, else the file
        # default) — one config per tutor, applied to all their studies; not the per-study snapshot.
        config_snapshot = self.effective_app_config(actor["person_id"], application_key)
        return self.sessions.create(actor_account_id=actor_account_id, subject_person_id=subject_person_id,
                                    study_id=study_id, application_key=application_key,
                                    config_snapshot=config_snapshot, metadata=metadata)

    # Per-tutor app configuration ------------------------------------------------------------------
    # Default from the activity's session_config.json; tutor override on their person profile.

    def default_app_config(self, application_key: str) -> dict[str, Any]:
        if application_key in _DEFAULT_CONFIG_CACHE:
            return dict(_DEFAULT_CONFIG_CACHE[application_key])
        activity = _APP_ACTIVITY.get(application_key)
        config: dict[str, Any] = {}
        if activity:
            try:
                schema = json.loads((_ACTIVITY_DIR / activity / "session_config.json").read_text(encoding="utf-8"))
                options = schema.get("properties", {}).get("options", {}).get("properties", {})
                config = {key: spec["default"] for key, spec in options.items()
                          if isinstance(spec, dict) and "default" in spec}
                config["name"] = activity
                config["description"] = activity
            except (OSError, ValueError, KeyError):
                config = {}
        _DEFAULT_CONFIG_CACHE[application_key] = dict(config)
        return dict(config)

    def _saved_app_config(self, person_id: str, application_key: str) -> dict[str, Any] | None:
        field = f"{_APP_CONFIG_PREFIX}{application_key}"
        value = self.people.profile_slice(person_id, [field]).get(field)
        return value if isinstance(value, dict) and value else None

    def effective_app_config(self, person_id: str, application_key: str) -> dict[str, Any]:
        return self._saved_app_config(person_id, application_key) or self.default_app_config(application_key)

    def app_config_fields(self, application_key: str) -> list[dict[str, Any]]:
        """The editable field schema (key/type/enum/default/description) from session_config.json,
        so the UI can render every original variable with the right control."""
        activity = _APP_ACTIVITY.get(application_key)
        if not activity:
            return []
        try:
            schema = json.loads((_ACTIVITY_DIR / activity / "session_config.json").read_text(encoding="utf-8"))
            options = schema.get("properties", {}).get("options", {}).get("properties", {})
        except (OSError, ValueError, KeyError):
            return []
        fields = []
        for key, spec in options.items():
            if not isinstance(spec, dict):
                continue
            items = spec.get("items") if isinstance(spec.get("items"), dict) else {}
            fields.append({"key": key, "type": spec.get("type"), "enum": spec.get("enum"),
                           "item_enum": items.get("enum"),  # allowed values for array fields (e.g. languages)
                           "default": spec.get("default"), "description": spec.get("description"),
                           "title": spec.get("title")})
        return fields

    def get_app_config(self, actor_account_id: str, application_key: str) -> dict[str, Any]:
        actor = self._require_instructor(actor_account_id)
        default = self.default_app_config(application_key)
        saved = self._saved_app_config(actor["person_id"], application_key)
        return {"application_key": application_key, "default": default,
                "config": saved or default, "customized": saved is not None,
                "fields": self.app_config_fields(application_key)}

    def set_app_config(self, actor_account_id: str, application_key: str, config: dict[str, Any]) -> dict[str, Any]:
        actor = self._require_instructor(actor_account_id)
        self.people.update(actor["person_id"], profile_patch={f"{_APP_CONFIG_PREFIX}{application_key}": config},
                           actor_person_id=actor["person_id"])
        return self.get_app_config(actor_account_id, application_key)

    def reset_app_config(self, actor_account_id: str, application_key: str) -> dict[str, Any]:
        actor = self._require_instructor(actor_account_id)
        self.people.update(actor["person_id"], profile_patch={f"{_APP_CONFIG_PREFIX}{application_key}": None},
                           actor_person_id=actor["person_id"])
        return self.get_app_config(actor_account_id, application_key)

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

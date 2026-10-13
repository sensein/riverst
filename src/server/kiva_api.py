"""Authenticated KIVA routes backed by the KIVA SQLite service layer."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from authorization.auth import get_current_user, get_roles, ROLE_RESEARCHER
from kiva_data import AuthorizationError, ConflictError, KivaBackend, KivaDatabase, NotFoundError, ValidationError
from kiva_data.errors import KivaDataError


def _version_info() -> dict[str, str]:
    """The running app's version + environment, for stamping problem reports.

    A deploy-written ``version.json`` (next to the server dir or any parent) wins; otherwise
    fall back to ``git describe`` of this checkout. ``env`` comes from ``KIVA_ENV`` (default local).
    """
    env = os.getenv("KIVA_ENV", "local").strip().lower()
    if env not in {"local", "sandbox", "prod"}:
        env = "local"
    here = Path(__file__).resolve()
    for base in (here.parent, *here.parents):
        version_file = base / "version.json"
        if version_file.exists():
            try:
                data = json.loads(version_file.read_text(encoding="utf-8"))
                return {"version": str(data.get("version", "unknown")),
                        "env": str(data.get("env", env)),
                        "commit": str(data.get("commit", "")),
                        "deployed_at": str(data.get("deployed_at", ""))}
            except (ValueError, OSError):
                break

    def _git(*args: str) -> str:
        try:
            return subprocess.run(["git", "-C", str(here.parent), *args],
                                  capture_output=True, text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "detached"
    commit = _git("rev-parse", "--short", "HEAD") or "unknown"
    dirty = "-dirty" if _git("status", "--porcelain") else ""
    return {"version": f"{branch}@{commit}{dirty}", "env": env, "commit": commit, "deployed_at": ""}


def create_kiva_router(write_runtime_session: Callable[[str, dict[str, Any]], None]) -> APIRouter:
    path = Path(os.getenv("KIVA_DB_PATH", str(Path.home() / "riverst-data" / "kiva.sqlite3")))
    database = KivaDatabase(path)
    database.initialize(Path(__file__).parent / "kiva_data" / "schema.sql")
    backend = KivaBackend(database)
    router = APIRouter(prefix="/api/kiva", tags=["kiva"])

    # Record the running build as a known drop for this environment (non-fatal).
    try:
        _info = _version_info()
        backend.register_drop(_info["version"], _info["env"])
    except Exception:  # noqa: BLE001
        pass

    def actor(user: dict[str, Any]) -> dict[str, Any]:
        logged_in = backend.login(user["sub"], user["sub"], user.get("name"))
        # Authorized KIVA users are instructors by default — local bypass, or any email in
        # authorized_users.json's authorized_emails (researchers). No self-service bootstrap.
        if user.get("bypass") or ROLE_RESEARCHER in get_roles(user.get("sub", "")):
            backend.ensure_instructor(logged_in["account"]["account_id"])
            logged_in["person"] = backend.people.get(logged_in["account"]["person_id"])
        return logged_in

    def run(operation: Callable[[], Any]) -> Any:
        try:
            return operation()
        except AuthorizationError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except NotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (ValidationError, ConflictError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except KivaDataError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/me")
    def me(current_user: dict = Depends(get_current_user)):
        return run(lambda: actor(current_user))

    @router.get("/menu")
    def menu(current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.launch_menu(logged_in["account"]["account_id"]))

    @router.post("/studies")
    def create_study(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.create_study(logged_in["account"]["account_id"], payload["name"], payload.get("definition", {})))

    @router.patch("/studies/{study_id}")
    def update_study(study_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.update_study(logged_in["account"]["account_id"], study_id, **payload))

    @router.get("/studies")
    def list_studies(current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.list_studies(logged_in["account"]["account_id"]))

    @router.delete("/studies/{study_id}")
    def close_study(study_id: str, current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.update_study(logged_in["account"]["account_id"], study_id, status="closed"))

    @router.post("/studies/{study_id}/applications")
    def study_application(study_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.set_study_application(logged_in["account"]["account_id"], study_id, payload["application_key"], payload.get("config"), payload.get("enabled", True)))

    @router.post("/applications")
    def save_application(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.save_application(logged_in["account"]["account_id"], payload["application_key"], payload["name"]))

    @router.get("/applications")
    def list_applications(status: str = "all", current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        if status not in {"active", "inactive", "all"}:
            raise HTTPException(status_code=400, detail="Invalid application status filter")
        return run(lambda: backend.list_applications(logged_in["account"]["account_id"],
                                                      status=None if status == "all" else status))

    @router.patch("/applications/{application_key}")
    def update_application(application_key: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.update_application(logged_in["account"]["account_id"], application_key,
            name=payload["name"], status=payload.get("status", "active")))

    @router.delete("/applications/{application_key}")
    def deactivate_application(application_key: str, current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        apps = run(lambda: backend.list_applications(logged_in["account"]["account_id"], status=None))
        app = next((item for item in apps if item["application_key"] == application_key), None)
        if app is None:
            raise HTTPException(status_code=404, detail="Application was not found")
        return run(lambda: backend.update_application(logged_in["account"]["account_id"], application_key,
            name=app["name"], status="inactive"))
    @router.post("/people")
    def create_person(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.create_person(
            logged_in["account"]["account_id"],
            roles=payload["roles"],
            profile=payload.get("profile", {}),
        ))

    @router.get("/people")
    def list_people(role: str | None = None, status: str = "active", current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        if status not in {"active", "inactive", "all"}:
            raise HTTPException(status_code=400, detail="Invalid person status filter")
        return run(lambda: backend.list_people(logged_in["account"]["account_id"], role=role,
                                               status=None if status == "all" else status))

    @router.patch("/people/{person_id}")
    def update_person(person_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.update_person(logged_in["account"]["account_id"], person_id,
            profile_patch=payload.get("profile_patch"), roles=payload.get("roles"), status=payload.get("status")))

    @router.delete("/people/{person_id}")
    def deactivate_person(person_id: str, current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.update_person(logged_in["account"]["account_id"], person_id, status="inactive"))

    @router.post("/guardian-links")
    def link_guardian(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.link_guardian_learner(logged_in["account"]["account_id"],
            payload["guardian_person_id"], payload["learner_person_id"], status=payload.get("status", "active")))


    @router.post("/studies/{study_id}/learners")
    def onboard(study_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.onboard_learner(logged_in["account"]["account_id"], study_id,
            learner_person_id=payload.get("learner_person_id"), profile_patch=payload.get("profile_patch"), guardian_person_ids=payload.get("guardian_person_ids", [])))

    @router.get("/subjects/{person_id}/studies/{study_id}/applications")
    def applications(person_id: str, study_id: str, current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.applications_for(logged_in["account"]["account_id"], person_id, study_id))

    @router.post("/sessions")
    def create_session(payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        session = run(lambda: backend.create_session(logged_in["account"]["account_id"], payload["subject_person_id"], payload["study_id"], payload["application_key"], payload.get("metadata")))
        config = {**session["config_snapshot"], **(session.get("metadata") or {}), "user_id": f"{session['subject_person_id']}.{session['study_id']}"}
        config["kiva_session_id"] = session["session_id"]
        write_runtime_session(session["session_id"], config)
        return session

    @router.patch("/sessions/{session_id}")
    def update_session(session_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        status = payload.get("status")
        if status not in {"running", "completed", "abandoned", "failed"}:
            raise HTTPException(status_code=400, detail="Invalid session lifecycle status")
        return run(lambda: backend.update_session(logged_in["account"]["account_id"], session_id, status=status))

    # Problem tracker ------------------------------------------------------------------------------

    @router.get("/version")
    def version(current_user: dict = Depends(get_current_user)):
        return _version_info()

    @router.get("/drops")
    def drops(env: str | None = None, current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.list_drops(logged_in["account"]["account_id"], env=env))

    @router.post("/problems")
    def report_problem(request: Request, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        info = _version_info()
        user_agent = request.headers.get("user-agent")
        return run(lambda: backend.report_problem(
            logged_in["account"]["account_id"],
            title=payload.get("title", ""), description=payload.get("description", ""),
            severity=payload.get("severity", "normal"), area=payload.get("area") or None,
            session_id=payload.get("session_id") or None,
            reported_version=info["version"], reported_env=info["env"], client_info=user_agent))

    @router.get("/problems")
    def list_problems(status: str | None = None, version: str | None = None, env: str | None = None,
                      area: str | None = None, mine: bool = False,
                      current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        reporter = logged_in["account"]["person_id"] if mine else None
        return run(lambda: backend.list_problems(
            logged_in["account"]["account_id"], status=status, reported_version=version,
            reported_env=env, area=area, reporter_person_id=reporter))

    @router.get("/retests/mine")
    def my_retests(current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.my_retests(logged_in["account"]["account_id"]))

    @router.get("/problems/{problem_id}")
    def get_problem(problem_id: str, current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.get_problem(logged_in["account"]["account_id"], problem_id))

    @router.patch("/problems/{problem_id}")
    def patch_problem(problem_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        account_id = logged_in["account"]["account_id"]
        action = payload.get("action")
        if action == "assign":
            return run(lambda: backend.assign_problem(account_id, problem_id, payload["assignee_person_id"]))
        if action == "mark_fixed":
            return run(lambda: backend.mark_problem_fixed(account_id, problem_id, payload["version"], note=payload.get("note")))
        if action == "close":
            return run(lambda: backend.close_problem(account_id, problem_id, payload["reason"],
                related_problem_id=payload.get("related_problem_id"), note=payload.get("note")))
        raise HTTPException(status_code=400, detail="Unknown problem action")

    @router.post("/problems/{problem_id}/retest")
    def retest_problem(problem_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        info = _version_info()
        return run(lambda: backend.retest_problem(logged_in["account"]["account_id"], problem_id,
            result=payload.get("result"), version=info["version"], note=payload.get("note")))

    @router.post("/problems/{problem_id}/comment")
    def comment_problem(problem_id: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.comment_problem(logged_in["account"]["account_id"], problem_id, payload.get("note", "")))

    # Per-tutor app configuration ------------------------------------------------------------------

    @router.get("/app-config/{application_key}")
    def get_app_config(application_key: str, current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        return run(lambda: backend.get_app_config(logged_in["account"]["account_id"], application_key))

    @router.patch("/app-config/{application_key}")
    def set_app_config(application_key: str, payload: dict = Body(...), current_user: dict = Depends(get_current_user)):
        logged_in = run(lambda: actor(current_user))
        if payload.get("reset"):
            return run(lambda: backend.reset_app_config(logged_in["account"]["account_id"], application_key))
        return run(lambda: backend.set_app_config(logged_in["account"]["account_id"], application_key, payload["config"]))

    return router

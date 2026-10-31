"""Kirish, rollar va huquqlar.

HUQUQLAR JADVALI: har bir yo'l uchun kerakli huquq aniq yozilgan. Jadvalda YO'Q yo'l kirish yoqilganda avtomatik
TAQIQLANADI (yangi endpoint qo'shilib, himoyasiz qolib ketmasin); `tests/test_auth.py` har bir ro'yxatdan o'tgan yo'l
jadvalda borligini tekshiradi.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

from core.auth import ROLES, AuthError, AuthService, LockedError, User
from core.identity import current_user
from core.store import EpisodeStore

# ochiq yo'llar: kirishsiz ham (sahifaning o'zi, holat, kirish)
PUBLIC = {("GET", "/"), ("GET", "/models-ui"), ("GET", "/shadow-ui"), ("GET", "/health"), ("GET", "/auth/status"), ("POST", "/auth/login")}

_ANY = "auth.any"          # istalgan kirgan foydalanuvchi
ROUTE_PERMS: dict[tuple[str, str], str] = {
    ("POST", "/auth/logout"): _ANY, ("GET", "/auth/me"): _ANY, ("POST", "/auth/change-password"): _ANY,
    ("GET", "/screening/red-flags"): _ANY, ("GET", "/models"): _ANY,
    ("GET", "/episodes"): "episode.read", ("POST", "/episodes"): "episode.create",
    ("GET", "/episodes/{eid}"): "episode.read", ("GET", "/episodes/{eid}/digest"): "episode.read",
    ("GET", "/episodes/{eid}/audit"): "episode.audit",
    ("POST", "/episodes/{eid}/transition"): "episode.transition",
    ("POST", "/episodes/{eid}/screening"): "screening.run",
    ("POST", "/episodes/{eid}/echo-diagnosis"): "echo.diagnosis",
    ("POST", "/episodes/{eid}/risk"): "risk.assess", ("GET", "/episodes/{eid}/heart-team-protocol"): "protocol.read",
    ("POST", "/episodes/{eid}/ecg"): "ai.upload", ("POST", "/episodes/{eid}/angio"): "ai.upload",
    ("POST", "/episodes/{eid}/echo-ef"): "ai.upload",
    ("POST", "/episodes/{eid}/guardian/checkin"): "guardian.submit", ("POST", "/episodes/{eid}/guardian/inr"): "guardian.submit",
    ("POST", "/episodes/{eid}/guardian/inr-image"): "guardian.submit",
    ("GET", "/alerts"): "alerts.read", ("GET", "/episodes/{eid}/alerts"): "alerts.read", ("POST", "/alerts/{alert_id}/ack"): "alerts.ack",
    ("GET", "/learning/status"): "learning.read",
    ("POST", "/learning/promote"): "learning.approve", ("POST", "/learning/rollback"): "learning.approve",
    ("GET", "/users"): "users.manage", ("POST", "/users"): "users.manage",
    ("POST", "/users/{username}/disable"): "users.manage", ("POST", "/users/{username}/enable"): "users.manage",
    ("POST", "/users/{username}/role"): "users.manage", ("POST", "/users/{username}/password"): "users.manage",
    ("GET", "/audit/security"): "users.manage",
    ("GET", "/shadow/pending"): "shadow.label", ("POST", "/shadow/{run_id}/label"): "shadow.label",
    ("GET", "/shadow/report"): "shadow.report",
}

_CLINICIAN = {"episode.create", "episode.read", "screening.run", "echo.diagnosis", "episode.transition", "ai.upload",
              "guardian.submit", "alerts.read"}
_CARDIOLOGIST = _CLINICIAN | {"risk.assess", "protocol.read", "episode.audit", "learning.read", "learning.approve",
                             "shadow.label", "shadow.report"}
ROLE_PERMS: dict[str, set[str]] = {
    "admin": {_ANY, "episode.read", "episode.audit", "alerts.read", "learning.read", "users.manage", "shadow.report"},
    "clinician": _CLINICIAN | {_ANY},
    "cardiologist": _CARDIOLOGIST | {_ANY},
    "surgeon": _CARDIOLOGIST | {"alerts.ack", _ANY},
    "icu": {_ANY, "episode.read", "episode.transition", "risk.assess", "protocol.read", "ai.upload", "guardian.submit", "alerts.read"},
    "patient": {_ANY, "guardian.submit"},       # faqat O'Z epizodiga uy-nazorat ma'lumoti
}
assert set(ROLE_PERMS) == set(ROLES)


def permissions_of(role: str) -> list[str]:
    return sorted(p for p in ROLE_PERMS[role] if p != _ANY)


def _bearer(request: Request) -> Optional[str]:
    h = request.headers.get("authorization", "")
    return h[7:].strip() if h.lower().startswith("bearer ") else None


def make_dependency(auth: AuthService) -> Callable:
    async def authenticate(request: Request) -> None:
        route = request.scope.get("route")
        key = (request.method, route.path if route is not None else request.url.path)
        if key in PUBLIC:
            return
        user = auth.resolve(_bearer(request))
        if user is None:
            raise HTTPException(401, "kirish talab etiladi", headers={"WWW-Authenticate": "Bearer"})
        perm = ROUTE_PERMS.get(key)
        if perm is None:
            raise HTTPException(403, "bu yo'l huquq jadvalida yo'q, shuning uchun taqiqlangan")
        if perm != _ANY and perm not in ROLE_PERMS[user.role]:
            raise HTTPException(403, f"«{user.role}» roli uchun ruxsat yo'q ({perm})")
        if user.role == "patient" and perm != _ANY and request.path_params.get("eid") != user.episode_id:
            raise HTTPException(403, "bemor faqat o'z epizodiga ma'lumot yubora oladi")
        request.state.user = user
        current_user.set(user.username)          # audit jurnali va yo'llanma muallifi uchun haqiqiy foydalanuvchi
    return authenticate


class LoginIn(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


class UserIn(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)
    role: str
    display_name: str = Field("", max_length=80)
    episode_id: Optional[str] = Field(None, max_length=64)


class RoleIn(BaseModel):
    role: str
    episode_id: Optional[str] = Field(None, max_length=64)


class PasswordIn(BaseModel):
    new_password: str = Field(max_length=256)


class ChangePasswordIn(BaseModel):
    old_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


def register_status(app: FastAPI, enabled: bool) -> None:
    @app.get("/auth/status")
    def auth_status() -> dict:
        """Kirish yoqilganmi? (sahifa shu bo'yicha kirish oynasini ko'rsatadi)"""
        return {"enabled": enabled}


def register(app: FastAPI, auth: AuthService, store: EpisodeStore) -> None:
    def fail(exc: AuthError) -> HTTPException:
        headers = {"Retry-After": str(exc.retry_after)} if isinstance(exc, LockedError) else None
        return HTTPException(exc.status, str(exc), headers=headers)

    def me(request: Request) -> User:
        return request.state.user

    @app.post("/auth/login")
    def login(body: LoginIn) -> dict:
        try:
            token, expires, user = auth.login(body.username, body.password)
        except AuthError as exc:
            raise fail(exc) from None
        return {"token": token, "expires_at": datetime.fromtimestamp(expires, timezone.utc).isoformat(),
                "user": user.public(), "permissions": permissions_of(user.role)}

    @app.post("/auth/logout")
    def logout(request: Request) -> dict:
        auth.logout(_bearer(request) or "")
        return {"ok": True}

    @app.get("/auth/me")
    def auth_me(request: Request) -> dict:
        u = me(request)
        return {"user": u.public(), "permissions": permissions_of(u.role)}

    @app.post("/auth/change-password")
    def change_password(body: ChangePasswordIn, request: Request) -> dict:
        try:
            auth.change_password(me(request).username, body.old_password, body.new_password, keep_token=_bearer(request))
        except AuthError as exc:
            raise fail(exc) from None
        return {"ok": True, "note": "boshqa qurilmalardagi seanslar bekor qilindi"}

    @app.get("/users")
    def list_users() -> list[dict]:
        return [u.public() for u in auth.list_users()]

    @app.post("/users", status_code=201)
    def create_user(body: UserIn, request: Request) -> dict:
        try:
            return auth.create_user(body.username, body.password, body.role, body.display_name, body.episode_id,
                                    by=me(request).username).public()
        except AuthError as exc:
            raise fail(exc) from None

    @app.post("/users/{username}/disable")
    def disable_user(username: str, request: Request) -> dict:
        try:
            return auth.set_active(username, False, by=me(request).username).public()
        except AuthError as exc:
            raise fail(exc) from None

    @app.post("/users/{username}/enable")
    def enable_user(username: str, request: Request) -> dict:
        try:
            return auth.set_active(username, True, by=me(request).username).public()
        except AuthError as exc:
            raise fail(exc) from None

    @app.post("/users/{username}/role")
    def set_role(username: str, body: RoleIn, request: Request) -> dict:
        try:
            return auth.set_role(username, body.role, by=me(request).username, episode_id=body.episode_id).public()
        except AuthError as exc:
            raise fail(exc) from None

    @app.post("/users/{username}/password")
    def reset_password(username: str, body: PasswordIn, request: Request) -> dict:
        try:
            auth.reset_password(username, body.new_password, by=me(request).username)
        except AuthError as exc:
            raise fail(exc) from None
        return {"ok": True, "note": "foydalanuvchining barcha seanslari bekor qilindi"}

    @app.get("/audit/security")
    def security_log(limit: int = Query(100, ge=1, le=500)) -> list[dict]:
        """Kirish, chiqish va foydalanuvchilar boshqaruvi hodisalari (parol va tokenlar yozilmaydi)."""
        return store.security_events(limit)

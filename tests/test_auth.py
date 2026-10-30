"""Kirish va rollar: huquqlar jadvali to'liq, rol bo'yicha taqiq, bloklash, seans muddati, haqiqiy foydalanuvchi auditda."""
import json
import sqlite3

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api import auth_routes
from api.main import create_app, default_app
from core.auth import MAX_FAILS, AuthError, AuthService, hash_password, verify_password
from core.identity import current_user
from core.registry import ModelCard
from core.store import SqliteEpisodeStore
from screening.model import PCGModel

CARD = ModelCard(name="pcg_test", version="0", task="t", dataset="CirCor DigiScope", weights="none")
PW = "Yaxshi-parol-123"


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def env(tmp_path):
    db = str(tmp_path / "a.db")
    store = SqliteEpisodeStore(db)
    clock = Clock()
    auth = AuthService(db, log=store.log_event, clock=clock)
    auth.create_user("admin1", PW, "admin", by="test")
    model = PCGModel(CARD, lambda x: (np.full(len(x), 0.9, np.float32), np.full(len(x), 0.1, np.float32)))
    client = TestClient(create_app(store, model, auth=auth, recordings_dir=tmp_path / "rec", models_dir=tmp_path / "models"))
    return client, auth, store, clock, db


def login(client, user, pw=PW):
    r = client.post("/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def make(auth, name, role, **kw):
    auth.create_user(name, PW, role, by="test", **kw)


def hdr(env, name, role, **kw):
    client, auth = env[0], env[1]
    make(auth, name, role, **kw)
    return login(client, name)


# ---------- parol
def test_password_hash_is_salted_and_verifies():
    a, b = hash_password(PW), hash_password(PW)
    assert a != b and verify_password(PW, a) and not verify_password(PW + "x", a) and PW not in a


def test_password_policy(env):
    auth = env[1]
    for i, bad in enumerate(("qisqa", "password123", "kimdir-parol")):          # qisqa, keng tarqalgan, nomga teng
        name = "kimdir-parol" if i == 2 else f"user{i}"
        with pytest.raises(AuthError) as e:
            auth.create_user(name, bad, "clinician", by="t")
        assert e.value.status == 422


# ---------- ochiq / yopiq
def test_public_routes_and_everything_else_needs_login(env):
    client = env[0]
    assert client.get("/health").json()["auth"] == "on"
    assert client.get("/auth/status").json() == {"enabled": True}
    assert client.get("/").status_code == 200
    for method, path in [("GET", "/episodes"), ("POST", "/episodes"), ("GET", "/alerts"), ("GET", "/users"), ("GET", "/models")]:
        assert client.request(method, path).status_code == 401, (method, path)
    assert client.get("/episodes", headers={"Authorization": "Bearer yolgon"}).status_code == 401


def test_docs_are_disabled_when_auth_is_on(env):
    for p in ("/docs", "/redoc", "/openapi.json"):
        assert env[0].get(p).status_code in (401, 404)


def test_auth_off_is_unchanged(tmp_path):
    model = PCGModel(CARD, lambda x: (np.full(len(x), 0.9, np.float32), np.full(len(x), 0.1, np.float32)))
    c = TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "o.db")), model))
    assert c.get("/health").json()["auth"] == "off" and c.get("/auth/status").json() == {"enabled": False}
    assert c.post("/episodes", json={"patient_ref": "X-1", "actor": "dr"}).status_code == 201
    assert c.get("/docs").status_code == 200


def test_every_registered_route_is_in_the_permission_table(env):
    app = env[0].app
    seen = set()
    for r in app.routes:
        for m in getattr(r, "methods", None) or ():
            if m in ("HEAD", "OPTIONS"):
                continue
            seen.add((m, r.path))
    missing = {k for k in seen if k not in auth_routes.ROUTE_PERMS and k not in auth_routes.PUBLIC}
    assert not missing, f"huquq jadvalida yo'q: {sorted(missing)}"
    stale = {k for k in auth_routes.ROUTE_PERMS if k not in seen}
    assert not stale, f"jadvalda bor, lekin yo'l yo'q: {sorted(stale)}"


def test_unlisted_route_is_forbidden_not_open(env):
    client, auth = env[0], env[1]

    @client.app.get("/yangi-yashirin")
    def yangi() -> dict:
        return {"x": 1}
    h = login(client, "admin1")
    assert client.get("/yangi-yashirin", headers=h).status_code == 403


# ---------- rollar
ROLE_MATRIX = {
    # rol: (epizod yarata oladimi, xavf baholay oladimi, signalni tasdiqlay oladimi, foydalanuvchilarni boshqaradimi)
    "admin": (False, False, False, True),
    "clinician": (True, False, False, False),
    "cardiologist": (True, True, False, False),
    "surgeon": (True, True, True, False),
    "icu": (False, True, False, False),
}


@pytest.mark.parametrize("role", sorted(ROLE_MATRIX))
def test_role_permissions_matrix(env, role):
    client = env[0]
    h = hdr(env, "u-" + role, role)
    create, risk, ack, users = ROLE_MATRIX[role]
    assert (client.post("/episodes", json={"patient_ref": "R-1"}, headers=h).status_code == 201) is create
    assert (client.get("/users", headers=h).status_code == 200) is users
    assert (client.get("/audit/security", headers=h).status_code == 200) is users
    # xavf: ruxsat bo'lsa 404 (epizod yo'q) yoki 422 (tana), bo'lmasa aniq 403
    code = client.post("/episodes/yoq/risk", json={}, headers=h).status_code
    assert (code != 403) is risk
    code = client.post("/alerts/99999/ack", json={"actor": "x"}, headers=h).status_code
    assert (code != 403) is ack


def test_admin_cannot_run_clinical_actions(env):
    client = env[0]
    h = login(client, "admin1")
    assert client.post("/episodes", json={"patient_ref": "A-1"}, headers=h).status_code == 403
    assert client.get("/episodes", headers=h).status_code == 200


def test_me_and_permissions(env):
    client = env[0]
    h = hdr(env, "kardio1", "cardiologist", display_name="Dr. K")
    body = client.get("/auth/me", headers=h).json()
    assert body["user"]["role"] == "cardiologist" and "risk.assess" in body["permissions"] and "users.manage" not in body["permissions"]
    assert "password" not in json.dumps(body).lower()


# ---------- bemor
def test_patient_only_submits_to_own_episode(env):
    client = env[0]
    doc = hdr(env, "dr1", "clinician")
    own = client.post("/episodes", json={"patient_ref": "P-1"}, headers=doc).json()["id"]
    other = client.post("/episodes", json={"patient_ref": "P-2"}, headers=doc).json()["id"]
    p = hdr(env, "bemor1", "patient", episode_id=own)
    assert client.post(f"/episodes/{own}/guardian/checkin", json={"actor": "x", "heart_rate": 80}, headers=p).status_code != 403
    assert client.post(f"/episodes/{other}/guardian/checkin", json={"actor": "x", "heart_rate": 80}, headers=p).status_code == 403
    assert client.get(f"/episodes/{own}", headers=p).status_code == 403          # o'qish ham yo'q
    assert client.get("/episodes", headers=p).status_code == 403
    assert client.get("/alerts", headers=p).status_code == 403
    assert client.post("/episodes", json={"patient_ref": "P-3"}, headers=p).status_code == 403


def test_patient_requires_episode_id(env):
    with pytest.raises(AuthError):
        env[1].create_user("bemor2", PW, "patient", by="t")


# ---------- bloklash, muddat
def test_lockout_after_failed_attempts_even_for_unknown_user(env):
    client, auth, store, clock, _ = env
    for _ in range(MAX_FAILS):
        assert client.post("/auth/login", json={"username": "admin1", "password": "noto'g'ri-parol"}).status_code == 401
    r = client.post("/auth/login", json={"username": "admin1", "password": PW})          # to'g'ri parol ham bloklangan
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    clock.t += 301
    assert client.post("/auth/login", json={"username": "admin1", "password": PW}).status_code == 200
    for _ in range(MAX_FAILS):
        client.post("/auth/login", json={"username": "yoq-odam", "password": "x"})
    assert client.post("/auth/login", json={"username": "yoq-odam", "password": "x"}).status_code == 429


def test_error_does_not_reveal_whether_user_exists(env):
    client = env[0]
    a = client.post("/auth/login", json={"username": "admin1", "password": "x"})
    b = client.post("/auth/login", json={"username": "yoq-odam", "password": "x"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_session_expires(env):
    client, auth, store, clock, _ = env
    h = login(client, "admin1")
    assert client.get("/auth/me", headers=h).status_code == 200
    clock.t += 12 * 3600 + 1
    assert client.get("/auth/me", headers=h).status_code == 401


def test_logout_revokes_token(env):
    client = env[0]
    h = login(client, "admin1")
    assert client.post("/auth/logout", headers=h).status_code == 200
    assert client.get("/auth/me", headers=h).status_code == 401


def test_token_is_stored_only_as_hash(env):
    client, _, _, _, db = env
    h = login(client, "admin1")
    token = h["Authorization"].split()[1]
    raw = sqlite3.connect(db)
    dump = json.dumps([list(r) for t in ("sessions", "users") for r in raw.execute(f"SELECT * FROM {t}")])
    assert token not in dump and PW not in dump


# ---------- boshqaruv
def test_disabled_user_token_dies_immediately(env):
    client = env[0]
    admin = login(client, "admin1")
    h = hdr(env, "dr2", "clinician")
    assert client.get("/auth/me", headers=h).status_code == 200
    assert client.post("/users/dr2/disable", headers=admin).status_code == 200
    assert client.get("/auth/me", headers=h).status_code == 401
    assert client.post("/auth/login", json={"username": "dr2", "password": PW}).status_code == 401
    assert client.post("/users/dr2/enable", headers=admin).status_code == 200
    login(client, "dr2")


def test_role_change_applies_to_existing_session(env):
    client = env[0]
    admin = login(client, "admin1")
    h = hdr(env, "dr3", "clinician")
    assert client.post("/episodes", json={"patient_ref": "C-1"}, headers=h).status_code == 201
    assert client.post("/users/dr3/role", json={"role": "icu"}, headers=admin).status_code == 200
    assert client.post("/episodes", json={"patient_ref": "C-2"}, headers=h).status_code == 403


def test_last_active_admin_is_protected(env):
    client, auth = env[0], env[1]
    admin = login(client, "admin1")
    assert client.post("/users/admin1/disable", headers=admin).status_code == 409
    assert client.post("/users/admin1/role", json={"role": "clinician"}, headers=admin).status_code == 409
    make(auth, "admin2", "admin")
    assert client.post("/users/admin1/disable", headers=admin).status_code == 200      # endi ikkinchi administrator bor


def test_password_change_revokes_other_sessions_only(env):
    client = env[0]
    make(env[1], "dr4", "clinician")
    a, b = login(client, "dr4"), login(client, "dr4")
    r = client.post("/auth/change-password", json={"old_password": PW, "new_password": "Yangi-parol-456"}, headers=a)
    assert r.status_code == 200
    assert client.get("/auth/me", headers=a).status_code == 200 and client.get("/auth/me", headers=b).status_code == 401
    assert client.post("/auth/change-password", json={"old_password": "xato", "new_password": "Boshqa-parol-789"}, headers=a).status_code == 401
    login(client, "dr4", "Yangi-parol-456")


def test_admin_password_reset_revokes_sessions(env):
    client = env[0]
    admin = login(client, "admin1")
    h = hdr(env, "dr5", "clinician")
    assert client.post("/users/dr5/password", json={"new_password": "Tiklangan-parol-1"}, headers=admin).status_code == 200
    assert client.get("/auth/me", headers=h).status_code == 401
    login(client, "dr5", "Tiklangan-parol-1")


def test_user_creation_validation(env):
    client = env[0]
    admin = login(client, "admin1")
    ok = client.post("/users", json={"username": "dr6", "password": PW, "role": "clinician"}, headers=admin)
    assert ok.status_code == 201 and "password" not in json.dumps(ok.json()).lower()
    assert client.post("/users", json={"username": "dr6", "password": PW, "role": "clinician"}, headers=admin).status_code == 409
    assert client.post("/users", json={"username": "dr7", "password": PW, "role": "bosh-vrach"}, headers=admin).status_code == 422
    assert client.post("/users", json={"username": "D R", "password": PW, "role": "clinician"}, headers=admin).status_code == 422


# ---------- audit: haqiqiy foydalanuvchi
def test_audit_records_real_user_not_claimed_actor(env):
    client = env[0]
    h = hdr(env, "dr.haqiqiy", "cardiologist")
    eid = client.post("/episodes", json={"patient_ref": "A-1", "actor": "soxta-nom"}, headers=h).json()["id"]
    audit = client.get(f"/episodes/{eid}/audit", headers=h).json()
    assert audit and {a["actor"] for a in audit} == {"dr.haqiqiy"}


def test_handoff_author_and_alert_ack_use_real_user(env):
    client, auth, store, _, _ = env
    h = hdr(env, "jarroh1", "surgeon")
    eid = client.post("/episodes", json={"patient_ref": "H-1", "population": "adult"}, headers=h).json()["id"]
    cur = "screening"
    for stage in ("workup", "heart_team", "procedure", "icu", "discharge", "guardian_30d"):
        t = client.post(f"/episodes/{eid}/transition", headers=h, json={"from_stage": cur, "to_stage": stage, "author": "soxta-muallif"})
        assert t.status_code == 200, t.text
        cur = stage
    ep = store.get(eid)
    assert ep.handoffs and all(hh.author == "jarroh1" for hh in ep.handoffs)

    # signal: bemor yuboradi, jarroh tasdiqlaydi
    p = hdr(env, "bemor9", "patient", episode_id=eid)
    r = client.post(f"/episodes/{eid}/guardian/checkin", headers=p, json={"actor": "x", "wound_signs": ["purulent_discharge"]})
    assert r.status_code == 200 and r.json()["alert_id"] is not None, r.text
    alerts = client.get(f"/episodes/{eid}/alerts", headers=h).json()["items"]
    assert alerts
    ack = client.post(f"/alerts/{alerts[0]['id']}/ack", json={"actor": "soxta-tasdiqlovchi"}, headers=h)
    assert ack.status_code == 200 and ack.json()["ack_by"] == "jarroh1"
    assert {a["actor"] for a in client.get(f"/episodes/{eid}/audit", headers=h).json() if a["action"] == "alert.ack"} == {"jarroh1"}
    assert "bemor9" in {a["actor"] for a in client.get(f"/episodes/{eid}/audit", headers=h).json()}


def test_security_log_has_events_but_no_secrets(env):
    client = env[0]
    client.post("/auth/login", json={"username": "admin1", "password": "TOKEN-EMAS-parol-xato"})
    h = login(client, "admin1")
    client.post("/users", json={"username": "dr8", "password": "Maxfiy-parol-999", "role": "clinician"}, headers=h)
    ev = client.get("/audit/security", headers=h).json()
    actions = {e["action"] for e in ev}
    assert {"auth.login_failed", "auth.login", "user.create"} <= actions
    dump = json.dumps(ev)
    assert "TOKEN-EMAS-parol-xato" not in dump and "Maxfiy-parol-999" not in dump and h["Authorization"].split()[1] not in dump


def test_identity_context_is_cleared_after_request(env):
    client = env[0]
    h = hdr(env, "dr9", "clinician")
    client.get("/auth/me", headers=h)
    assert current_user.get() is None


# ---------- ishga tushirish himoyasi
def test_default_app_refuses_to_start_without_admin(tmp_path, monkeypatch):
    monkeypatch.setenv("CARDIOPATH_DB", str(tmp_path / "bosh.db"))
    monkeypatch.setenv("CARDIOPATH_AUTH", "on")
    with pytest.raises(SystemExit) as e:
        default_app()
    assert "auth_cli" in str(e.value)


def test_auth_cli_creates_admin_then_default_app_starts(tmp_path, monkeypatch, capsys):
    from core import auth_cli
    db = str(tmp_path / "cli.db")
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(PW + "\n"))
    assert auth_cli.main(["--db", db, "create-user", "--username", "bosh-admin", "--role", "admin", "--password-stdin"]) == 0
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("qisqa\n"))
    assert auth_cli.main(["--db", db, "create-user", "--username", "dr10", "--role", "clinician", "--password-stdin"]) == 1
    assert auth_cli.main(["--db", db, "list-users"]) == 0
    out = capsys.readouterr().out
    assert "bosh-admin" in out and "dr10" not in out and PW not in out
    monkeypatch.setenv("CARDIOPATH_DB", db)
    monkeypatch.setenv("CARDIOPATH_AUTH", "on")
    monkeypatch.setenv("CARDIOPATH_MODELS", str(tmp_path / "m"))
    app = default_app()
    assert TestClient(app).get("/auth/status").json() == {"enabled": True}


# ---------- model tasdiqlash ekrani (E18)
def _candidate(tmp_path, passed=True, name="c1"):
    from learning.versions import ModelVersions
    from tests.test_learning import make_files, report
    return ModelVersions(tmp_path / "models").add_candidate(make_files(tmp_path, name), report(passed))


def test_promote_requires_cardiologist_or_surgeon_and_records_real_name(env, tmp_path):
    client = env[0]
    vid = _candidate(tmp_path)
    body = {"version": vid, "note": "yaxshi natija"}
    for role in ("clinician", "icu", "admin", "patient"):
        extra = {"episode_id": "e1"} if role == "patient" else {}
        h = hdr(env, "u-" + role, role, **extra)
        assert client.post("/learning/promote", json=body, headers=h).status_code == 403, role
    assert client.post("/learning/promote", json=body).status_code == 401
    h = hdr(env, "dr.tasdiq", "cardiologist")
    r = client.post("/learning/promote", json=body, headers=h)
    assert r.status_code == 200 and r.json()["approved_by"] == "dr.tasdiq" and r.json()["restart_needed"] is True
    st = client.get("/learning/status", headers=h).json()
    assert st["current_version"] == vid and any(x["event"] == "promoted" and x["by"] == "dr.tasdiq" for x in st["history"])
    assert any(e["action"] == "model.promote" and e["actor"] == "dr.tasdiq"
               for e in client.get("/audit/security", headers=login(client, "admin1")).json())
    assert client.post("/learning/promote", json=body, headers=h).status_code == 409           # allaqachon joriy


def test_failed_or_unknown_candidate_cannot_be_promoted(env, tmp_path):
    client = env[0]
    h = hdr(env, "jarroh2", "surgeon")
    bad = _candidate(tmp_path, passed=False, name="bad")
    assert client.post("/learning/promote", json={"version": bad}, headers=h).status_code == 409
    assert client.post("/learning/promote", json={"version": "v-yoq"}, headers=h).status_code == 409
    assert client.post("/learning/promote", json={"version": "../.."}, headers=h).status_code == 422


def test_rollback_needs_reason_and_restores_previous(env, tmp_path):
    client = env[0]
    h = hdr(env, "dr.qaytar", "cardiologist")
    v1 = _candidate(tmp_path, name="r1")
    assert client.post("/learning/rollback", json={"note": "sabab bor"}, headers=h).status_code == 409   # qaytariladigan narsa yo'q
    client.post("/learning/promote", json={"version": v1}, headers=h)
    assert client.post("/learning/rollback", json={"note": "x"}, headers=h).status_code == 422
    r = client.post("/learning/rollback", json={"note": "sifat tushdi"}, headers=h)
    assert r.status_code == 200 and r.json()["restored"] == "baseline" and r.json()["approved_by"] == "dr.qaytar"
    assert client.get("/learning/status", headers=h).json()["current_version"] == "baseline"


def test_promote_refused_when_auth_is_off(tmp_path):
    model = PCGModel(CARD, lambda x: (np.full(len(x), 0.9, np.float32), np.full(len(x), 0.1, np.float32)))
    c = TestClient(create_app(SqliteEpisodeStore(str(tmp_path / "off.db")), model, models_dir=tmp_path / "models"))
    vid = _candidate(tmp_path)
    r = c.post("/learning/promote", json={"version": vid})
    assert r.status_code == 403 and "CARDIOPATH_AUTH" in r.json()["detail"]
    assert c.get("/learning/status").json()["current_version"] == "baseline"


def test_models_page_is_served(env):
    r = env[0].get("/models-ui")
    assert r.status_code == 200 and "learning/promote" in r.text and "uz" in r.text

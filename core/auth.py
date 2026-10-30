"""Foydalanuvchilar, parollar, seanslar va kirishni bloklash.

Xavfsizlik qarorlari:
  * Parol scrypt (standart kutubxona, tuzli) bilan saqlanadi; ochiq parol HECH QAYERDA yozilmaydi (jurnalda ham).
  * Standart parol yo'q: birinchi administrator buyruq satridan yaratiladi (python -m core.auth_cli).
  * Token tasodifiy 32 bayt; bazada faqat uning SHA-256 xeshi (baza o'g'irlansa ham tokenni tiklab bo'lmaydi). Muddat 12 soat.
  * Noto'g'ri parol 5 marta → 5 daqiqa bloklash. Mavjud bo'lmagan nom uchun ham xuddi shunday hisoblanadi va parol
    tekshiruvi vaqti o'zgarmaydi (foydalanuvchi nomini topib bo'lmasin).
  * Oxirgi faol administratorni o'chirish yoki roldan mahrum qilish mumkin emas (tizim qulflanib qolmasin).
  * Foydalanuvchi o'chirilsa/roli o'zgarsa, qo'llanishi darhol (har so'rovda bazadan o'qiladi); o'chirilsa seanslari bekor.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable, Optional

ROLES = ("admin", "clinician", "cardiologist", "surgeon", "icu", "patient")
MIN_PASSWORD = 10
SESSION_TTL_S = 12 * 3600
MAX_FAILS, LOCK_S, MAX_TRACKED = 5, 300, 10_000
_USERNAME = re.compile(r"^[a-z0-9._-]{3,32}$")
_COMMON = {"password12", "password123", "1234567890", "qwertyuiop", "0123456789", "1q2w3e4r5t", "parol12345", "admin12345"}
_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}


class AuthError(Exception):
    """status: 401 kirish xatosi, 403 taqiqlangan, 409 ziddiyat, 422 noto'g'ri qiymat, 404 topilmadi."""

    def __init__(self, message: str, status: int = 401) -> None:
        super().__init__(message)
        self.status = status


class LockedError(AuthError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"juda ko'p noto'g'ri urinish; {retry_after} soniyadan keyin qayta urinib ko'ring", 429)
        self.retry_after = retry_after


@dataclass(frozen=True)
class User:
    username: str
    role: str
    display_name: str
    active: bool
    episode_id: Optional[str] = None

    def public(self) -> dict:
        return {"username": self.username, "role": self.role, "display_name": self.display_name,
                "active": self.active, "episode_id": self.episode_id}


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, **_SCRYPT)
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, dk = stored.split("$")
        if scheme != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                              dklen=len(base64.b64decode(dk)))
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except (ValueError, TypeError):
        return False


_DUMMY: Optional[str] = None


def _dummy_hash() -> str:
    global _DUMMY
    if _DUMMY is None:
        _DUMMY = hash_password("timing-equalizer-not-a-real-password")
    return _DUMMY


def check_password_policy(username: str, password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"parol kamida {MIN_PASSWORD} belgi bo'lishi kerak", 422)
    if password.lower() == username.lower() or password.lower() in _COMMON:
        raise AuthError("parol juda oddiy yoki foydalanuvchi nomiga teng", 422)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, db_path: str, log: Optional[Callable[[str, str, dict], None]] = None,
                 clock: Callable[[], float] = time.time, session_ttl: int = SESSION_TTL_S) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False, timeout=15)
        self._lock = threading.Lock()
        self._clock, self._ttl = clock, session_ttl
        self._log = log or (lambda actor, action, detail: None)
        # foydalanuvchi nomi → [urinishlar soni, bloklanish tugashi]; cheklangan (LRU), shunda xotira cheksiz o'smaydi
        self._fails: "OrderedDict[str, list]" = OrderedDict()
        with self._lock, self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, display_name TEXT, password_hash TEXT NOT NULL, "
                "role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, episode_id TEXT, created_at REAL, updated_at REAL)")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, created_at REAL, expires_at REAL)")

    # ---- foydalanuvchilar
    @staticmethod
    def _user(row) -> User:
        return User(username=row[0], role=row[1], display_name=row[2] or row[0], active=bool(row[3]), episode_id=row[4])

    _COLS = "username, role, display_name, active, episode_id"

    def _get(self, username: str) -> Optional[User]:
        row = self._conn.execute(f"SELECT {self._COLS} FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()
        return self._user(row) if row else None

    def get(self, username: str) -> Optional[User]:
        with self._lock:
            return self._get(username)

    def list_users(self) -> list[User]:
        with self._lock:
            return [self._user(r) for r in self._conn.execute(f"SELECT {self._COLS} FROM users ORDER BY username")]

    def has_admin(self) -> bool:
        with self._lock:
            return self._conn.execute("SELECT 1 FROM users WHERE role = 'admin' AND active = 1 LIMIT 1").fetchone() is not None

    def create_user(self, username: str, password: str, role: str, display_name: str = "", episode_id: Optional[str] = None,
                    by: str = "system") -> User:
        username = username.strip().lower()
        if not _USERNAME.match(username):
            raise AuthError("foydalanuvchi nomi 3–32 belgi: kichik lotin harflari, raqam, '.', '_', '-'", 422)
        if role not in ROLES:
            raise AuthError(f"noma'lum rol: {role} (mumkin: {', '.join(ROLES)})", 422)
        if role == "patient" and not episode_id:
            raise AuthError("bemor roli uchun epizod ID kerak (u faqat o'z epizodiga yoza oladi)", 422)
        if role != "patient" and episode_id:
            raise AuthError("epizod ID faqat bemor roli uchun", 422)
        check_password_policy(username, password)
        now = self._clock()
        with self._lock, self._conn:
            if self._get(username):
                raise AuthError("bunday foydalanuvchi allaqachon bor", 409)
            self._conn.execute(
                "INSERT INTO users (username, display_name, password_hash, role, active, episode_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 1, ?, ?, ?)",
                (username, display_name.strip()[:80] or username, hash_password(password), role, episode_id, now, now))
        self._log(by, "user.create", {"username": username, "role": role})
        return self.get(username)  # type: ignore[return-value]

    def _other_active_admin(self, username: str) -> bool:
        return self._conn.execute("SELECT 1 FROM users WHERE role = 'admin' AND active = 1 AND username != ? LIMIT 1",
                                  (username,)).fetchone() is not None

    def set_active(self, username: str, active: bool, by: str) -> User:
        with self._lock, self._conn:
            user = self._get(username)
            if user is None:
                raise AuthError("foydalanuvchi topilmadi", 404)
            if not active and user.role == "admin" and user.active and not self._other_active_admin(user.username):
                raise AuthError("oxirgi faol administratorni o'chirib bo'lmaydi", 409)
            self._conn.execute("UPDATE users SET active = ?, updated_at = ? WHERE username = ?",
                               (int(active), self._clock(), user.username))
            if not active:
                self._conn.execute("DELETE FROM sessions WHERE username = ?", (user.username,))
        self._log(by, "user.enable" if active else "user.disable", {"username": user.username})
        return self.get(username)  # type: ignore[return-value]

    def set_role(self, username: str, role: str, by: str, episode_id: Optional[str] = None) -> User:
        if role not in ROLES:
            raise AuthError(f"noma'lum rol: {role}", 422)
        if role == "patient" and not episode_id:
            raise AuthError("bemor roli uchun epizod ID kerak", 422)
        with self._lock, self._conn:
            user = self._get(username)
            if user is None:
                raise AuthError("foydalanuvchi topilmadi", 404)
            if user.role == "admin" and role != "admin" and user.active and not self._other_active_admin(user.username):
                raise AuthError("oxirgi faol administratorning rolini o'zgartirib bo'lmaydi", 409)
            self._conn.execute("UPDATE users SET role = ?, episode_id = ?, updated_at = ? WHERE username = ?",
                               (role, episode_id if role == "patient" else None, self._clock(), user.username))
        self._log(by, "user.set_role", {"username": user.username, "from": user.role, "to": role})
        return self.get(username)  # type: ignore[return-value]

    def _set_password(self, username: str, new_password: str, keep_token: Optional[str] = None) -> None:
        check_password_policy(username, new_password)
        with self._lock, self._conn:
            self._conn.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE username = ?",
                               (hash_password(new_password), self._clock(), username))
            if keep_token:
                self._conn.execute("DELETE FROM sessions WHERE username = ? AND token_hash != ?", (username, _token_hash(keep_token)))
            else:
                self._conn.execute("DELETE FROM sessions WHERE username = ?", (username,))
            self._fails.pop(username, None)

    def reset_password(self, username: str, new_password: str, by: str) -> None:
        user = self.get(username)
        if user is None:
            raise AuthError("foydalanuvchi topilmadi", 404)
        self._set_password(user.username, new_password)
        self._log(by, "user.reset_password", {"username": user.username})

    def change_password(self, username: str, old_password: str, new_password: str, keep_token: Optional[str] = None) -> None:
        with self._lock:
            row = self._conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,)).fetchone()
        if row is None or not verify_password(old_password, row[0]):
            self._log(username, "auth.change_password_failed", {})
            raise AuthError("eski parol noto'g'ri", 401)
        self._set_password(username, new_password, keep_token)
        self._log(username, "auth.change_password", {})

    # ---- kirish
    def _check_lock(self, username: str) -> None:
        with self._lock:
            until = self._fails.get(username, [0, 0.0])[1]
        left = int(until - self._clock())
        if left > 0:
            raise LockedError(left)

    def _record_fail(self, username: str) -> None:
        with self._lock:
            rec = self._fails.setdefault(username, [0, 0.0])
            self._fails.move_to_end(username)
            rec[0] += 1
            if rec[0] >= MAX_FAILS:
                rec[0], rec[1] = 0, self._clock() + LOCK_S
            while len(self._fails) > MAX_TRACKED:
                self._fails.popitem(last=False)

    def login(self, username: str, password: str) -> tuple[str, float, User]:
        key = (username or "").strip().lower()
        self._check_lock(key)
        with self._lock:
            row = self._conn.execute("SELECT password_hash, role, display_name, active, episode_id FROM users WHERE username = ?",
                                     (key,)).fetchone()
        # mavjud bo'lmagan nom uchun ham parol tekshiruvi bajariladi (vaqt farqi nomni oshkor qilmasin)
        ok = verify_password(password or "", row[0] if row else _dummy_hash())
        if not (row and ok and row[3]):
            self._record_fail(key)
            self._log(key[:32] or "-", "auth.login_failed", {})
            raise AuthError("login yoki parol noto'g'ri", 401)
        with self._lock:
            self._fails.pop(key, None)
        token = secrets.token_urlsafe(32)
        now = self._clock()
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            self._conn.execute("INSERT INTO sessions (token_hash, username, created_at, expires_at) VALUES (?, ?, ?, ?)",
                               (_token_hash(token), key, now, now + self._ttl))
        self._log(key, "auth.login", {})
        return token, now + self._ttl, User(key, row[1], row[2] or key, True, row[4])

    def resolve(self, token: Optional[str]) -> Optional[User]:
        if not token:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT u.username, u.role, u.display_name, u.active, u.episode_id FROM sessions s JOIN users u ON u.username = s.username "
                "WHERE s.token_hash = ? AND s.expires_at > ? AND u.active = 1", (_token_hash(token), self._clock())).fetchone()
        return self._user(row) if row else None

    def logout(self, token: str) -> None:
        user = self.resolve(token)
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
        if user:
            self._log(user.username, "auth.logout", {})

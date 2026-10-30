"""Foydalanuvchilarni buyruq satridan boshqarish (birinchi administratorni shu yerdan yaratasiz).

    python -m core.auth_cli create-user --username dr.karimova --role cardiologist --display-name "Dr. Karimova"
    python -m core.auth_cli create-user --username admin1 --role admin
    python -m core.auth_cli create-user --username bemor001 --role patient --episode-id <epizod ID>
    python -m core.auth_cli list-users | disable <nom> | enable <nom> | set-role <nom> <rol> | reset-password <nom>

Parol so'raladi (ekranda ko'rinmaydi, ikki marta). Skriptlar uchun: --password-stdin. Standart parol yo'q.
Baza: --db yoki CARDIOPATH_DB (standart: cardiopath.db). Kirishni yoqish: CARDIOPATH_AUTH=on.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

from core.auth import ROLES, AuthError, AuthService
from core.store import SqliteEpisodeStore

BY = "cli"


def _password(args) -> str:
    if args.password_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    p1 = getpass.getpass("Parol: ")
    if p1 != getpass.getpass("Parolni takrorlang: "):
        raise AuthError("parollar mos kelmadi", 422)
    return p1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("CARDIOPATH_DB", "cardiopath.db"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-user")
    c.add_argument("--username", required=True)
    c.add_argument("--role", required=True, choices=ROLES)
    c.add_argument("--display-name", default="")
    c.add_argument("--episode-id")
    c.add_argument("--password-stdin", action="store_true")
    sub.add_parser("list-users")
    for name in ("disable", "enable"):
        sub.add_parser(name).add_argument("username")
    r = sub.add_parser("set-role")
    r.add_argument("username")
    r.add_argument("role", choices=ROLES)
    r.add_argument("--episode-id")
    p = sub.add_parser("reset-password")
    p.add_argument("username")
    p.add_argument("--password-stdin", action="store_true")
    args = ap.parse_args(argv)

    store = SqliteEpisodeStore(args.db)
    auth = AuthService(args.db, log=store.log_event)
    try:
        if args.cmd == "create-user":
            u = auth.create_user(args.username, _password(args), args.role, args.display_name, args.episode_id, by=BY)
            print(f"yaratildi: {u.username} ({u.role})")
        elif args.cmd == "list-users":
            for u in auth.list_users():
                print(f"{u.username:24s} {u.role:13s} {'faol' if u.active else 'O`CHIRILGAN':10s} {u.display_name}"
                      + (f"  epizod={u.episode_id}" if u.episode_id else ""))
        elif args.cmd in ("disable", "enable"):
            u = auth.set_active(args.username, args.cmd == "enable", by=BY)
            print(f"{u.username}: {'faol' if u.active else 'o`chirildi'}")
        elif args.cmd == "set-role":
            u = auth.set_role(args.username, args.role, by=BY, episode_id=args.episode_id)
            print(f"{u.username}: rol {u.role}")
        elif args.cmd == "reset-password":
            auth.reset_password(args.username, _password(args), by=BY)
            print("parol almashtirildi; foydalanuvchining barcha seanslari bekor qilindi")
    except AuthError as exc:
        print(f"RAD ETILDI: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

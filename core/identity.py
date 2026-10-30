"""So'rovni bajarayotgan HAQIQIY foydalanuvchi (kirish yoqilgan bo'lsa).

Hozirgacha `actor`/`author` maydonini mijoz o'zi yozar edi, ya'ni istalgan ism yozish mumkin edi. Kirish yoqilganda
server autentifikatsiya qilingan foydalanuvchini shu kontekst o'zgaruvchisiga qo'yadi va audit jurnali, yo'llanma muallifi
hamda signalni qabul qiluvchi uchun mijoz yozgan ism E'TIBORSIZ qoldiriladi.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

current_user: ContextVar[Optional[str]] = ContextVar("current_user", default=None)


def effective_actor(claimed: str) -> str:
    """Kirish yoqilgan bo'lsa — haqiqiy foydalanuvchi nomi; o'chiq bo'lsa — mijoz yozgan ism (avvalgidek)."""
    return current_user.get() or claimed

"""Eskalatsiya: Guardian natijalari → ogohlantirish darajasi → operatsiya qilgan jarrohga xabar.

Xabarda faqat psevdonim (patient_ref) — shaxsiy ma'lumot Telegram'ga chiqmaydi.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from core.evidence import Evidence, RiskLevel, risk_rank

log = logging.getLogger("cardiopath.guardian")


class Alert(str, Enum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


PATIENT_MESSAGES = {
    Alert.GREEN: "Rahmat! Ko'rsatkichlaringiz qabul qilindi.",
    Alert.AMBER: "Ma'lumotlaringiz shifokoringizga yuborildi. Bugun siz bilan bog'lanishadi.",
    Alert.RED: "Shifokoringiz darhol xabardor qilindi. Ahvolingiz og'ir bo'lsa, kutmasdan 103 ga qo'ng'iroq qiling.",
}


@dataclass
class Escalation:
    alert: Alert
    reasons: list[str] = field(default_factory=list)
    patient_message: str = ""
    notified: bool = False
    message: str = ""                 # jarrohga ketgan matn — yetkazilmasa, qayta yuborish uchun saqlanadi

    def to_dict(self) -> dict:
        return {"alert": self.alert.value, "reasons": self.reasons,
                "patient_message": self.patient_message, "notified": self.notified}


class Notifier(Protocol):
    def send(self, text: str) -> bool: ...


class LogNotifier:
    is_external: bool = False

    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, text: str) -> bool:
        self.sent.append(text)
        log.warning("GUARDIAN ALERT: %s", text)
        return True


class TelegramNotifier:
    is_external: bool = True

    """CARDIOPATH_TG_TOKEN + CARDIOPATH_TG_CHAT (jarroh yoki navbatchi guruh)."""

    def __init__(self, token: str, chat_id: str) -> None:
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.chat_id = chat_id

    @classmethod
    def from_env(cls) -> "TelegramNotifier | None":
        token, chat = os.environ.get("CARDIOPATH_TG_TOKEN"), os.environ.get("CARDIOPATH_TG_CHAT")
        return cls(token, chat) if token and chat else None

    def send(self, text: str) -> bool:
        import httpx

        try:
            r = httpx.post(self.url, json={"chat_id": self.chat_id, "text": text}, timeout=10)
            return r.status_code == 200
        except httpx.HTTPError as exc:
            log.error("Telegram xabari yuborilmadi: %s", exc)
            return False

class SmsNotifier:
    is_external: bool = True

    """Kasalxona favqulodda SMS shlyuzi (Eskiz / PlayMobile yoki umumiy HTTP SMS API).
    Muhit: CARDIOPATH_SMS_URL, CARDIOPATH_SMS_PHONE, CARDIOPATH_SMS_TOKEN
    """

    def __init__(self, url: str, phone: str, token: str = "") -> None:
        self.url = url
        self.phone = phone
        self.token = token

    @classmethod
    def from_env(cls) -> Optional["SmsNotifier"]:
        url = os.environ.get("CARDIOPATH_SMS_URL")
        phone = os.environ.get("CARDIOPATH_SMS_PHONE")
        token = os.environ.get("CARDIOPATH_SMS_TOKEN", "")
        if url and phone:
            return cls(url, phone, token)
        return None

    def send(self, text: str) -> bool:
        import httpx

        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        payload = {"phone": self.phone, "message": text[:160]}
        try:
            r = httpx.post(self.url, json=payload, headers=headers, timeout=10)
            return r.status_code in (200, 201, 202)
        except Exception as exc:
            log.error("SMS yuborilmadi: %s", exc)
            return False


def build_notifier_from_env() -> Notifier:
    tg = TelegramNotifier.from_env()
    if tg is not None:
        return tg
    sms = SmsNotifier.from_env()
    if sms is not None:
        return sms
    return LogNotifier()



def escalate(patient_ref: str, day: int | None, items: list[Evidence], notifier: Notifier) -> Escalation:
    usable = [e for e in items if not e.abstained]
    abstained = [e for e in items if e.abstained]
    worst = max((risk_rank(e.risk) or 0 for e in usable), default=0)
    if worst >= risk_rank(RiskLevel.HIGH):
        alert = Alert.RED
    elif worst >= risk_rank(RiskLevel.MODERATE) or abstained:
        alert = Alert.AMBER      # o'qib bo'lmagan ma'lumot ham inson ko'rigiga
    else:
        alert = Alert.GREEN
    reasons = [f"{e.kind}: {'; '.join(e.explanation)}" for e in usable
               if (risk_rank(e.risk) or 0) >= risk_rank(RiskLevel.MODERATE)]
    reasons += [f"{e.kind}: o'qib bo'lmadi — {'; '.join(e.explanation)}" for e in abstained]
    esc = Escalation(alert, reasons, PATIENT_MESSAGES[alert])
    if alert != Alert.GREEN:
        head = "🔴 SHOSHILINCH" if alert == Alert.RED else "🟠 Bugun ko'rib chiqing"
        day_s = f", operatsiyadan keyin {day}-kun" if day is not None else ""
        esc.message = f"{head} — bemor {patient_ref}{day_s}\n" + "\n".join(f"• {r}" for r in reasons)
        esc.notified = notifier.send(esc.message)
    return esc

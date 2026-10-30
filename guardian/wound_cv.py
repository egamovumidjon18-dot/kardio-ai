"""Sternotomiya yarasi rasmidan infeksiya/ajralish aniqlash (CV) — BLOKLANGAN, o'qitilmagan. Faqat interfeys.

NIMA KERAK: izohlangan operatsiyadan keyingi sternotomiya yarasi rasmlari (kamida bir necha yuz, eritema/
ekssudat/dehissensiya yorliqlari bilan, bemor darajasida bo'lingan). Ochiq sternotomiya dataseti MAVJUD EMAS
(umumiy yara datasetlari — diabetik oyoq, bosim yaralari — boshqa to'qima/anatomiya, ko'chirib bo'lmaydi).
Yo'l: Guardian orqali rozilik bilan yig'ilgan rasmlar (`photo_ref`) + jarroh yorlig'i → keyin o'qitish.

Hozir: yara bo'yicha qaror faqat so'rovnoma qoidalari (`guardian/checkin.py`) va jarroh rasmni ko'rishi orqali.
"""
from __future__ import annotations

from core.evidence import Evidence, Provenance, Source

BLOCKED_REASON = ("Yara rasmi CV modeli mavjud emas: ochiq sternotomiya dataseti yo'q. Rasm jarrohga yuboriladi, "
                  "qaror so'rovnoma qoidalari va jarroh ko'rigi asosida.")


class WoundImageModel:
    available = False

    def analyze(self, *_, **__) -> Evidence:
        return Evidence.abstain("guardian.wound_image", Source.MODEL,
                                Provenance(name="wound_cv", version="blocked", reference="ochiq dataset yo'q"),
                                BLOCKED_REASON)

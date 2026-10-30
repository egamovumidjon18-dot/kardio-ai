"""AI-EKG orqali past EF (LVEF ≤40%) skrining — BLOKLANGAN, o'qitilmagan. Faqat interfeys.

NIMA KERAK:
  * juftlangan EKG + ExoKG-EF yorliqlari. Ochiq variant: MIMIC-IV-ECHO + MIMIC-IV-ECG — ikkalasi PhysioNet
    credentialed (CITI kursi + ma'lumotdan foydalanish shartnomasi + muassasa/rahbar ma'lumotnomasi). Hozir
    bu ruxsat yo'q, shuning uchun model O'QITILMAGAN va hech qanday natija uydirilmaydi;
  * muqobil: o'z klinikangizda ExoKG bilan tasdiqlangan ~1–2 ming EKG (rozilik bilan, `research/export_local.py` kabi oqim).
Pipeline tayyor bo'lganda: `ecg.signal.preprocess` + shu klass ichida ONNX backend + `DATASET_LICENSES["MIMIC-IV-ECHO"]`
(commercial_use=False) — product rejimida avtomatik bloklanadi.
"""
from __future__ import annotations

from core.evidence import Evidence, Provenance, Source

BLOCKED_REASON = ("AI-EKG past EF modeli mavjud emas: o'qitish uchun MIMIC-IV-ECHO/ECG (PhysioNet credentialed) kerak, "
                  "ruxsat hali yo'q. EF'ni ExoKG o'lchaydi.")


class LowEFFromECG:
    available = False

    def analyze(self, *_, **__) -> Evidence:
        return Evidence.abstain("ecg.low_ef", Source.MODEL,
                                Provenance(name="ecg_low_ef", version="blocked", reference="MIMIC-IV-ECHO (credentialed)"),
                                BLOCKED_REASON)

"""Concordance — deterministik qoida va AI natijasini yonma-yon qo'yish.

Xavfsizlik falsafasi shu yerda kodlanadi:
  * DISAGREE yashirilmaydi — shifokor muhokamasi uchun majburiy punkt.
  * AI xavfni faqat OSHIRA oladi; qoida bergan xavfni hech qachon pasaytirmaydi.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core.evidence import Evidence, RiskLevel, risk_rank


class Agreement(str, Enum):
    AGREE = "agree"
    DISAGREE = "disagree"
    AI_ABSTAINED = "ai_abstained"
    RULE_ONLY = "rule_only"        # AI moduli umuman yo'q / ulanmagan
    NOT_COMPARABLE = "not_comparable"  # ikkala natija bor, lekin solishtirib bo'lmaydi (masalan, turli vaqtdagi o'lchovlar)


@dataclass
class ConcordanceResult:
    question: str
    status: Agreement
    rule: Evidence
    ai: Optional[Evidence]
    final_risk: RiskLevel
    message: str

    @property
    def needs_discussion(self) -> bool:
        return self.status in (Agreement.DISAGREE, Agreement.AI_ABSTAINED)

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "status": self.status.value,
            "needs_discussion": self.needs_discussion,
            "final_risk": self.final_risk.value,
            "rule": self.rule.to_dict(),
            "ai": self.ai.to_dict() if self.ai else None,
            "message": self.message,
        }


def compare(question: str, rule: Evidence, ai: Optional[Evidence], tolerance: int = 0) -> ConcordanceResult:
    """Ikki trekni xavf toifasi bo'yicha solishtiradi.

    tolerance — nechta qo'shni toifa farqi hali "mos" hisoblanadi (default: 0, qat'iy).
    final_risk — max(qoida, AI): AI faqat eskalatsiya qiladi.
    """
    if ai is None:
        return ConcordanceResult(question, Agreement.RULE_ONLY, rule, None, rule.risk,
                                 "AI natijasi yo'q (ma'lumot yuklanmagan yoki model ulanmagan) — faqat deterministik qoida.")
    r, a = risk_rank(rule.risk), risk_rank(ai.risk)
    if ai.abstained or a is None:
        reason = "; ".join(ai.explanation) or "ishonch past"
        return ConcordanceResult(question, Agreement.AI_ABSTAINED, rule, ai, rule.risk,
                                 f"AI xulosa bermadi ({reason}) — qoida natijasini shifokor baholaydi.")
    if r is None:
        return ConcordanceResult(question, Agreement.DISAGREE, rule, ai, ai.risk,
                                 "Qoida toifasi aniqlanmadi — faqat AI natijasi bor, shifokor tekshiradi.")
    final = rule.risk if r >= a else ai.risk
    if abs(r - a) <= tolerance:
        return ConcordanceResult(question, Agreement.AGREE, rule, ai, final,
                                 f"Qoida va AI mos: {rule.risk.value}.")
    direction = "yuqoriroq" if a > r else "pastroq"
    return ConcordanceResult(question, Agreement.DISAGREE, rule, ai, final,
                             f"ZIDDIYAT: qoida {rule.risk.value}, AI {ai.risk.value} ({direction}). "
                             f"Yakuniy xavf {final.value} (AI hech qachon pasaytirmaydi). Muhokama majburiy.")

"""Taxminiy QFR — angiografik o'lchovlardan oddiy gidrodinamik formula (TASDIQLANMAGAN).

Poiseuille + Bernulli formulasi bilan stenozdagi bosim tushishi taxmin qilinadi.
Tomirdagi qon oqimi o'lchanmaydi — jadvaldagi o'rtacha qiymatdan olinadi.

MUHIM: bu FAVOR II/III tadqiqotlarida tekshirilgan QFR usuli EMAS (u 3D angiografik
qayta tiklash va kadrlardan o'lchangan oqimga asoslanadi). Bu formula invaziv FFR/iFR
bilan solishtirilmagan. Shuning uchun:
  * natija hech qachon «me'yor» yoki «xavfsiz» deb ko'rsatilmaydi va xavfni pasaytirmaydi;
  * stenoz foizi (%DS) bo'yicha xavf darajasi formuladan qat'i nazar saqlanadi;
  * davolash tavsiyasi (stent, CABG, dori) berilmaydi — qaror yurak jamoasiniki.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Optional

from core.evidence import Evidence, Provenance, RiskLevel, Source

QFR_REFERENCE = "Poiseuille + Bernulli taxminiy formulasi (FAVOR QFR usuli emas; invaziv FFR bilan tekshirilmagan)"
QFR_PROV = Provenance(
    name="virtual_qfr_hemodynamics",
    version="2026.11.03",
    reference=QFR_REFERENCE,
    dataset_license="fizik formula; klinik validatsiya yo'q",
)

# Qonning fizik konstantalari (37°C haroratda)
BLOOD_VISCOSITY_PA_S = 0.0035       # Dinamik qovushqoqlik (Pa*s)
BLOOD_DENSITY_KG_M3 = 1050.0        # Zichlik (kg/m³)
MEAN_AORTIC_PRESSURE_MMHG = 90.0    # O'rtacha me'yoriy aorta bosimi (Pa = mmHg * 133.322)
PA_IN_PASCALS = MEAN_AORTIC_PRESSURE_MMHG * 133.322

# Tomir turiga ko'ra me'yoriy giperemik qon oqimi (mL/s)
VESSEL_FLOW_RATES = {
    "LMS": 2.2,         # Chap asosiy poya (umumiy oqim)
    "LAD": 1.2,         # Chap oldingi tushuvchi arteriya
    "LAD_PROX": 1.2,
    "LAD_MID_DIST": 0.9,
    "LCX": 0.9,         # O'rab oluvchi arteriya
    "RCA": 1.0,         # O'ng toj arteriya
    "DIAGONAL": 0.5,
    "OM": 0.5,
}


@dataclass
class QfrInput:
    vessel: str                             # LMS, LAD, LAD_PROX, LCX, RCA...
    reference_diameter_mm: float            # Referens normal tomir diametri (masalan, 3.2 mm)
    minimal_lumen_diameter_mm: float        # Minimal toraygan lümen diametri - MLD (masalan, 1.1 mm)
    lesion_length_mm: float                 # Stenoz uzunligi (masalan, 15.0 mm)
    aortic_pressure_mmhg: float = 90.0      # O'lchangan aorta bosimi (mmHg)
    timi_frame_count: Optional[float] = None # Angiografik kontrast tezligi (ixtiyoriy)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QfrResult:
    qfr: float                              # Hisoblangan QFR indeksi (0.00 - 1.00)
    percent_diameter_stenosis: float        # Diametr bo'yicha torayish foizi (%DS)
    percent_area_stenosis: float            # Maydon bo'yicha torayish foizi (%AS)
    pressure_drop_mmhg: float               # Stenozdagi bosim yo'qotilishi (mmHg)
    is_ischemic: bool                       # Ishemiya mavjudligi (QFR <= 0.80)
    clinical_recommendation: str            # izoh (davolash tavsiyasi EMAS)
    risk_level: RiskLevel                   # Xavf darajasi

    def to_dict(self) -> dict:
        return {
            "qfr": round(self.qfr, 3),
            "percent_diameter_stenosis": round(self.percent_diameter_stenosis, 1),
            "percent_area_stenosis": round(self.percent_area_stenosis, 1),
            "pressure_drop_mmhg": round(self.pressure_drop_mmhg, 2),
            "is_ischemic": self.is_ischemic,
            "clinical_recommendation": self.clinical_recommendation,
            "risk_level": self.risk_level.value,
        }


def calculate_virtual_qfr(inp: QfrInput) -> QfrResult:
    """Angiografik o'lchovlardan virtual QFR indeksini hisoblaydi."""
    d_ref = max(0.5, inp.reference_diameter_mm)
    mld = max(0.1, min(inp.minimal_lumen_diameter_mm, d_ref))
    length = max(1.0, inp.lesion_length_mm)
    pa_mmhg = max(50.0, inp.aortic_pressure_mmhg)
    pa_pascals = pa_mmhg * 133.322

    # 1. Geometrik torayish ko'rsatkichlari
    pct_ds = (1.0 - (mld / d_ref)) * 100.0
    pct_as = (1.0 - (mld**2 / d_ref**2)) * 100.0

    # 2. Gidrodinamik oqimni aniqlash (m³/s ga o'tkazish: 1 mL/s = 1e-6 m³/s)
    base_flow_ml_s = VESSEL_FLOW_RATES.get(inp.vessel.upper(), 1.0)
    # Agar tomir ingichka bo'lsa (Murray qonuniga ko'ra oqim r^3 ga mutanosib)
    murray_factor = min(1.5, max(0.4, (d_ref / 3.0)**2.5))
    flow_m3_s = base_flow_ml_s * murray_factor * 1e-6

    # Metrga o'tkazish
    mld_m = mld * 1e-3
    d_ref_m = d_ref * 1e-3
    length_m = length * 1e-3

    # 3. Navier-Stokes Poiseuille qovushqoq bosim tushishi (ΔPv)
    # ΔPv = (128 * μ * L) / (π * MLD⁴) * Q
    delta_p_viscous = (128.0 * BLOOD_VISCOSITY_PA_S * length_m * flow_m3_s) / (math.pi * (mld_m**4))

    # 4. Bernulli turbulent kengayish yo'qotishi (ΔPe)
    # ΔPe = (8 * ρ / π²) * (1/MLD² - 1/Dref²)² * Q²
    expansion_term = (1.0 / (mld_m**2) - 1.0 / (d_ref_m**2))
    delta_p_expansion = (8.0 * BLOOD_DENSITY_KG_M3 / (math.pi**2)) * (expansion_term**2) * (flow_m3_s**2)

    total_delta_p_pa = delta_p_viscous + delta_p_expansion
    total_delta_p_mmhg = total_delta_p_pa / 133.322

    # 5. QFR hisoblash: QFR = 1.0 - (ΔP / Pa)
    qfr_val = max(0.10, min(1.00, 1.0 - (total_delta_p_pa / pa_pascals)))

    # 6. Xavf darajasi. Formula tasdiqlanmagan — u xavfni faqat OSHIRISHI mumkin, pasaytira olmaydi.
    is_ischemic = qfr_val <= 0.80
    vessel = inp.vessel.upper()
    # Anatomik pol: stenoz foizi bo'yicha (ESC — chap asosiy poyada >=50% ahamiyatli)
    if vessel == "LMS" and pct_ds >= 50.0:
        floor = RiskLevel.HIGH
    elif pct_ds >= 70.0:
        floor = RiskLevel.HIGH
    elif pct_ds >= 50.0:
        floor = RiskLevel.MODERATE
    else:
        floor = RiskLevel.UNKNOWN
    if qfr_val <= 0.75:
        calc = RiskLevel.VERY_HIGH
    elif qfr_val <= 0.80:
        calc = RiskLevel.HIGH
    elif qfr_val <= 0.85:
        calc = RiskLevel.MODERATE
    else:
        calc = RiskLevel.UNKNOWN          # formula ishemiyani istisno qila olmaydi
    order = [RiskLevel.UNKNOWN, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.VERY_HIGH]
    risk = max(floor, calc, key=order.index)

    decide = ("Davolash qarori invaziv FFR/iFR yoki tasdiqlangan QFR dasturi, klinik belgilar "
              "va yurak jamoasi (Heart Team) bilan qabul qilinadi.")
    if risk == RiskLevel.UNKNOWN:
        rec = ("Taxminiy hisob bosim tushishini kichik ko'rsatdi, lekin bu formula tasdiqlanmagan va "
               "ishemiyani istisno qila OLMAYDI. " + decide)
    elif calc in (RiskLevel.HIGH, RiskLevel.VERY_HIGH):
        rec = "Taxminiy hisob ishemiya ehtimolini ko'rsatadi (tasdiqlanmagan formula). " + decide
    else:
        rec = ("Stenoz darajasi yoki taxminiy hisob e'tibor talab qiladi (tasdiqlanmagan formula). " + decide)
    if vessel == "LMS" and pct_ds >= 50.0:
        rec = "Chap asosiy poyada ≥50% torayish — anatomik jihatdan ahamiyatli. " + rec

    return QfrResult(
        qfr=qfr_val,
        percent_diameter_stenosis=pct_ds,
        percent_area_stenosis=pct_as,
        pressure_drop_mmhg=total_delta_p_mmhg,
        is_ischemic=is_ischemic,
        clinical_recommendation=rec,
        risk_level=risk,
    )


def assess_qfr_evidence(inp: QfrInput) -> Evidence:
    """QFR tahlilini o'tkazib, standart Evidence ob'yektini shakllantiradi."""
    res = calculate_virtual_qfr(inp)

    expl = [
        f"Taxminiy QFR = {res.qfr:.2f} (TASDIQLANMAGAN formula; me'yorni tasdiqlamaydi)",
        f"Stenoz darajasi: %DS={res.percent_diameter_stenosis:.1f}%, %AS={res.percent_area_stenosis:.1f}% (Bosim yo'qotilishi: ΔP={res.pressure_drop_mmhg:.1f} mmHg)",
        res.clinical_recommendation,
    ]

    return Evidence(
        kind="angio.qfr",
        value=res.to_dict(),
        source=Source.MODEL,
        provenance=QFR_PROV,
        risk=res.risk_level,
        explanation=expl,
    )

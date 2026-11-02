"""ExoKG Dopler gemodinamikasi va yurak qopqoqlari patologiyasi (Valvular Heart Disease).

Klinik asos:
  * 2021 ESC/EACTS Guidelines for the management of valvular heart disease;
  * ASE/EACVI 2020 Recommendations for the Evaluation of Valvular Regurgitation.

Baholanadigan ko'rsatkichlar:
  1. Aortal stenoz (AS): Vmax (m/s), o'rtacha gradient (mmHg), aortal qopqoq maydoni (AVA cm²);
  2. Mitral yetishmovchilik (MR): EROA (mm²), regürgitatsiya hajmi (ml), vena contracta (mm);
  3. Aortal yetishmovchilik (AR): PHT (ms), vena contracta (mm), tushuvchi aortada golodiastolik oqim;
  4. Triksupid regürgitatsiyasi (TR) va o'pka gipertenziyasi: TR Vmax orqali sPAP hisoblash (Bernulli tenglamasi).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.evidence import Evidence, Provenance, RiskLevel, Source

REFERENCE = "2021 ESC/EACTS Valvular Heart Disease Guidelines; ASE/EACVI 2020"


@dataclass
class ValvularEchoInput:
    # Aortal Stenoz (AS)
    as_vmax: Optional[float] = None             # m/s
    as_mean_gradient: Optional[float] = None    # mmHg
    as_ava: Optional[float] = None              # cm²
    
    # Mitral Regürgitatsiya (MR)
    mr_eroa: Optional[float] = None             # mm²
    mr_reg_vol: Optional[float] = None          # ml
    mr_vena_contracta: Optional[float] = None   # mm
    mr_etiology: str = "primary"                # "primary" | "secondary"
    
    # Aortal Regürgitatsiya (AR)
    ar_pht: Optional[float] = None              # ms (Pressure Half-Time)
    ar_vena_contracta: Optional[float] = None   # mm
    ar_holodiastolic_reversal: bool = False
    
    # Triksupid va o'pka bosimi (sPAP)
    tr_vmax: Optional[float] = None             # m/s
    rap: float = 5.0                            # mmHg (o'ng bo'lmacha bosimi, default 5)
    
    # Chap qorincha otib berish fraksiyasi (LVEF)
    lvef: Optional[float] = None                # %


def _prov() -> Provenance:
    return Provenance(
        name="echocardiography_valves",
        version="esc-eacts-2021",
        reference=REFERENCE,
    )


def evaluate_valvular_echo(inp: ValvularEchoInput) -> Evidence:
    prov = _prov()
    
    # Biologik ehtimolli oraliqlarni tekshirish (Plausibility checks)
    if inp.as_vmax is not None and not (0.5 <= inp.as_vmax <= 8.0):
        return Evidence.abstain("echo.valves", Source.CLINICIAN, prov, f"Aortal Vmax biologik oraliqdan tashqarida: {inp.as_vmax} m/s [0.5-8.0]")
    if inp.as_mean_gradient is not None and not (0.0 <= inp.as_mean_gradient <= 160.0):
        return Evidence.abstain("echo.valves", Source.CLINICIAN, prov, f"Aortal o'rtacha gradient noaniq: {inp.as_mean_gradient} mmHg [0-160]")
    if inp.as_ava is not None and not (0.1 <= inp.as_ava <= 6.0):
        return Evidence.abstain("echo.valves", Source.CLINICIAN, prov, f"Aortal qopqoq maydoni (AVA) noaniq: {inp.as_ava} cm² [0.1-6.0]")
    if inp.tr_vmax is not None and not (0.5 <= inp.tr_vmax <= 6.5):
        return Evidence.abstain("echo.valves", Source.CLINICIAN, prov, f"TR Vmax biologik oraliqdan tashqarida: {inp.tr_vmax} m/s [0.5-6.5]")
    if inp.rap not in (0.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0):
        if not (0.0 <= inp.rap <= 30.0):
            return Evidence.abstain("echo.valves", Source.CLINICIAN, prov, f"O'ng bo'lmacha bosimi (RAP) noaniq: {inp.rap} mmHg [0-30]")

    findings: dict = {
        "aortic_stenosis": {"grade": "none", "severe": False},
        "mitral_regurgitation": {"grade": "none", "severe": False},
        "aortic_regurgitation": {"grade": "none", "severe": False},
        "pulmonary_hypertension": {"spap_mmhg": None, "grade": "none", "severe": False},
    }
    expl: list[str] = []
    risks: list[RiskLevel] = [RiskLevel.LOW]

    # 1. Aortal Stenoz (AS)
    as_severe = False
    as_grade = "none"
    if inp.as_vmax is not None or inp.as_mean_gradient is not None or inp.as_ava is not None:
        vmax = inp.as_vmax or 0.0
        grad = inp.as_mean_gradient or 0.0
        ava = inp.as_ava

        if vmax >= 4.0 or grad >= 40.0 or (ava is not None and ava <= 1.0):
            as_severe = True
            if ava is not None and ava <= 1.0 and grad < 40.0 and inp.lvef is not None and inp.lvef < 50.0:
                as_grade = "severe_lflg"
                expl.append(f"Og'ir past oqimli past gradientli aortal stenoz (LFLG-AS: AVA={ava} cm², MeanGrad={grad} mmHg, EF={inp.lvef}%)")
            else:
                as_grade = "severe"
                expl.append(f"Og'ir aortal stenoz (Vmax={vmax:.1f} m/s, MeanGrad={grad:.0f} mmHg" + (f", AVA={ava:.2f} cm²" if ava else "") + ") — SAVR yoki TAVI ko'rsatmasi")
            risks.append(RiskLevel.VERY_HIGH)
        elif vmax >= 3.0 or grad >= 20.0 or (ava is not None and ava <= 1.5):
            as_grade = "moderate"
            expl.append(f"O'rtacha aortal stenoz (Vmax={vmax:.1f} m/s, MeanGrad={grad:.0f} mmHg)")
            risks.append(RiskLevel.MODERATE)
        elif vmax >= 2.0 or grad > 0.0 or (ava is not None and ava > 1.5):
            as_grade = "mild"
            expl.append(f"Yengil aortal stenoz (Vmax={vmax:.1f} m/s)")
            risks.append(RiskLevel.LOW)

    findings["aortic_stenosis"] = {"grade": as_grade, "severe": as_severe}

    # 2. Mitral Regürgitatsiya (MR)
    mr_severe = False
    mr_grade = "none"
    if inp.mr_eroa is not None or inp.mr_reg_vol is not None or inp.mr_vena_contracta is not None:
        eroa = inp.mr_eroa or 0.0
        rvol = inp.mr_reg_vol or 0.0
        vc = inp.mr_vena_contracta or 0.0
        is_secondary = (inp.mr_etiology == "secondary")

        # ESC 2021: Primary vs Secondary mezonlari
        severe_primary = (eroa >= 40.0 or rvol >= 60.0 or vc >= 7.0)
        severe_secondary = is_secondary and (eroa >= 20.0 or rvol >= 30.0)

        if severe_primary or severe_secondary:
            mr_severe = True
            mr_grade = "severe"
            expl.append(f"Og'ir mitral yetishmovchilik ({inp.mr_etiology}: " +
                        (f"EROA={eroa:.1f} mm², " if inp.mr_eroa else "") +
                        (f"RegVol={rvol:.0f} ml, " if inp.mr_reg_vol else "") +
                        (f"VC={vc:.1f} mm" if inp.mr_vena_contracta else "") + ")")
            risks.append(RiskLevel.VERY_HIGH)
        elif eroa >= 20.0 or rvol >= 30.0 or vc >= 3.0:
            mr_grade = "moderate"
            expl.append("O'rtacha mitral yetishmovchilik")
            risks.append(RiskLevel.MODERATE)
        else:
            mr_grade = "mild"
            expl.append("Yengil mitral yetishmovchilik")
            risks.append(RiskLevel.LOW)

    findings["mitral_regurgitation"] = {"grade": mr_grade, "severe": mr_severe, "etiology": inp.mr_etiology}

    # 3. Aortal Regürgitatsiya (AR)
    ar_severe = False
    ar_grade = "none"
    if inp.ar_pht is not None or inp.ar_vena_contracta is not None or inp.ar_holodiastolic_reversal:
        pht = inp.ar_pht
        vc = inp.ar_vena_contracta or 0.0
        reversal = inp.ar_holodiastolic_reversal

        if (pht is not None and pht < 200.0) or vc > 6.0 or reversal:
            ar_severe = True
            ar_grade = "severe"
            expl.append("Og'ir aortal yetishmovchilik (PHT < 200 ms yoki VC > 6 mm yoki aortada golodiastolik oqim)")
            risks.append(RiskLevel.VERY_HIGH)
        elif (pht is not None and pht <= 500.0) or vc >= 3.0:
            ar_grade = "moderate"
            expl.append("O'rtacha aortal yetishmovchilik")
            risks.append(RiskLevel.MODERATE)
        else:
            ar_grade = "mild"
            expl.append("Yengil aortal yetishmovchilik")
            risks.append(RiskLevel.LOW)

    findings["aortic_regurgitation"] = {"grade": ar_grade, "severe": ar_severe}

    # 4. Triksupid Regürgitatsiyasi va sPAP (O'pka Gipertenziyasi)
    if inp.tr_vmax is not None:
        # Bernulli tenglamasi: sPAP = 4 * Vtr^2 + RAP
        spap = round(4.0 * (inp.tr_vmax ** 2) + inp.rap, 1)
        findings["pulmonary_hypertension"]["spap_mmhg"] = spap

        if spap > 50.0:
            ph_grade = "severe"
            findings["pulmonary_hypertension"]["severe"] = True
            findings["pulmonary_hypertension"]["grade"] = "severe"
            expl.append(f"Og'ir o'pka gipertenziyasi (sPAP={spap:.0f} mmHg > 50) — EuroSCORE II yuqori xavf omili")
            risks.append(RiskLevel.VERY_HIGH)
        elif spap > 35.0:
            findings["pulmonary_hypertension"]["grade"] = "moderate"
            expl.append(f"O'rtacha o'pka gipertenziyasi (sPAP={spap:.0f} mmHg)")
            risks.append(RiskLevel.HIGH)
        else:
            findings["pulmonary_hypertension"]["grade"] = "normal_or_mild"
            expl.append(f"O'pka arteriyasi bosimi me'yorda (sPAP={spap:.0f} mmHg)")
            risks.append(RiskLevel.LOW)

    if not expl:
        expl.append("Klapanlar patologiyasi yoki o'pka gipertenziyasi aniqlanmadi (me'yor)")

    # Max risk level
    final_risk = max(risks, key=lambda r: ["low", "moderate", "high", "very_high"].index(r.value))

    return Evidence(
        kind="echo.valves",
        source=Source.CLINICIAN,
        provenance=prov,
        risk=final_risk,
        value=findings,
        explanation=expl,
    )

"""12 tarmoqli EKG signallaridan asosiy elektrokardiografik intervallarni o'lchash.

O'lchanadigan ko'rsatkichlar:
  * Yurak urishi chastotasi (HR, BPM) va RR oralig'i (ms);
  * PR oralig'i (me'yorda: 120–200 ms; >200 ms: 1-darajali AV-blokada; <120 ms: qisqargan PR / WPW);
  * QRS davomiyligi (me'yorda: 70–110 ms; ≥120 ms: Giss tutami oyoqchalari blokadasi);
  * QT va korreksiyalangan QTc (Bazett va Fridericia bo'yicha).

Xavf darajalari:
  * LOW: barcha intervallar me'yorda;
  * MODERATE: mo''tadil taxikardiya/bradikardiya, chegaradagi QTc (450–480 ms), 1-darajali AV-blokada, QRS 110–120 ms;
  * HIGH / VERY_HIGH: kritik QTc uzayishi (≥480 ms ayollarda, ≥470 ms erkaklarda yoki umumiy ≥500 ms — Torsades de Pointes xavfi), og'ir bradikardiya (<40 bpm) yoki keng QRS (≥140 ms).
"""
from __future__ import annotations

from typing import Optional
import numpy as np

from core.evidence import Evidence, Provenance, RiskLevel, Source, risk_rank

REFERENCE = "AHA/ACCF/HRS Recommendations for the Standardization and Interpretation of the Electrocardiogram (2009)"


def _worse_risk(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    return a if (risk_rank(a) or 0) >= (risk_rank(b) or 0) else b


def detect_r_peaks(lead: np.ndarray, fs: float) -> np.ndarray:
    """1D EKG signalidan R cho'qqilarini aniqlash (Pan-Tompkins modifikatsiyasi)."""
    N = len(lead)
    if N < int(fs * 2.0):
        return np.array([], dtype=int)

    # 1-tartibli hosila
    diff = np.diff(lead, prepend=lead[0])
    # Kvadratga oshirish (energiya)
    squared = diff ** 2
    # Sirpanuvchi integrallash oynasi (~120 ms)
    win_len = max(3, int(0.12 * fs))
    kernel = np.ones(win_len) / win_len
    mwi = np.convolve(squared, kernel, mode="same")

    # Adaptiv chegara
    th = float(np.mean(mwi) + 1.0 * np.std(mwi))
    peaks: list[int] = []
    min_dist = int(0.28 * fs)  # Maksimal 210 bpm

    i = 0
    while i < N:
        if mwi[i] > th:
            w_start = max(0, i - int(0.08 * fs))
            w_end = min(N, i + int(0.15 * fs))
            local_r = w_start + int(np.argmax(lead[w_start:w_end]))
            if not peaks or (local_r - peaks[-1] >= min_dist):
                peaks.append(local_r)
            elif lead[local_r] > lead[peaks[-1]]:
                peaks[-1] = local_r
            i = w_end
        else:
            i += 1

    return np.array(peaks, dtype=int)


def _lead_for_intervals(signal: np.ndarray, leads: tuple[str, ...]) -> np.ndarray:
    """Intervallarni o'lchash uchun eng yaxshi tarmoqni tanlash (II > V5 > I > 0)."""
    leads_upper = [l.upper() for l in leads]
    for pref in ("II", "V5", "I", "V4"):
        if pref in leads_upper:
            idx = leads_upper.index(pref)
            return signal[idx]
    return signal[0]


def measure_intervals(signal: np.ndarray, fs: float, leads: tuple[str, ...] = ("II",),
                      gender: str = "unknown") -> Evidence:
    """12 tarmoqli (yoki bitta tarmoqli) EKG signalidan intervallarni o'lchaydi."""
    prov = Provenance(name="ecg_intervals", version="1.0", reference=REFERENCE)
    kind = "ecg.intervals"

    if signal.ndim == 1:
        lead = signal
    else:
        lead = _lead_for_intervals(signal, leads)

    r_peaks = detect_r_peaks(lead, fs)
    if len(r_peaks) < 3:
        return Evidence.abstain(kind, Source.RULE, prov, "R-cho'qqilar yetarli emas (kamida 3 ta zarba kerak)")

    rr_s = np.diff(r_peaks) / fs
    median_rr = float(np.median(rr_s))
    if median_rr <= 0:
        return Evidence.abstain(kind, Source.RULE, prov, "RR oralig'i noto'g'ri")

    hr = 60.0 / median_rr
    qrs_list: list[float] = []
    pr_list: list[float] = []
    qt_list: list[float] = []

    for r in r_peaks[1:-1]:
        # QRS onset: R cho'qqidan oldingi minimal nuqta (Q)
        pre_win = max(0, r - int(0.08 * fs))
        q_idx = pre_win + int(np.argmin(lead[pre_win:r])) if r > pre_win else r

        # QRS offset: R cho'qqidan keyingi S minimal nuqtasi yoki J nuqtasi
        post_win = min(len(lead), r + int(0.10 * fs))
        s_idx = r + int(np.argmin(lead[r:post_win])) if post_win > r else r

        qrs_ms = (s_idx - q_idx) / fs * 1000.0
        if 40 <= qrs_ms <= 220:
            qrs_list.append(qrs_ms)

        # P to'lqin: Q nuqtasidan 60ms dan 260ms gacha oldingi oraliq
        p_start = max(0, q_idx - int(0.26 * fs))
        p_end = max(0, q_idx - int(0.06 * fs))
        if p_end > p_start:
            p_idx = p_start + int(np.argmax(lead[p_start:p_end]))
            pr_ms = (q_idx - p_start) / fs * 1000.0
            if 80 <= pr_ms <= 360:
                pr_list.append(pr_ms)

        # T to'lqin offset: S dan keyin 450 ms gacha
        t_start = s_idx + int(0.05 * fs)
        t_end = min(len(lead), r + int(min(0.55 * median_rr, 0.52) * fs))
        if t_end > t_start:
            t_peak = t_start + int(np.argmax(lead[t_start:t_end]))
            t_end_idx = min(len(lead), t_peak + int(0.08 * fs))
            qt_ms = (t_end_idx - q_idx) / fs * 1000.0
            if 250 <= qt_ms <= 650:
                qt_list.append(qt_ms)

    qrs = round(float(np.median(qrs_list)), 1) if qrs_list else None
    pr = round(float(np.median(pr_list)), 1) if pr_list else None
    qt = round(float(np.median(qt_list)), 1) if qt_list else None

    qtc_b = round(float(qt / np.sqrt(median_rr)), 1) if (qt and median_rr > 0) else None
    qtc_f = round(float(qt / (median_rr ** (1.0 / 3.0))), 1) if (qt and median_rr > 0) else None

    findings: list[str] = []
    risk = RiskLevel.LOW

    # 1. Yurak urish tezligi baholash
    if hr > 140:
        findings.append(f"Og'ir taxikardiya: {hr:.0f} zarba/daq")
        risk = _worse_risk(risk, RiskLevel.HIGH)
    elif hr > 100:
        findings.append(f"Sinus taxikardiyasi: {hr:.0f} zarba/daq")
        risk = _worse_risk(risk, RiskLevel.MODERATE)
    elif hr < 40:
        findings.append(f"Og'ir bradikardiya: {hr:.0f} zarba/daq")
        risk = _worse_risk(risk, RiskLevel.HIGH)
    elif hr < 50:
        findings.append(f"Sinus bradikardiyasi: {hr:.0f} zarba/daq")
        risk = _worse_risk(risk, RiskLevel.MODERATE)
    else:
        findings.append(f"Yurak urishi me'yorda: {hr:.0f} zarba/daq")

    # 2. QTc baholash
    qtc_ref = qtc_b or qtc_f
    if qtc_ref is not None:
        female = (gender.lower() in ("female", "ayol", "f"))
        threshold_high = 480.0 if female else 470.0
        if qtc_ref >= 500.0:
            findings.append(f"Kritik QTc uzayishi (QTc={qtc_ref:.0f} ms ≥ 500 ms) — Torsades de Pointes xavfi yuqori")
            risk = _worse_risk(risk, RiskLevel.HIGH)
        elif qtc_ref >= threshold_high:
            findings.append(f"QTc uzaygan (QTc={qtc_ref:.0f} ms, chegara: {threshold_high:.0f} ms)")
            risk = _worse_risk(risk, RiskLevel.HIGH)
        elif qtc_ref >= 450.0:
            findings.append(f"Chegaradagi QTc (QTc={qtc_ref:.0f} ms)")
            risk = _worse_risk(risk, RiskLevel.MODERATE)
        else:
            findings.append(f"QTc me'yorda (QTc={qtc_ref:.0f} ms)")

    # 3. QRS kengligi baholash
    if qrs is not None:
        if qrs >= 140.0:
            findings.append(f"Aniq QRS kengayishi ({qrs:.0f} ms ≥ 140 ms) — qorincha ichi o'tkazuvchanligi buzilgan")
            risk = _worse_risk(risk, RiskLevel.HIGH)
        elif qrs >= 120.0:
            findings.append(f"Keng QRS ({qrs:.0f} ms ≥ 120 ms) — Giss oyoqchasi blokadasi ehtimoli")
            risk = _worse_risk(risk, RiskLevel.MODERATE)

    # 4. PR intervali baholash
    if pr is not None:
        if pr > 210.0:
            findings.append(f"1-darajali atrioventrikulyar blokada (PR={pr:.0f} ms > 210 ms)")
            risk = _worse_risk(risk, RiskLevel.MODERATE)
        elif pr < 110.0:
            findings.append(f"Qisqargan PR intervali (PR={pr:.0f} ms < 110 ms) — qo'shimcha o'tkazuvchi yo'llar ehtimoli")
            risk = _worse_risk(risk, RiskLevel.MODERATE)

    value = {
        "heart_rate_bpm": round(hr, 1),
        "rr_ms": round(median_rr * 1000.0, 1),
        "pr_ms": pr,
        "qrs_ms": qrs,
        "qt_ms": qt,
        "qtc_bazett_ms": qtc_b,
        "qtc_fridericia_ms": qtc_f,
        "n_beats_analyzed": len(r_peaks),
        "findings": findings,
    }

    return Evidence(
        kind=kind,
        value=value,
        source=Source.RULE,
        provenance=prov,
        risk=risk,
        explanation=findings,
    )

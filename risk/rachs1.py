"""RACHS-1 — tug'ma yurak nuqsonlari jarrohligida xavf toifasi (1–6), operatsiya turiga qarab.

Jenkins KJ et al. Consensus-based method for risk adjustment for surgery for congenital heart disease.
J Thorac Cardiovasc Surg 2002;123(1):110–118. doi:10.1067/mtc.2002.119064

Qoidalar (nashr bo'yicha):
  * har bir operatsiya o'z toifasiga ega; ba'zilari yoshga bog'liq (≤ 30 kun yoki > 30 kun);
  * bir nechta operatsiya bo'lsa — eng murakkabining (eng yuqori) toifasi olinadi;
  * ro'yxatda yo'q operatsiya → toifalab bo'lmaydi (abstain), shifokor baholaydi;
  * istisnolar: chala tug'ilgan chaqaloqda faqat arterial yo'lni yopish, yurak ko'chirib o'tkazish.
Asl kogortadagi (PCCC) kasalxona o'limi: 1 — 0.4%, 2 — 3.8%, 3 — 8.5%, 4 — 19.4%, 6 — 47.7% (5-toifa: holat kam).
Zamonaviy markazlarda o'lim ancha past (CHSS 2006: 0.7 / 0.9 / 2.7 / 7.7 / — / 17.2%), shuning uchun foizlar faqat
toifaning nisbiy og'irligini ko'rsatadi, bemorning shaxsiy xavfi EMAS.
Diqqat: operatsiyalar ro'yxati nashr ilovasidan olingan; klinik ishlatishdan oldin kardioxirurg asl jadval bilan solishtirishi kerak.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.evidence import Evidence, Provenance, RiskLevel, Source

REFERENCE = "Jenkins KJ et al. J Thorac Cardiovasc Surg 2002;123(1):110-118"
NEONATE_DAYS = 30
MORTALITY_2002 = {1: 0.4, 2: 3.8, 3: 8.5, 4: 19.4, 5: None, 6: 47.7}
MORTALITY_CHSS_2006 = {1: 0.7, 2: 0.9, 3: 2.7, 4: 7.7, 5: None, 6: 17.2}
LEVEL = {1: RiskLevel.LOW, 2: RiskLevel.MODERATE, 3: RiskLevel.HIGH, 4: RiskLevel.VERY_HIGH,
         5: RiskLevel.VERY_HIGH, 6: RiskLevel.VERY_HIGH}

# kod: (o'zbekcha nomi, toifa ≤ 30 kun, toifa > 30 kun); None — nashrda shu yosh uchun toifa berilmagan (abstain)
PROCEDURES: dict[str, tuple[str, Optional[int], int]] = {
    # 1-toifa
    "asd_repair": ("Bo'lmachalararo to'siq nuqsonini (ikkilamchi, sinus venosus, FOO) yopish", 1, 1),
    "aortopexy": ("Aortopeksiya", 1, 1),
    "pda_closure": ("Arterial (Botallo) yo'lni yopish", None, 1),
    "coarctation_repair": ("Aorta koarktatsiyasini tuzatish", 2, 1),
    "papvc_repair": ("Qisman anomal o'pka venalari drenajini tuzatish", 1, 1),
    # 2-toifa
    "aortic_valvotomy": ("Aorta qopqog'i valvotomiyasi / valvuloplastikasi", 4, 2),
    "subaortic_resection": ("Subaortal stenozni rezeksiya qilish", 2, 2),
    "pulmonary_valvotomy": ("O'pka arteriyasi qopqog'i valvotomiyasi / valvuloplastikasi", 2, 2),
    "pulmonary_valve_replacement": ("O'pka arteriyasi qopqog'ini almashtirish", 2, 2),
    "rv_infundibulectomy": ("O'ng qorincha infundibulektomiyasi", 2, 2),
    "rvot_augmentation": ("O'pka chiqish yo'lini kengaytirish", 2, 2),
    "coronary_fistula_repair": ("Koronar arteriya fistulasini tuzatish", 2, 2),
    "asd_vsd_repair": ("BBTN va QATN ni birga yopish", 2, 2),
    "primum_asd_repair": ("Birlamchi BBTN (ostium primum) ni tuzatish", 2, 2),
    "vsd_repair": ("Qorinchalararo to'siq nuqsonini (QATN) yopish", 2, 2),
    "vsd_pulmonary_valvotomy": ("QATN yopish + o'pka valvotomiyasi yoki infundibulyar rezeksiya", 2, 2),
    "vsd_pa_band_removal": ("QATN yopish + o'pka arteriyasi bandajini olib tashlash", 2, 2),
    "tof_repair": ("Fallo tetradasini to'liq tuzatish", 2, 2),
    "tapvc_repair": ("To'liq anomal o'pka venalari drenajini tuzatish", 4, 2),
    "glenn": ("Glenn anastomozi", 2, 2),
    "vascular_ring": ("Qon tomir halqasini tuzatish", 2, 2),
    "ap_window_repair": ("Aorto-pulmonal oynani yopish", 2, 2),
    "pa_stenosis_repair": ("O'pka arteriyasi stenozini tuzatish", 2, 2),
    "pa_transection": ("O'pka arteriyasini kesib o'tkazish", 2, 2),
    "common_atrium_closure": ("Umumiy bo'lmachani bo'lish", 2, 2),
    "lv_ra_shunt_repair": ("Chap qorincha – o'ng bo'lmacha shuntini tuzatish", 2, 2),
    # 3-toifa
    "aortic_valve_replacement": ("Aorta qopqog'ini almashtirish", 3, 3),
    "ross": ("Ross operatsiyasi", 3, 3),
    "lvot_patch": ("Chap qorincha chiqish yo'liga yamoq", 3, 3),
    "ventriculomyotomy": ("Ventrikulomiotomiya", 3, 3),
    "aortoplasty": ("Aortoplastika", 3, 3),
    "mitral_valvotomy": ("Mitral valvotomiya / valvuloplastika", 3, 3),
    "mitral_valve_replacement": ("Mitral qopqoqni almashtirish", 3, 3),
    "tricuspid_valvectomy": ("Trikuspidal qopqoq valvektomiyasi", 3, 3),
    "tricuspid_valvotomy": ("Trikuspidal valvotomiya / valvuloplastika", 3, 3),
    "tricuspid_valve_replacement": ("Trikuspidal qopqoqni almashtirish", 3, 3),
    "ebstein_repositioning": ("Ebshteyn anomaliyasida trikuspidal qopqoqni joyiga ko'chirish", 5, 3),
    "anomalous_coronary_repair": ("Anomal koronar arteriyani tuzatish (tunnel bilan yoki tunnelsiz)", 3, 3),
    "semilunar_valve_closure": ("Yarimoysimon (aorta yoki o'pka) qopqoqni yopish", 3, 3),
    "rv_pa_conduit": ("O'ng qorincha – o'pka arteriyasi konduiti", 3, 3),
    "lv_pa_conduit": ("Chap qorincha – o'pka arteriyasi konduiti", 3, 3),
    "dorv_repair": ("O'ng qorinchadan ikki tomir chiqishini tuzatish", 3, 3),
    "fontan": ("Fontan operatsiyasi", 3, 3),
    "avsd_repair": ("Atrioventrikulyar kanalni (qisman yoki to'liq) tuzatish", 3, 3),
    "pa_banding": ("O'pka arteriyasini bandajlash", 3, 3),
    "tof_pa_repair": ("Fallo tetradasi + o'pka atreziyasini tuzatish", 3, 3),
    "cor_triatriatum_repair": ("Uch bo'lmachali yurakni tuzatish", 3, 3),
    "systemic_pa_shunt": ("Sistemaviy – o'pka arteriyasi shunti (masalan, Blalock-Taussig)", 3, 3),
    "atrial_switch": ("Bo'lmacha almashtirish (Senning / Mustard)", 3, 3),
    "arterial_switch": ("Arterial almashtirish (Jatene)", 3, 3),
    "anomalous_pa_reimplantation": ("Anomal o'pka arteriyasini qayta ulash", 3, 3),
    "annuloplasty": ("Annuloplastika", 3, 3),
    "coarctation_vsd_repair": ("Koarktatsiyani tuzatish + QATN yopish", 3, 3),
    "intracardiac_tumor_excision": ("Yurak ichidagi o'smani olib tashlash", 3, 3),
    # 4-toifa
    "konno": ("Konno operatsiyasi", 4, 4),
    "single_ventricle_vsd_enlargement": ("Yagona qorinchada QATN ni kengaytirish", 4, 4),
    "atrial_septectomy": ("Bo'lmachalararo septektomiya", 4, 4),
    "rastelli": ("Rastelli operatsiyasi (TMA + QATN + subpulmonal stenoz)", 4, 4),
    "atrial_switch_vsd": ("Bo'lmacha almashtirish + QATN yopish", 4, 4),
    "atrial_switch_subpulmonary": ("Bo'lmacha almashtirish + subpulmonal stenozni tuzatish", 4, 4),
    "arterial_switch_band_removal": ("Arterial almashtirish + o'pka bandajini olib tashlash", 4, 4),
    "arterial_switch_vsd": ("Arterial almashtirish + QATN yopish", 4, 4),
    "arterial_switch_subpulmonary": ("Arterial almashtirish + subpulmonal stenozni tuzatish", 4, 4),
    "truncus_repair": ("Umumiy arterial stvolni tuzatish", 4, 4),
    "arch_repair": ("Gipoplastik yoki uzilgan aorta ravog'ini tuzatish (QATN yopish bilan yoki usiz)", 4, 4),
    "transverse_arch_graft": ("Ko'ndalang ravoqqa protez", 4, 4),
    "unifocalization": ("Fallo tetradasi + o'pka atreziyasida unifokalizatsiya", 4, 4),
    "double_switch": ("Ikki tomonlama almashtirish (double switch)", 4, 4),
    # 5-toifa
    "truncus_iaa_repair": ("Umumiy arterial stvol + uzilgan aorta ravog'ini tuzatish", 5, 5),
    # 6-toifa
    "norwood": ("Norvud operatsiyasi (GChYuS 1-bosqich)", 6, 6),
    "stage1_non_hlhs": ("GChYuS bo'lmagan holatda 1-bosqich (Norvud tipidagi) operatsiya", 6, 6),
    "damus_kaye_stansel": ("Damus-Kaye-Stansel operatsiyasi", 6, 6),
}
EXCLUDED = {"heart_transplant": "Yurak ko'chirib o'tkazish RACHS-1 ga kirmaydi"}


@dataclass
class Rachs1Input:
    procedures: list[str]
    age_days: float
    premature: bool = False                     # < 37 hafta tug'ilgan chaqaloq


def procedure_category(code: str, age_days: float) -> Optional[int]:
    _, neo, older = PROCEDURES[code]
    return neo if age_days <= NEONATE_DAYS else older


def rachs1(x: Rachs1Input) -> Evidence:
    prov = Provenance(name="rachs1", version="2002", reference=REFERENCE)
    codes = list(dict.fromkeys(x.procedures))
    if not codes:
        return Evidence.abstain("risk.rachs1", Source.RULE, prov, "operatsiya ko'rsatilmagan")
    if x.age_days < 0 or x.age_days > 18 * 365.25:
        return Evidence.abstain("risk.rachs1", Source.RULE, prov,
                                "RACHS-1 18 yoshgacha bo'lgan bolalar uchun; kattalarda EuroSCORE II ishlatiladi")
    excl = [EXCLUDED[c] for c in codes if c in EXCLUDED]
    if excl:
        return Evidence.abstain("risk.rachs1", Source.RULE, prov, "; ".join(excl))
    if x.premature and codes == ["pda_closure"]:
        return Evidence.abstain("risk.rachs1", Source.RULE, prov,
                                "chala tug'ilgan chaqaloqda faqat arterial yo'lni yopish RACHS-1 dan chiqarilgan")
    unknown = [c for c in codes if c not in PROCEDURES]
    if unknown:
        return Evidence.abstain("risk.rachs1", Source.RULE, prov,
                                f"ro'yxatda yo'q operatsiya: {', '.join(unknown)} — toifani kardioxirurg belgilaydi")

    per = [(c, procedure_category(c, x.age_days)) for c in codes]
    no_cat = [c for c, k in per if k is None]
    if no_cat:
        return Evidence.abstain("risk.rachs1", Source.RULE, prov,
                                f"{', '.join(PROCEDURES[c][0] for c in no_cat)}: {NEONATE_DAYS} kungacha bo'lgan yoshda nashrda "
                                "toifa berilmagan — kardioxirurg baholaydi")
    cat = max(k for _, k in per)
    m02, m06 = MORTALITY_2002[cat], MORTALITY_CHSS_2006[cat]
    expl = [f"{PROCEDURES[c][0]}: {k}-toifa" for c, k in per]
    if len(per) > 1:
        expl.append(f"bir nechta operatsiya → eng yuqori toifa olinadi: {cat}")
    expl.append(f"yosh {x.age_days:.0f} kun ({'≤' if x.age_days <= NEONATE_DAYS else '>'} {NEONATE_DAYS} kun)")
    expl.append(("asl kogortada o'lim " + (f"{m02}%" if m02 is not None else "baholanmagan (holat kam)")) +
                (f"; zamonaviy markazlarda ≈ {m06}%" if m06 is not None else "") +
                " — bu toifa og'irligi, bemorning shaxsiy xavfi emas")
    return Evidence(kind="risk.rachs1", value=cat, unit="-toifa (1–6)", source=Source.RULE, provenance=prov,
                    risk=LEVEL[cat], explanation=expl)

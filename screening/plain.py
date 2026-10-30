"""Skrining natijasini shifokor uchun oddiy tilda tushuntirish (o'zbek / rus / ingliz).

Texnik izlar (Evidence.explanation) "Batafsil" bo'limida qoladi; bu modul esa
sarlavha, "nima qilish kerak" va har bir ko'rsatkich bo'yicha bitta aniq jumla beradi.
"""
from __future__ import annotations

import re
from typing import Optional

from core.concordance import Agreement
from core.evidence import Evidence, RiskLevel
from screening.rules import RED_FLAGS
from screening.triage import TriageResult

LANGS = ("uz", "ru", "en")

T: dict[str, dict[str, str]] = {
    # sarlavha va "nima qilish kerak"
    "critical.h": {"uz": "Kritik tug'ma yurak nuqsoni gumoni",
                   "ru": "Подозрение на критический врождённый порок сердца",
                   "en": "Suspected critical congenital heart disease"},
    "critical.t": {"uz": "Bolani bugunoq neonatolog yoki pediatrik kardiologga yuboring. ExoKG qilinmaguncha uyga javob bermang.",
                   "ru": "Направьте ребёнка к неонатологу или детскому кардиологу сегодня. Не выписывайте до проведения ЭхоКГ.",
                   "en": "Refer the child to a neonatologist or paediatric cardiologist today. Do not discharge before echocardiography."},
    "high.h": {"uz": "Yurak nuqsoni belgilari bor", "ru": "Есть признаки порока сердца", "en": "Signs of heart disease present"},
    "high.t": {"uz": "Pediatrik kardiolog ko'rigi va ExoKG — imkon qadar tezroq.",
               "ru": "Осмотр детского кардиолога и ЭхоКГ — как можно скорее.",
               "en": "Paediatric cardiology review and echocardiography as soon as possible."},
    "mod.h": {"uz": "ExoKG tavsiya etiladi", "ru": "Рекомендуется ЭхоКГ", "en": "Echocardiography recommended"},
    "mod.t": {"uz": "Rejali tartibda ExoKG ga yo'llang.", "ru": "Направьте на плановую ЭхоКГ.",
              "en": "Refer for a routine echocardiogram."},
    "low.h": {"uz": "Xavf belgilari aniqlanmadi", "ru": "Признаков риска не выявлено", "en": "No warning signs found"},
    "low.t": {"uz": "Hozircha qo'shimcha tekshiruv kerak emas. Shikoyat yoki yangi belgi paydo bo'lsa, qayta tekshiring.",
              "ru": "Дополнительное обследование пока не требуется. При появлении жалоб или новых симптомов — повторите обследование.",
              "en": "No further tests needed now. Re-screen if symptoms or new signs appear."},
    "unk.h": {"uz": "Ma'lumot yetarli emas", "ru": "Недостаточно данных", "en": "Not enough information"},
    "unk.t": {"uz": "Kamida bitta ko'rsatkich kiriting: SpO₂, klinik belgi yoki yurak tovushi.",
              "ru": "Введите хотя бы один показатель: SpO₂, клинический признак или запись тонов сердца.",
              "en": "Enter at least one finding: SpO₂, a clinical sign or a heart sound recording."},
    "rep.h": {"uz": "Pulsoksimetriyani qayta o'lchash kerak", "ru": "Нужно повторить пульсоксиметрию",
              "en": "Repeat pulse oximetry"},
    "rep.t": {"uz": "1 soatdan keyin o'ng qo'l va oyoqda qayta o'lchang va natijani «Urinish: 2» bilan kiriting. "
                    "Ikkinchi marta ham me'yorda bo'lmasa — darhol kardiologga.",
              "ru": "Через 1 час повторите измерение на правой руке и ноге и введите результат с «Попытка: 2». "
                    "Если снова не в норме — срочно к кардиологу.",
              "en": "Repeat on the right hand and a foot in 1 hour and enter it as «Attempt: 2». "
                    "If still not normal — refer to cardiology immediately."},
    # bo'lim nomlari
    "cchd": {"uz": "Pulsoksimetriya (yangi tug'ilgan)", "ru": "Пульсоксиметрия (новорождённый)",
             "en": "Pulse oximetry (newborn)"},
    "rest": {"uz": "SpO₂ (tinch holatda)", "ru": "SpO₂ (в покое)", "en": "SpO₂ (at rest)"},
    "flags": {"uz": "Klinik belgilar", "ru": "Клинические признаки", "en": "Clinical signs"},
    "pcg": {"uz": "Yurak tovushi (AI)", "ru": "Тоны сердца (ИИ)", "en": "Heart sounds (AI)"},
    # pulsoksimetriya
    "cchd.nums": {"uz": "O'ng qo'l {rh}%, oyoq {ft}% (farq {d}%)", "ru": "Правая рука {rh}%, нога {ft}% (разница {d}%)",
                  "en": "Right hand {rh}%, foot {ft}% (difference {d}%)"},
    "cchd.pass": {"uz": "me'yorda", "ru": "норма", "en": "normal"},
    "cchd.repeat": {"uz": "chegaraviy — qayta o'lchash kerak", "ru": "пограничный — нужно повторить",
                    "en": "borderline — repeat needed"},
    "cchd.fail": {"uz": "me'yordan past — kritik nuqson gumoni", "ru": "ниже нормы — подозрение на критический порок",
                  "en": "below normal — critical defect suspected"},
    "cchd.early": {"uz": "Eslatma: tug'ilgandan 24 soat o'tmagan — natija noto'g'ri ijobiy bo'lishi mumkin.",
                   "ru": "Внимание: прошло меньше 24 часов после рождения — возможен ложноположительный результат.",
                   "en": "Note: less than 24 hours after birth — false positives are more likely."},
    "bad_value": {"uz": "Qiymat noto'g'ri kiritilgan — tekshiring.", "ru": "Значение введено неверно — проверьте.",
                  "en": "The value looks wrong — please check it."},
    "rest.red": {"uz": "past (gipoksemiya)", "ru": "низкая (гипоксемия)", "en": "low (hypoxaemia)"},
    "rest.yellow": {"uz": "chegaraviy", "ru": "пограничная", "en": "borderline"},
    "rest.green": {"uz": "me'yorda", "ru": "норма", "en": "normal"},
    # belgilar
    "flags.none": {"uz": "Belgilanmagan.", "ru": "Не отмечены.", "en": "None ticked."},
    "flags.major": {"uz": "jiddiy", "ru": "серьёзный", "en": "major"},
    # AI
    "pcg.none": {"uz": "Yozuv yuklanmagan.", "ru": "Запись не загружена.", "en": "No recording uploaded."},
    "pcg.nomodel": {"uz": "AI modeli o'rnatilmagan — yozuv tahlil qilinmadi.",
                    "ru": "Модель ИИ не установлена — запись не проанализирована.",
                    "en": "The AI model is not installed — the recording was not analysed."},
    "pcg.neonate": {"uz": "1 oydan kichik chaqaloqlarda AI ishlatilmaydi — pulsoksimetriya va klinik ko'rik asosiy.",
                    "ru": "У детей младше 1 месяца ИИ не применяется — основа: пульсоксиметрия и осмотр.",
                    "en": "AI is not used in babies under 1 month — rely on pulse oximetry and examination."},
    "pcg.quality": {"uz": "Yozuvlar sifatsiz (juda qisqa, ovoz kesilgan yoki stetoskop teriga tegmagan). Qayta yozib ko'ring.",
                    "ru": "Записи плохого качества (слишком короткие, перегруз или стетоскоп не прилегал). Запишите заново.",
                    "en": "Recordings are poor quality (too short, clipped, or the stethoscope lost contact). Please record again."},
    "pcg.unstable": {"uz": "Natija noaniq: yozuv davomida o'zgarib turdi (shovqin yoki harakat). Bola tinchlanganda qayta yozing.",
                     "ru": "Результат неясен: менялся по ходу записи (шум или движение). Запишите заново, когда ребёнок успокоится.",
                     "en": "Unclear: the result changed during the recording (noise or movement). Record again when the child is calm."},
    "pcg.unsure": {"uz": "Natija noaniq — shovqinni shifokor o'zi eshitib baholashi kerak.",
                   "ru": "Результат неясен — шум должен оценить врач при аускультации.",
                   "en": "Unclear — the clinician should judge the murmur by auscultation."},
    "pcg.murmur": {"uz": "Yurak shovqini ehtimoli yuqori (eng aniq — {loc}). Shovqin zararsiz ham bo'lishi mumkin; ExoKG aniqlaydi.",
                   "ru": "Высокая вероятность шума (лучше всего — {loc}). Шум может быть функциональным; уточнит ЭхоКГ.",
                   "en": "A murmur is likely (clearest at the {loc}). It may be innocent; echocardiography will tell."},
    "pcg.clear": {"uz": "Yurak shovqini aniqlanmadi.", "ru": "Шум в сердце не выявлен.", "en": "No murmur detected."},
    "pcg.skipped": {"uz": "Ishlatilmagan yozuvlar", "ru": "Не использованы", "en": "Recordings not used"},
    "skip.short": {"uz": "juda qisqa", "ru": "слишком короткая", "en": "too short"},
    "skip.clip": {"uz": "ovoz kesilgan", "ru": "перегруз сигнала", "en": "clipped"},
    "skip.silent": {"uz": "deyarli ovoz yo'q", "ru": "почти нет сигнала", "en": "almost silent"},
    "attention": {"uz": "Klinik qoidalar va AI natijasi bir-biridan farq qiladi. Xulosa xavfsizroq (yuqoriroq xavf) tomonga qilindi — shifokor baholashi shart.",
                  "ru": "Клинические правила и ИИ расходятся. Вывод сделан в сторону большего риска — требуется оценка врача.",
                  "en": "Clinical rules and the AI disagree. The conclusion follows the higher risk — clinician review is required."},
}

LOCATIONS = {
    "AV": {"uz": "aorta nuqtasi", "ru": "точке аорты", "en": "aortic area"},
    "PV": {"uz": "o'pka arteriyasi nuqtasi", "ru": "точке лёгочной артерии", "en": "pulmonary area"},
    "TV": {"uz": "trikuspidal nuqta", "ru": "трикуспидальной точке", "en": "tricuspid area"},
    "MV": {"uz": "mitral nuqta (cho'qqi)", "ru": "митральной точке (верхушка)", "en": "mitral area (apex)"},
    "Phc": {"uz": "boshqa nuqta", "ru": "другой точке", "en": "other site"},
    "UNK": {"uz": "yozuv", "ru": "записи", "en": "recording"},
}

FLAG_NAMES: dict[str, dict[str, str]] = {
    "cyanosis": {"ru": "центральный цианоз", "en": "central cyanosis"},
    "feeding_diaphoresis": {"ru": "потливость и быстрая утомляемость при кормлении", "en": "sweating or tiring during feeds"},
    "failure_to_thrive": {"ru": "плохая прибавка в весе", "en": "poor weight gain"},
    "tachypnea_rest": {"ru": "тахипноэ в покое", "en": "fast breathing at rest"},
    "hepatomegaly": {"ru": "гепатомегалия", "en": "enlarged liver"},
    "weak_femoral_pulse": {"ru": "слабый/отсутствующий пульс на бедренной артерии", "en": "weak or absent femoral pulses"},
    "exertional_syncope": {"ru": "обморок при нагрузке", "en": "fainting on exertion"},
    "exertional_chest_pain": {"ru": "боль в груди при нагрузке", "en": "chest pain on exertion"},
    "family_sudden_death": {"ru": "внезапная смерть в семье до 50 лет", "en": "sudden death in the family before 50"},
    "recurrent_pneumonia": {"ru": "повторные пневмонии", "en": "recurrent pneumonia"},
    "exercise_intolerance": {"ru": "плохая переносимость нагрузки", "en": "poor exercise tolerance"},
    "syndromic_features": {"ru": "синдромальные признаки (напр., Даун)", "en": "syndromic features (e.g. Down syndrome)"},
}


def lang_of(lang: Optional[str]) -> str:
    return lang if lang in LANGS else "uz"


def tr(key: str, lang: str, **kw) -> str:
    return T[key][lang].format(**kw)


def flag_name(code: str, lang: str) -> str:
    return RED_FLAGS[code][0] if lang == "uz" else FLAG_NAMES[code][lang]


def _cchd(e: Evidence, L: str) -> dict:
    title = tr("cchd", L)
    if e.abstained:
        return {"title": title, "level": "grey", "text": tr("bad_value", L)}
    rh, ft, d = (re.findall(r"(\d+)%", e.explanation[0]) + ["?", "?", "?"])[:3]
    level = {"pass": "green", "repeat": "yellow", "fail": "red"}[e.value]
    text = f"{tr('cchd.nums', L, rh=rh, ft=ft, d=d)}: {tr('cchd.' + e.value, L)}."
    if any("24 soat" in s for s in e.explanation):
        text += " " + tr("cchd.early", L)
    return {"title": title, "level": level, "text": text}


def _resting(e: Evidence, L: str) -> dict:
    if e.abstained:
        return {"title": tr("rest", L), "level": "grey", "text": tr("bad_value", L)}
    level = {RiskLevel.HIGH: "red", RiskLevel.MODERATE: "yellow"}.get(e.risk, "green")
    return {"title": tr("rest", L), "level": level, "text": f"{e.value:.0f}% — {tr('rest.' + level, L)}."}


def _flags(e: Evidence, L: str) -> dict:
    if e.abstained:
        return {"title": tr("flags", L), "level": "grey", "text": tr("bad_value", L)}
    if not e.value:
        return {"title": tr("flags", L), "level": "green", "text": tr("flags.none", L)}
    names = [flag_name(c, L) + (f" ({tr('flags.major', L)})" if RED_FLAGS[c][1] else "") for c in e.value]
    level = {RiskLevel.HIGH: "red", RiskLevel.MODERATE: "yellow"}.get(e.risk, "green")
    return {"title": tr("flags", L), "level": level, "text": "; ".join(names) + "."}


def _skip_reason(text: str, L: str) -> str:
    parts = [tr(k, L) for word, k in (("qisqa", "skip.short"), ("kesilgan", "skip.clip"), ("deyarli", "skip.silent"))
             if word in text]
    return ", ".join(parts) or text


def _pcg(e: Optional[Evidence], uploaded: int, model_ready: bool, L: str) -> dict:
    title = tr("pcg", L)
    if not uploaded:
        return {"title": title, "level": "grey", "text": tr("pcg.none", L)}
    if e is None:
        return {"title": title, "level": "grey", "text": tr("pcg.nomodel", L)}
    v = e.value or {}
    note = ""
    if v.get("skipped"):
        bits = []
        for s in v["skipped"]:
            loc, _, why = s.partition(":")
            bits.append(f"{LOCATIONS.get(loc, {}).get(L, loc)} — {_skip_reason(why, L)}")
        note = f" {tr('pcg.skipped', L)}: " + "; ".join(bits) + "."
    if e.abstained:
        reason = e.explanation[0]
        key = ("pcg.neonate" if "validatsiya qilinmagan" in reason else
               "pcg.quality" if "sifatli yozuv yo'q" in reason else
               "pcg.unstable" if "kelishmadi" in reason else "pcg.unsure")
        return {"title": title, "level": "grey", "text": tr(key, L) + note}
    if e.risk == RiskLevel.MODERATE:
        loc = LOCATIONS.get(v.get("max_location", ""), {}).get(L, v.get("max_location", ""))
        return {"title": title, "level": "yellow", "text": tr("pcg.murmur", L, loc=loc) + note}
    return {"title": title, "level": "green", "text": tr("pcg.clear", L) + note}


VERDICTS = {RiskLevel.VERY_HIGH: ("red", "critical"), RiskLevel.HIGH: ("red", "high"),
            RiskLevel.MODERATE: ("yellow", "mod"), RiskLevel.LOW: ("green", "low"),
            RiskLevel.NORMAL: ("green", "low"), RiskLevel.UNKNOWN: ("grey", "unk")}


def plain_report(result: TriageResult, rule_items: list[Evidence], pcg: Optional[Evidence],
                 uploaded: int, model_ready: bool, lang: str = "uz") -> dict:
    L = lang_of(lang)
    final = result.concordance.final_risk
    repeat = final == RiskLevel.MODERATE and any(e.kind == "screening.cchd" and e.value == "repeat" for e in rule_items)
    level, key = ("yellow", "rep") if repeat else VERDICTS[final]
    items = []
    for e in rule_items:
        if e.kind == "screening.cchd":
            items.append(_cchd(e, L))
        elif e.kind == "screening.spo2":
            items.append(_resting(e, L))
        elif e.kind == "screening.red_flags":
            items.append(_flags(e, L))
    items.append(_pcg(pcg, uploaded, model_ready, L))
    attention = tr("attention", L) if result.concordance.status == Agreement.DISAGREE else None
    return {"lang": L, "level": level, "headline": tr(key + ".h", L), "todo": tr(key + ".t", L),
            "items": items, "attention": attention}

"""EKG / angiografiya / MNO-rasm / ExoKG EF natijalarini oddiy tilda (uz/ru/en) tushuntirish.

Shakl `screening.plain.plain_report` bilan bir xil: {lang, level, headline, todo, items, attention}.
Matnda texnik kod yo'q; texnik izlar `evidence.explanation` da qoladi.
"""
from __future__ import annotations

from core.evidence import Evidence, RiskLevel
from screening.plain import lang_of

T: dict[str, dict[str, str]] = {
    # ---- EKG
    "ecg.afib.h": {"uz": "Bo'lmachalar fibrillyatsiyasi (aritmiya) ehtimoli yuqori",
                   "ru": "Высока вероятность фибрилляции предсердий (аритмии)",
                   "en": "Atrial fibrillation (irregular rhythm) is likely"},
    "ecg.afib.t": {"uz": "EKGni shifokor ko'rib tasdiqlasin va bemor bilan bugun bog'laning.",
                   "ru": "Врач должен просмотреть ЭКГ и подтвердить; свяжитесь с пациентом сегодня.",
                   "en": "A doctor should review and confirm the ECG; contact the patient today."},
    "ecg.other.h": {"uz": "EKGda o'zgarishlar bor", "ru": "На ЭКГ есть изменения", "en": "The ECG shows changes"},
    "ecg.other.t": {"uz": "Aritmiya topilmadi, lekin shifokor EKGni ko'rib chiqsin: {found}.",
                    "ru": "Аритмия не найдена, но врачу стоит посмотреть ЭКГ: {found}.",
                    "en": "No arrhythmia found, but a doctor should review the ECG: {found}."},
    "ecg.ok.h": {"uz": "EKGda xavfli belgi topilmadi", "ru": "Опасных признаков на ЭКГ не найдено",
                 "en": "No warning signs on the ECG"},
    "ecg.ok.t": {"uz": "Hozircha qo'shimcha chora kerak emas. Shikoyat bo'lsa, EKGni qayta oling.",
                 "ru": "Дополнительных мер пока не требуется. При жалобах повторите ЭКГ.",
                 "en": "No further action for now. Repeat the ECG if symptoms appear."},
    "ecg.title": {"uz": "EKG", "ru": "ЭКГ", "en": "ECG"},
    "lowef.title": {"uz": "EKG bo'yicha yurak qisqarishi (EF)", "ru": "Сократимость сердца (ФВ) по ЭКГ",
                    "en": "Heart pumping (EF) from the ECG"},
    "lowef.h": {"uz": "Yurak qisqarishi pasaygan bo'lishi mumkin", "ru": "Возможно снижение сократимости сердца",
                "en": "The heart's pumping may be reduced"},
    "lowef.t": {"uz": "ExoKG qiling: EF'ni faqat ExoKG o'lchaydi. Bu tashxis emas, skrining belgisi.",
                "ru": "Сделайте ЭхоКГ: ФВ измеряет только ЭхоКГ. Это не диагноз, а сигнал скрининга.",
                "en": "Order an echocardiogram: only echo measures EF. This is a screening signal, not a diagnosis."},
    "lowef.ok.h": {"uz": "EKGda yurak qisqarishi pasayishi belgisi topilmadi", "ru": "Признаков снижения сократимости на ЭКГ не найдено",
                   "en": "No sign of reduced pumping on the ECG"},
    "lowef.ok.t": {"uz": "Bu EF normal ekanini kafolatlamaydi. Shikoyat yoki klinik shubha bo'lsa, ExoKG qiling.",
                   "ru": "Это не гарантирует нормальную ФВ. При жалобах или клиническом подозрении сделайте ЭхоКГ.",
                   "en": "This does not guarantee a normal EF. If there are symptoms or clinical doubt, order an echo."},
    "lowef.age": {"uz": "Bu baho faqat kattalar uchun. Bolada EF'ni ExoKG o'lchaydi.",
                  "ru": "Эта оценка только для взрослых. У ребёнка ФВ измеряет ЭхоКГ.",
                  "en": "This estimate is for adults only. In a child, EF is measured by echo."},
    "ecg.q": {"uz": "EKG sifati past yoki yetarli emas — qayta yozing (10 soniya, harakatsiz).",
              "ru": "Качество ЭКГ низкое или недостаточное — запишите заново (10 секунд, без движения).",
              "en": "The ECG quality is too low — record again (10 seconds, lying still)."},
    "ecg.age": {"uz": "Bu dastur faqat kattalar EKGsini baholaydi. Bolalar EKGsini kardiolog o'qisin.",
                "ru": "Программа оценивает ЭКГ только у взрослых. ЭКГ ребёнка должен прочитать кардиолог.",
                "en": "This tool only reads adult ECGs. A cardiologist should read a child's ECG."},
    "ecg.unsure": {"uz": "Dastur aniq javob bera olmadi. EKGni shifokor o'zi ko'rsin.",
                   "ru": "Программа не смогла дать уверенный ответ. Пусть врач сам посмотрит ЭКГ.",
                   "en": "The tool could not give a confident answer. A doctor should read the ECG."},
    "ecg.MI": {"uz": "infarkt belgilari", "ru": "признаки инфаркта", "en": "signs of infarction"},
    "ecg.STTC": {"uz": "ST-T o'zgarishlari", "ru": "изменения ST-T", "en": "ST-T changes"},
    "ecg.CD": {"uz": "o'tkazuvchanlik buzilishi", "ru": "нарушение проводимости", "en": "conduction disturbance"},
    "ecg.HYP": {"uz": "gipertrofiya belgilari", "ru": "признаки гипертрофии", "en": "signs of hypertrophy"},
    # ---- angiografiya
    "angio.title": {"uz": "Koronar angiografiya (SYNTAX-ga yordamchi)", "ru": "Коронарография (помощник для SYNTAX)",
                    "en": "Coronary angiography (SYNTAX helper)"},
    "angio.found.h": {"uz": "Shubhali torayish joylari topildi", "ru": "Найдены подозрительные места сужения",
                      "en": "Suspected narrowings found"},
    "angio.found.t": {"uz": "{n} ta joy belgilandi. Bu SYNTAX hisob-kitobi emas — Heart Team angiogrammada o'zi tekshiradi.",
                      "ru": "Отмечено мест: {n}. Это не расчёт SYNTAX — Heart Team проверяет ангиограмму сам.",
                      "en": "{n} spot(s) marked. This is not a SYNTAX score — the Heart Team reviews the angiogram itself."},
    "angio.none.h": {"uz": "Bu kadrda shubhali joy topilmadi", "ru": "На этом кадре подозрительных мест не найдено",
                     "en": "No suspicious spot on this frame"},
    "angio.none.t": {"uz": "Bu stenoz yo'qligini bildirmaydi. Barcha ko'rinishlarni shifokor ko'rib chiqadi.",
                     "ru": "Это не означает отсутствие стеноза. Все проекции оценит врач.",
                     "en": "This does not mean there is no stenosis. A doctor reviews all views."},
    "angio.q": {"uz": "Kadr mos emas (sifati past, kontrast yetarli emas yoki boshqa turdagi rasm). Boshqa kadr yuboring.",
                "ru": "Кадр не подходит (низкое качество, мало контраста или другой тип снимка). Отправьте другой кадр.",
                "en": "The frame is not suitable (low quality, poor contrast or a different kind of image). Send another one."},
    "angio.unsure": {"uz": "Dastur ishonchli javob bera olmadi. Angiogrammani shifokor ko'rsin.",
                     "ru": "Программа не смогла дать надёжный ответ. Ангиограмму должен оценить врач.",
                     "en": "The tool could not give a reliable answer. A doctor should review the angiogram."},
    # ---- MNO rasm
    "inr.title": {"uz": "MNO (varfarin nazorati)", "ru": "МНО (контроль варфарина)", "en": "INR (warfarin control)"},
    "inr.low.h": {"uz": "MNO me'yorda: {v}", "ru": "МНО в норме: {v}", "en": "INR is in range: {v}"},
    "inr.low.t": {"uz": "Dorini shifokor aytganidek davom ettiring.", "ru": "Продолжайте приём как назначил врач.",
                  "en": "Keep taking the medicine as your doctor said."},
    "inr.mod.h": {"uz": "MNO maqsaddan tashqarida: {v}", "ru": "МНО вне целевого диапазона: {v}",
                  "en": "INR is outside the target: {v}"},
    "inr.high.h": {"uz": "MNO xavfli darajada: {v}", "ru": "МНО на опасном уровне: {v}", "en": "INR is at a dangerous level: {v}"},
    "inr.call.t": {"uz": "Shifokoringiz xabardor qilindi. Dozani o'zingiz o'zgartirmang. Qon ketsa yoki ahvolingiz og'ir bo'lsa, 103 ga qo'ng'iroq qiling.",
                   "ru": "Ваш врач уведомлён. Не меняйте дозу сами. При кровотечении или тяжёлом состоянии звоните 103.",
                   "en": "Your doctor has been notified. Do not change the dose yourself. If you bleed or feel very unwell, call 103."},
    "inr.read": {"uz": "Rasm o'qilmadi yoki aniq emas. Qog'ozni yorug' joyda, tekis tutib qayta suratga oling yoki qiymatni qo'lda kiriting.",
                 "ru": "Снимок не прочитан или нечёткий. Сфотографируйте бланк при хорошем свете ровно или введите значение вручную.",
                 "en": "The photo could not be read clearly. Retake it in good light, held flat, or type the value in."},
    "inr.unread.h": {"uz": "MNO qiymati o'qilmadi", "ru": "Значение МНО не прочитано", "en": "INR value could not be read"},
    "inr.unread.t": {"uz": "Shifokoringiz ma'lumotdan xabardor qilindi. Qog'ozni qayta suratga oling.",
                     "ru": "Врач уведомлён. Сфотографируйте бланк ещё раз.",
                     "en": "Your doctor has been told. Please retake the photo."},
    # ---- ExoKG EF
    "ef.title": {"uz": "Chap qorincha otilish fraksiyasi (EF)", "ru": "Фракция выброса левого желудочка (ФВ)",
                 "en": "Left ventricular ejection fraction (EF)"},
    "ef.low.h": {"uz": "EF taxminan {v}% — saqlangan", "ru": "ФВ около {v}% — сохранена", "en": "EF about {v}% — preserved"},
    "ef.mod.h": {"uz": "EF taxminan {v}% — biroz pasaygan", "ru": "ФВ около {v}% — немного снижена",
                 "en": "EF about {v}% — mildly reduced"},
    "ef.high.h": {"uz": "EF taxminan {v}% — pasaygan", "ru": "ФВ около {v}% — снижена", "en": "EF about {v}% — reduced"},
    "ef.vhigh.h": {"uz": "EF taxminan {v}% — keskin pasaygan", "ru": "ФВ около {v}% — резко снижена",
                   "en": "EF about {v}% — severely reduced"},
    "ef.t": {"uz": "Bu taxminiy baho (±6%). Yakuniy EF — ExoKG shifokorining o'lchovi.",
             "ru": "Это приблизительная оценка (±6%). Итоговая ФВ — измерение врача ЭхоКГ.",
             "en": "This is an estimate (±6%). The final EF is the echo doctor's measurement."},
    "ef.age": {"uz": "Bu dastur faqat kattalar ExoKGsini baholaydi. Bolalar uchun kardiolog o'lchasin.",
               "ru": "Программа оценивает только ЭхоКГ взрослых. У детей измерение делает кардиолог.",
               "en": "This tool only reads adult echo studies. For children a cardiologist should measure."},
    "ef.video": {"uz": "Video mos emas yoki yurak to'liq ko'rinmaydi. Apikal 4 kamerali ko'rinishda yangi video yuboring.",
                 "ru": "Видео не подходит или сердце видно не полностью. Отправьте новое видео в апикальной 4-камерной позиции.",
                 "en": "The video is not suitable or the heart is not fully visible. Send a new apical 4-chamber video."},
}


def tr(key: str, lang: str, **kw) -> str:
    return T[key][lang].format(**kw)


def _out(L: str, level: str, headline: str, todo: str, title: str, text: str, attention=None) -> dict:
    return {"lang": L, "level": level, "headline": headline, "todo": todo,
            "items": [{"title": title, "level": level, "text": text}], "attention": attention}


def _abstain(L: str, level_head: str, title: str, text: str) -> dict:
    return _out(L, "grey", level_head, text, title, text)


def _ecg(e: Evidence, L: str) -> dict:
    title = tr("ecg.title", L)
    if e.abstained:
        r = e.explanation[0]
        key = "ecg.age" if "yosh" in r else "ecg.q" if ("sifatsiz" in r or "qisqa" in r or "tarmoq" in r) else "ecg.unsure"
        return _abstain(L, title, title, tr(key, L))
    if e.risk == RiskLevel.HIGH:
        return _out(L, "red", tr("ecg.afib.h", L), tr("ecg.afib.t", L), title, tr("ecg.afib.h", L))
    found = ", ".join(tr("ecg." + c, L) for c in (e.value or {}).get("other_codes", []))
    if e.risk == RiskLevel.MODERATE:
        t = tr("ecg.other.t", L, found=found or "—")
        return _out(L, "yellow", tr("ecg.other.h", L), t, title, t)
    return _out(L, "green", tr("ecg.ok.h", L), tr("ecg.ok.t", L), title, tr("ecg.ok.h", L))


def _lowef(e: Evidence, L: str) -> dict:
    title = tr("lowef.title", L)
    if e.abstained:
        r = e.explanation[0]
        key = "lowef.age" if "yosh" in r else "ecg.q" if ("sifatsiz" in r or "qisqa" in r or "tarmoq" in r) else "ecg.unsure"
        return _abstain(L, title, title, tr(key, L))
    if e.risk == RiskLevel.MODERATE:
        return _out(L, "yellow", tr("lowef.h", L), tr("lowef.t", L), title, tr("lowef.h", L))
    return _out(L, "green", tr("lowef.ok.h", L), tr("lowef.ok.t", L), title, tr("lowef.ok.h", L))


def _angio(e: Evidence, L: str) -> dict:
    title = tr("angio.title", L)
    if e.abstained:
        key = "angio.q" if "yaroqsiz" in e.explanation[0] else "angio.unsure"
        return _abstain(L, title, title, tr(key, L))
    n = (e.value or {}).get("n_candidates", 0)
    if n:
        t = tr("angio.found.t", L, n=n)
        return _out(L, "yellow", tr("angio.found.h", L), t, title, t)
    t = tr("angio.none.t", L)
    return _out(L, "grey", tr("angio.none.h", L), t, title, t)


def _inr(e: Evidence, L: str) -> dict:
    title = tr("inr.title", L)
    if e.abstained:
        t = tr("inr.read", L)
        return _out(L, "yellow", tr("inr.unread.h", L), tr("inr.unread.t", L) + " " + t, title, t)
    v = f"{e.value:.1f}"
    if e.risk == RiskLevel.LOW:
        h = tr("inr.low.h", L, v=v)
        return _out(L, "green", h, tr("inr.low.t", L), title, h)
    if e.risk == RiskLevel.MODERATE:
        h = tr("inr.mod.h", L, v=v)
        return _out(L, "yellow", h, tr("inr.call.t", L), title, h)
    h = tr("inr.high.h", L, v=v)
    return _out(L, "red", h, tr("inr.call.t", L), title, h)


def _ef(e: Evidence, L: str) -> dict:
    title = tr("ef.title", L)
    if e.abstained:
        key = "ef.age" if "yosh" in e.explanation[0] else "ef.video"
        return _abstain(L, title, title, tr(key, L))
    v = f"{e.value:.0f}"
    level, key = {RiskLevel.LOW: ("green", "low"), RiskLevel.MODERATE: ("yellow", "mod"),
                  RiskLevel.HIGH: ("red", "high"), RiskLevel.VERY_HIGH: ("red", "vhigh")}[e.risk]
    h = tr(f"ef.{key}.h", L, v=v)
    return _out(L, level, h, tr("ef.t", L), title, h)


_BY_KIND = {"ecg.afib": _ecg, "ecg.low_ef": _lowef, "angio.stenosis_assist": _angio, "guardian.inr": _inr, "echo.ef": _ef}


def plain_ai(ev: Evidence, lang: str = "uz") -> dict:
    L = lang_of(lang)
    return _BY_KIND[ev.kind](ev, L)

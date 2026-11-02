/* CardioPath AI — shifokor ilovasi (Clinical Precision maketlari bo'yicha).
   Xavf hech qachon brauzerda hisoblanmaydi: hamma raqam va daraja serverdan keladi. Qizil natijalar animatsiyasiz. */
(() => {
"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* */ } } };

/* ------------------------------------------------------------------ ikonlar (oddiy chiziqli SVG, tashqi kutubxonasiz) */
const ICONS = {
  heart: '<path d="M12 20s-7-4.4-9-9.2C1.6 7.3 3.7 4 7.2 4c2 0 3.4 1.1 4.8 2.8C13.4 5.1 14.8 4 16.8 4c3.5 0 5.6 3.3 4.2 6.8C19 15.6 12 20 12 20z"/>',
  grid: '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
  layers: '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
  pulse: '<path d="M3 12h4l2-5 4 10 2-5h6"/>',
  shield: '<path d="M12 3l8 3v6c0 4.4-3.4 8-8 9-4.6-1-8-4.6-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
  steth: '<path d="M6 3v6a4 4 0 0 0 8 0V3"/><path d="M10 13v2a5 5 0 0 0 10 0v-2"/><circle cx="20" cy="11" r="2"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  back: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  check: '<path d="M5 12l5 5 9-10"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>',
  open: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  upload: '<path d="M12 16V4M6 10l6-6 6 6"/><path d="M4 20h16"/>',
  chart: '<path d="M4 19V5M4 19h16"/><path d="M7 15l4-4 3 3 5-6"/>',
  doc: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
  printer: '<path d="M7 8V3h10v5"/><rect x="4" y="8" width="16" height="8" rx="2"/><path d="M7 14h10v7H7z"/>',
  download: '<path d="M12 4v12M6 10l6 6 6-6"/><path d="M4 20h16"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
  list: '<path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  logout: '<path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10"/>',
};
const ic = (n) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n] || ""}</svg>`;

/* ------------------------------------------------------------------ tarjimalar */
const I = {
  uz: {
    vit_spo2: "SpO₂", vit_pcg: "Yurak tovushi", vit_ef: "EF (LVEF)", vit_risk: "Xavf", notEnteredShort: "Kiritilmagan", aiAdvice: "AI maslahati", nextStep: "Keyingi qadam", noAdvice: "Hozircha muhokama talab qiladigan AI topilmasi yo'q.", heartMap: "Auskultatsiya nuqtalari", heartNote: "Yozuv olingan nuqtalar; eng yuqori shovqin ehtimoli belgilangan.", notRecorded: "Yurak tovushi yozilmagan", v_aorta: "Aorta", v_pulm: "Pulmonal", v_tric: "Trikuspid", v_mitral: "Mitral", topPoint: "eng yuqori",
    hello_m: "Xayrli tong", hello_d: "Xayrli kun", hello_e: "Xayrli kech", hello_sub: "Bugungi holat bir qarashda", chart_stages: "Bemorlar qaysi bosqichda", chart_risk: "Bemorlar xavf darajasi bo'yicha", total: "jami", quick_alerts: "Ogohlantirishlar",
    act_glink: "Bemor havolasi (uy kuzatuvi)", act_kdigo: "KDIGO AKI", act_consent: "Yozma rozilik", glinkCopied: "Havola nusxalandi — bemorga yuboring",
    mg_eyebrow: "Modellar nazorati", mg_title: "AI modellarini boshqarish", mg_sub: "Versiyalar, litsenziyalar, qabul mezonlari, klinik tasdiq va qaytarish tarixi",
    mg_need: "Kardiolog tasdig'i talab etiladi", st_live: "Faol", st_shadow: "Sinovda", st_blocked: "Bloklangan", st_off: "Ulanmagan",
    mg_metric: "Aniqlik ko'rsatkichi (AUROC)", mg_license: "Litsenziya", mg_data: "Ma'lumot", mg_version: "Versiya", mg_research: "faqat tadqiqot", mg_ok_com: "ochiq",
    mg_learning: "Yurak tovushi modeli: o'z-o'zini o'rgatish", mg_running: "Ishlayotgan", mg_current: "Tasdiqlangan", mg_restart: "Yangi versiya tasdiqlangan — dasturni qayta ishga tushiring.",
    mg_cand: "Nomzod model", mg_noCand: "Hozircha nomzod yo'q. Yetarli yangi tasdiqlangan holat to'plangach dastur o'zi tayyorlaydi.",
    mg_gates: "Qabul mezonlari (oldindan belgilangan)", mg_pass: "O'tdi", mg_fail: "O'tmadi", mg_failNote: "Mezon bajarilmadi — tasdiqlab bo'lmaydi.",
    mg_approve: "Tasdiqlash", mg_rollback: "Qaytarish · sababini yozish", mg_reason: "Sabab (kamida 5 belgi)", mg_note: "Izoh", mg_authOff: "Tasdiqlash uchun kirish tizimi yoqilgan bo'lishi kerak. Buyruq:",
    mg_history: "O'zgarishlar tarixi", mg_noHistory: "Tarix bo'sh", mg_confirm: "Rostdan ham bu versiyani joriy qilasizmi?", mg_rbConfirm: "Oldingi versiyaga qaytarilsinmi?",
    mg_blockedTitle: "Ulanmagan yoki rad etilgan", mg_shadowTitle: "Sinovdagi modellar", mg_shadowNote: "Javobi hech kimga ko'rsatilmaydi; shifokorning ko'r bahosi bilan solishtiriladi.",
    sh_eyebrow: "Model sinovi · ko'r baholash", sh_title: "EKG ritmini mustaqil belgilash", sh_sub: "Kandidat model javoblari baholovchiga ko'rsatilmaydi",
    sh_queue: "Baholash navbati", sh_waiting: "{n} ta EKG kutmoqda", sh_blind: "Model javobi ataylab ko'rsatilmaydi — ko'r baholash.", sh_rate: "Shifokorning mustaqil ritm bahosi",
    sh_orig: "EKG'ni asl yozuvdan (qurilma yoki qog'oz) o'qing — dastur EKG'ni saqlamaydi.", sh_save: "Bahoni saqlash", sh_none: "Baholash kutayotgan EKG yo'q.",
    sh_report: "Umumiy hisobot", sh_early: "Hali erta — yetarli namuna yig'ilmagan.", sh_ready: "Yetarli namuna yig'ildi.", sh_afib: "AFIB bilan", sh_nonafib: "AFIB'siz",
    sh_compare: "Yakuniy taqqoslash", sh_locked: "Hozircha mavjud emas", sh_lockedNote: "Ishlayotgan model, sinovdagi model va shifokor bahosini solishtirish yetarli EKG yig'ilgach ochiladi.",
    sh_live: "Ishlayotgan model", sh_shadowM: "Sinovdagi model", sh_sens: "AFIB sezgirligi", sh_spec: "O'ziga xoslik", sh_fast: "Tez ritm → AFIB", sh_agree: "Ritm mosligi", sh_selected: "Tanlangan",
    rh_SR: "Sinus ritmi", rh_SBRAD: "Sinus bradikardiyasi", rh_STACH: "Sinus taxikardiyasi", rh_AFIB: "Bo'lmachalar fibrillyatsiyasi", rh_AFL: "Bo'lmachalar titrashi", rh_SVT: "SVT", rh_OTHER: "Boshqa / aniqlab bo'lmaydi",
    sc_eyebrow: "Skrining", sc_title: "Skrining: SpO₂, klinik belgilar va yurak tovushi", sc_sub: "Qoidalar va AI birga ishlaydi; qaror shifokorda",
    sc_new: "Yangi bemor skriningi", sc_cont: "Skrining bosqichidagi bemorlar", sc_start: "Skriningni boshlash", sc_none: "Skrining bosqichida bemor yo'q.",
    sc_wrongStage: "Skrining faqat «Skrining» bosqichida o'tkaziladi.", sc_age: "Yoshi", u_day: "kun", u_month: "oy", u_year: "yil",
    sc_spo2: "Kislorod saturatsiyasi (SpO₂)", sc_spo2Hint: "Yangi tug'ilganlarda (24–48 soat) o'ng qo'l va oyoqda o'lchang. Kattalarda faqat «tinch holatda».",
    sc_rh: "O'ng qo'l, %", sc_foot: "Oyoq, %", sc_attempt: "Urinish", sc_rest: "Tinch holatda, %", sc_flags: "Klinik belgilar", sc_major: "jiddiy",
    sc_ausc: "Yurak tovushi yozuvlari", sc_auscHint: "Nuqtani bosing yoki fayl tanlang. WAV, har nuqtada kamida 5 soniya (yaxshisi 15–20). Bitta nuqta ham yetarli.",
    sc_device: "Stetoskop modeli", sc_consent: "Bemor (yoki ota-ona) yozma roziligi olindi — yozuvlar tadqiqot uchun saqlansin",
    sc_short: "Juda qisqa (5 s dan kam)", sc_ready: "Tayyor", sc_needAge: "Yoshni kiriting.", sc_needPair: "O'ng qo'l va oyoq SpO₂ ikkalasi kerak.",
    sc_result: "Skrining natijasi", sc_findings: "Topilmalar", sc_echo: "Keyingi qadam: bemorni «Tekshiruv» bosqichiga o'tkazing (ExoKG).",
    loc_AV: "Aorta", loc_PV: "O'pka arteriyasi", loc_TV: "Trikuspidal", loc_MV: "Mitral (cho'qqi)",
    locw_AV: "to'sh suyagining o'ng chetida, 2-qovurg'a oralig'i", locw_PV: "to'sh suyagining chap chetida, 2-qovurg'a oralig'i",
    locw_TV: "to'sh suyagining chap chetida, 4-qovurg'a oralig'i", locw_MV: "chap o'rta o'mrov chizig'i, 5-qovurg'a oralig'i",
    dl_sent: "Jarrohga yuborildi {t}", dl_failed: "Jarrohga yetib bormadi — internet yo'q, avtomatik qayta yuboriladi ({n}-urinish)", dl_none: "Telegram sozlanmagan — faqat shu ro'yxatda", dl_notSeen: "jarroh hali «Qabul qildim» demadi", resend: "Hozir qayta yuborish",
    gl_inr: "Varfarin (MNO nazorati)", gl_hint: "Tanlansa, bemor sahifasida MNO natijasini yuborish bosqichi paydo bo'ladi.", gl_copy: "Havolani nusxalash", ind_none: "Varfarin ichmaydi", ind_mechanical_aortic: "Mexanik aortal klapan", ind_mechanical_aortic_risk: "Mexanik aortal klapan + xavf omillari", ind_mechanical_mitral: "Mexanik mitral klapan", ind_bioprosthetic: "Bioprotez (dastlabki oylar)", ind_af: "Bo'lmachalar fibrillyatsiyasi",
    nav_users: "Foydalanuvchilar", us_title: "Foydalanuvchilar va rollar", us_sub: "Kim dasturga kira oladi va nima qila oladi",
    us_authOff: "Kirish tizimi hozir o'chiq: dasturni shu kompyuterdagi har kim ishlatadi. Bir nechta shifokor ishlashi uchun kirishni yoqing.",
    us_authSteps: "Yoqish: 1) terminalda administrator yarating: python -m core.auth_cli create-user --username admin --role admin  2) CARDIOPATH_AUTH=on bilan qayta ishga tushiring.",
    us_add: "Foydalanuvchi qo'shish", us_login: "Login", us_name: "Ismi (ekranda ko'rinadi)", us_role: "Roli", us_pass: "Parol (kamida 10 belgi)", us_pass2: "Parolni takrorlang",
    us_patientCode: "Bemor kodi (faqat «Bemor» roli uchun)", us_status: "Holati", us_active: "Faol", us_disabled: "O'chirilgan", us_actions: "Amallar",
    us_disable: "O'chirish", us_enable: "Yoqish", us_reset: "Yangi parol", us_changeRole: "Rolni o'zgartirish", us_passMismatch: "Parollar bir xil emas",
    us_noPatient: "Bu kod bilan bemor topilmadi", us_log: "Xavfsizlik jurnali", us_logSub: "Kirishlar, xatolar va foydalanuvchi o'zgarishlari", us_me: "siz",
    role_admin: "Administrator", role_clinician: "Shifokor", role_cardiologist: "Kardiolog", role_surgeon: "Kardioxirurg", role_icu: "Reanimatsiya", role_patient: "Bemor",
    rd_admin: "foydalanuvchilar, jurnal; klinik amal yo'q", rd_clinician: "bemor qo'shish, skrining, fayl yuklash", rd_cardiologist: "+ xavf baholash, konsilium, model tasdig'i",
    rd_surgeon: "+ ogohlantirishni qabul qilish", rd_icu: "bosqich, xavf, fayl yuklash", rd_patient: "faqat o'z uy kuzatuvi",
    ev_auth_login: "Tizimga kirdi", ev_auth_login_failed: "Kirish muvaffaqiyatsiz", ev_auth_logout: "Tizimdan chiqdi", ev_auth_change_password: "Parolini o'zgartirdi", ev_auth_change_password_failed: "Parol o'zgartirilmadi", ev_user_create: "Foydalanuvchi qo'shildi", ev_user_disable: "Foydalanuvchi o'chirildi", ev_user_enable: "Foydalanuvchi yoqildi", ev_user_reset_password: "Parol yangilandi", ev_user_set_role: "Rol o'zgartirildi", ev_model_promote: "Model tasdiqlandi", ev_model_rollback: "Model qaytarildi",
    conc_not_comparable: "Solishtirib bo'lmaydi (o'lchovlar turli vaqtda)",
    bk_title: "Zaxira nusxalar", bk_sub: "Bemorlar bazasi har {h} soatda avtomatik saqlanadi; oxirgi {k} ta nusxa turadi.", bk_now: "Hozir nusxa olish", bk_none: "Hali nusxa yo'q.", bk_where: "Joyi", bk_tip: "Muhim: nusxalarni vaqti-vaqti bilan fleshka yoki boshqa diskka ham ko'chiring.", bk_off: "Avtomatik zaxiralash o'chiq.",
    nav_help: "Yordam",
    skip: "Asosiy qismga o'tish", research: "Tadqiqot rejimi", search: "Bemor kodi bo'yicha qidirish", newEpisode: "Yangi bemor",
    nav_dash: "Bosh panel", nav_eps: "Bemorlar", nav_screen: "Skrining", nav_alerts: "Ogohlantirishlar", nav_models: "Modellar", nav_shadow: "Model sinovi",
    welcome: "Xush kelibsiz", signInTitle: "Tizimga kirish", tagline: "Kardiologiya va kardioxirurgiya uchun AI yordamchi",
    username: "Foydalanuvchi nomi", password: "Parol", signIn: "Kirish", signOut: "Chiqish",
    loginNote: "Tadqiqot rejimi. Bemor ma'lumotlari shu kompyuterda qoladi. Yakuniy qaror shifokorniki.",
    loginBad: "Login yoki parol noto'g'ri", loginLocked: "Juda ko'p urinish — birozdan keyin qayta urining", loginNet: "Server bilan aloqa yo'q",
    actorPh: "Ismingiz (shifokor)", light: "Yorug'", dark: "Qorong'i",
    dashEyebrow: "Shifokor ish paneli", dashSub: "Kardiologiya va kardioxirurgiya · barcha yosh guruhlari", urgent: "Shoshilinch",
    noUrgent: "Hozir ochiq shoshilinch ogohlantirish yo'q.", openEp: "Bemorni ochish", ack: "Qabul qildim", ackDone: "Qabul qilindi",
    st_active: "Faol bemorlar", st_ht: "Konsilium kutmoqda", st_icu: "Reanimatsiya (ICU)", st_guard: "Guardian 30 kun",
    st_active_s: "yopilmaganlar", st_ht_s: "konsiliumdan oldin", st_icu_s: "faol kuzatuv", st_guard_s: "uy sharoitidagi nazorat",
    episodes: "Bemorlar", episodesSub: "Oxirgi yangilangan bemorlar", allPop: "Barcha aholi", allStages: "Barcha bosqichlar",
    col_ref: "Bemor kodi", col_pop: "Aholi", col_stage: "Bosqich", col_risk: "Xavf", col_upd: "Oxirgi o'zgarish", col_disc: "Muhokama",
    pop_adult: "Kattalar", pop_pediatric: "Bola", disc_n: "Savol: {n}", noEpisodes: "Hozircha bemor yo'q. «Yangi bemor» tugmasini bosing.",
    risk_low: "Past", risk_normal: "Me'yor", risk_moderate: "O'rta", risk_high: "Yuqori", risk_very_high: "Juda yuqori", risk_unknown: "Noma'lum",
    risk_none: "Baholanmagan", abstained: "AI aniq javob bermadi",
    stage_screening: "Skrining", stage_workup: "Tekshiruv", stage_heart_team: "Konsilium", stage_procedure: "Operatsiya", stage_icu: "Reanimatsiya",
    stage_discharge: "Chiqarish", stage_guardian_30d: "Guardian 30 kun", stage_closed: "Yopilgan",
    whatToDo: "Nima qilish kerak", nextStage: "Keyingi bosqichga o'tkazish", journey: "Bemor yo'li",
    sec_overview: "Umumiy ma'lumot", sec_risk: "Operatsiya oldi xavf", sec_ai: "AI natijalari", sec_disc: "Muhokama qilinadigan savollar", sec_proto: "Konsilium bayonnomasi",
    sec_evidence: "Natijalar tarixi", sec_conc: "Qoida va AI mosligi", details: "Batafsil",
    euroscore: "EuroSCORE II · kattalar", thakar: "Thakar · dializ xavfi", rachs: "RACHS-1 · <18 yosh", notApplicable: "Qo'llanilmaydi", notDone: "Hisoblanmagan",
    points: "ball", category: "-toifa", aiAssist: "AI yordamchi — yakuniy qarorni shifokor tasdiqlaydi.",
    ai_pcg: "Yurak tovushi (PCG)", ai_ecg: "Bo'lmachalar fibrillyatsiyasi", ai_ecg_low_ef: "Past EF (≤45%) ehtimoli", ai_ecg_shd: "Yurak tuzilishi belgilari",
    ai_angio: "Angiografiya: stenoz nomzodlari", ai_echo_ef: "ExoKG videodan EF", notRun: "Bajarilmagan", found: "Topildi", notFound: "Topilmadi",
    noDisc: "Muhokama talab qiladigan savol yo'q.", openQuestions: "Ochiq savollar", noEvidence: "Hali dalil yo'q.",
    conc_agree: "Mos keldi", conc_disagree: "Mos kelmadi — muhokama zarur", conc_ai_abstained: "AI javob bermadi", conc_rule_only: "Faqat qoida natijasi bor",
    src_rule: "Qoida", src_model: "AI", src_clinician: "Shifokor", src_patient: "Bemor",
    act_ecg: "EKG yuklash", act_risk: "Xavf baholash", act_proto: "Konsilium bayonnomasi", act_screen: "Skrining",
    tr_title: "Keyingi bosqichga o'tkazish", tr_to: "Qaysi bosqichga", tr_note: "Izoh (nima va nima uchun)", tr_q: "Ochiq savollar (har biri yangi qatorda)",
    tr_go: "O'tkazish", cancel: "Bekor qilish", tr_none: "Bu bosqichdan keyin o'tish yo'q (bemor yo'li yakunlangan).",
    ne_title: "Yangi bemor", ne_ref: "Bemor kodi (psevdonim)", ne_refHint: "Ism-familiya yozmang — faqat kod.", ne_pop: "Aholi", ne_go: "Yaratish",
    needActor: "Avval chap pastda ismingizni kiriting.", saved: "Saqlandi", failed: "Xato",
    ecgTitle: "EKG yuklash va AI tahlili", ecgSub: "Tadqiqot rejimi · natijalar shifokor tomonidan ko'rib chiqiladi", ecgUpload: "EKG faylini yuklash",
    ecgDrop: "EKG CSV faylini tanlang", ecgFmt: "CSV · 1-qator tarmoq nomlari (I, II, … V6) · qiymatlar mV", choose: "Fayl tanlash",
    fs: "Chastota", age: "Yoshi (yil)", analyze: "Tahlil qilish", analyzing: "Tahlil ketyapti · {t} da boshlandi",
    preview: "12 tarmoqli EKG · ko'rish", previewNote: "Faylingizdan chizilgan · diagnostika uchun emas", aiResults: "AI natijalari",
    sig_quality: "Signal tekshiruvi", leadsN: "{n} ta tarmoq", seconds: "{n} soniya", source: "Manba va model",
    m_model: "Model", m_version: "Versiya", m_dataset: "Ma'lumot", m_license: "Litsenziya", m_file: "Fayl",
    escal: "Guardian eskalatsiyasi", backToEp: "Bemor sahifasiga qaytish",
    riskTitle: "Operatsiya oldi xavf baholash", riskSub: "Har bir shkala o'z populyatsiyasi va mezonlari bo'yicha qo'llanadi",
    tab_es: "EuroSCORE II", tab_es_s: "(kattalar) + Thakar", tab_rachs: "RACHS-1", tab_rachs_s: "(<18 yosh)",
    f_patient: "Bemor ma'lumotlari", f_heart: "Yurak va klinik holat", f_op: "Operatsiya ma'lumotlari", f_aki: "Buyrak (Thakar)",
    f_age: "Yoshi", f_sex: "Jinsi", f_female: "Ayol", f_male: "Erkak", f_weight: "Vazni, kg", f_creat: "Kreatinin, µmol/L",
    f_nyha: "NYHA sinfi", f_lvef: "LVEF, % (ExoKG shifokori o'lchovi)", f_pa: "O'pka arteriyasi sistolik bosimi, mmHg", f_urg: "Shoshilinchlik", f_weightop: "Aralashuv og'irligi",
    f_surgery: "Operatsiya turi (Thakar)", notEntered: "— kiritilmagan —", assumedChip: "kiritilmasa eng past xavf deb olinadi",
    urg_elective: "Rejali", urg_urgent: "Shoshilinch", urg_emergency: "Favqulodda", urg_salvage: "Qutqaruv",
    w_isolated_cabg: "Izolyatsiyalangan KShSh (CABG)", w_single_non_cabg: "Bitta, KShSh emas", w_two: "Ikki aralashuv", w_three_plus: "Uch va undan ko'p",
    s_cabg: "KShSh", s_valve: "Qopqoq", s_cabg_valve: "KShSh + qopqoq", s_other: "Boshqa",
    fl_dialysis: "Dializda", fl_arteriopathy: "Yurakdan tashqari arteriopatiya", fl_mobility: "Harakatlanish cheklangan", fl_prevsurg: "Oldin yurak operatsiyasi",
    fl_lung: "Surunkali o'pka kasalligi", fl_endo: "Faol endokardit", fl_critical: "Kritik holat", fl_insulin: "Insulin talab qiluvchi diabet",
    fl_ccs4: "CCS 4 stenokardiya", fl_mi: "MI ≤ 90 kun", fl_aorta: "Ko'krak aortasi operatsiyasi", fl_chf: "Yurak yetishmovchiligi", fl_iabp: "Operatsiyagacha IABP",
    calc: "Hisoblash", esResult: "EuroSCORE II · natija", esMort: "Operativ o'lim xavfi · kattalar", factors: "Asosiy omillar",
    assumedWarn: "{n} ta maydon kiritilmadi — xavf past baholangan bo'lishi mumkin.", rachsAge: "Yoshi (kun)", premature: "Chala tug'ilgan (< 37 hafta)",
    rachsProcs: "Operatsiya(lar)", rachsResult: "RACHS-1 · natija", stageWarn: "Xavf baholash faqat «Konsilium» yoki «Reanimatsiya» bosqichida.",
    protoTitle: "Konsilium bayonnomasi (Heart Team)", protoSub: "A4 format · klinik dalillar, muhokama va qaror", readiness: "Tayyorlik",
    rd_risk: "Xavf shkalasi kiritildi", rd_ai: "AI dalillari mavjud", rd_disc: "Muhokama punktlari hal qilindi ({n} ta ochiq)", print: "Chop etish · A4",
    rd_block: "{n} ta savol hali muhokama qilinmagan — konsiliumda albatta ko'rib chiqing.",
    alertsTitle: "Ogohlantirishlar", alertsSub: "Guardian, operatsiyadan keyingi kuzatuv va klinik signal", ackNote: "«Qabul qildim» — ogohlantirishni ko'rganlikni bildiradi, muammo hal qilinganini emas.",
    tab_open: "Ochiq", tab_acked: "Qabul qilingan", lvl_all: "Daraja: barchasi", lvl_red: "Qizil", lvl_amber: "Sariq",
    ackedBy: "Qabul qildi: {who} · {t}", noAlerts: "Ogohlantirish yo'q.", refresh: "Yangilash",
    ago_now: "hozirgina", loadErr: "Ma'lumotni yuklab bo'lmadi", notFoundEp: "Bemor topilmadi", noPerm: "Bu bo'lim uchun huquqingiz yo'q.",
    kind_screening_triage: "Skrining xulosasi", kind_screening_cchd: "Pulsoksimetriya", kind_screening_pcg: "Yurak tovushi (AI)", kind_screening_red_flags: "Klinik belgilar",
    kind_screening_rule: "Skrining qoidasi", kind_risk_euroscore2: "EuroSCORE II", kind_risk_aki_rule: "Thakar (AKI)", kind_risk_aki_model: "AKI (AI)",
    kind_risk_rachs1: "RACHS-1", kind_risk_assumptions: "Taxmin qilingan qiymatlar", kind_ecg_afib: "EKG (AI)", kind_ecg_low_ef: "AI-EKG · past EF", kind_ecg_shd: "AI-EKG · yurak tuzilishi",
    kind_angio_stenosis_assist: "Angiografiya (AI)", kind_echo_ef: "ExoKG EF (AI)", kind_clinician_lvef: "ExoKG · LVEF", kind_workup_echo_dx: "ExoKG tashxisi",
    kind_guardian_hf: "Guardian · yurak yetishmovchiligi", kind_guardian_wound: "Guardian · yara", kind_guardian_weight: "Guardian · vazn", kind_guardian_inr: "Guardian · MNO",
    kind_research_recordings: "Tadqiqot yozuvlari",
  },
  ru: {
    vit_spo2: "SpO₂", vit_pcg: "Тоны сердца", vit_ef: "ФВ (ФВЛЖ)", vit_risk: "Риск", notEnteredShort: "Не внесено", aiAdvice: "Совет ИИ", nextStep: "Следующий шаг", noAdvice: "Пока нет находок ИИ, требующих обсуждения.", heartMap: "Точки аускультации", heartNote: "Точки с записью; отмечена точка с наибольшей вероятностью шума.", notRecorded: "Тоны сердца не записаны", v_aorta: "Аорта", v_pulm: "Лёгочная", v_tric: "Трикуспидальная", v_mitral: "Митральная", topPoint: "максимум",
    hello_m: "Доброе утро", hello_d: "Добрый день", hello_e: "Добрый вечер", hello_sub: "Клиническая картина дня одним взглядом", chart_stages: "На каком этапе пациенты", chart_risk: "Пациенты по уровню риска", total: "всего", quick_alerts: "Оповещения",
    act_glink: "Ссылка для пациента (наблюдение)", act_kdigo: "KDIGO AKI", act_consent: "Письменное согласие", glinkCopied: "Ссылка скопирована — отправьте пациенту",
    mg_eyebrow: "Контроль моделей", mg_title: "Управление моделями ИИ", mg_sub: "Версии, лицензии, критерии приёмки, клиническое утверждение и история отката",
    mg_need: "Требуется утверждение кардиолога", st_live: "Активна", st_shadow: "На испытании", st_blocked: "Заблокирована", st_off: "Не подключена",
    mg_metric: "Точность (AUROC)", mg_license: "Лицензия", mg_data: "Данные", mg_version: "Версия", mg_research: "только исследования", mg_ok_com: "открытая",
    mg_learning: "Модель тонов сердца: самообучение", mg_running: "Работает", mg_current: "Утверждена", mg_restart: "Новая версия утверждена — перезапустите программу.",
    mg_cand: "Модель-кандидат", mg_noCand: "Кандидата пока нет. Программа подготовит его, когда наберётся достаточно новых подтверждённых случаев.",
    mg_gates: "Критерии приёмки (заданы заранее)", mg_pass: "Пройден", mg_fail: "Не пройден", mg_failNote: "Критерий не выполнен — утвердить нельзя.",
    mg_approve: "Утвердить", mg_rollback: "Откатить · указать причину", mg_reason: "Причина (не менее 5 символов)", mg_note: "Комментарий", mg_authOff: "Для утверждения нужен включённый вход в систему. Команда:",
    mg_history: "История изменений", mg_noHistory: "История пуста", mg_confirm: "Сделать эту версию текущей?", mg_rbConfirm: "Вернуться к предыдущей версии?",
    mg_blockedTitle: "Не подключены или отклонены", mg_shadowTitle: "Модели на испытании", mg_shadowNote: "Ответ никому не показывается; сравнивается со слепой оценкой врача.",
    sh_eyebrow: "Испытание модели · слепая оценка", sh_title: "Независимая разметка ритма ЭКГ", sh_sub: "Ответы модели-кандидата оценщику не показываются",
    sh_queue: "Очередь оценки", sh_waiting: "Ожидают ЭКГ: {n}", sh_blind: "Ответ модели намеренно скрыт — слепая оценка.", sh_rate: "Независимая оценка ритма врачом",
    sh_orig: "Читайте ЭКГ с исходной записи (прибор или бумага) — программа ЭКГ не хранит.", sh_save: "Сохранить оценку", sh_none: "Нет ЭКГ, ожидающих оценки.",
    sh_report: "Общий отчёт", sh_early: "Пока рано — недостаточно случаев.", sh_ready: "Случаев достаточно.", sh_afib: "С ФП", sh_nonafib: "Без ФП",
    sh_compare: "Итоговое сравнение", sh_locked: "Пока недоступно", sh_lockedNote: "Сравнение рабочей модели, испытуемой модели и врача откроется, когда наберётся достаточно ЭКГ.",
    sh_live: "Рабочая модель", sh_shadowM: "Испытуемая модель", sh_sens: "Чувствительность ФП", sh_spec: "Специфичность", sh_fast: "Быстрый ритм → ФП", sh_agree: "Совпадение ритма", sh_selected: "Выбрано",
    rh_SR: "Синусовый ритм", rh_SBRAD: "Синусовая брадикардия", rh_STACH: "Синусовая тахикардия", rh_AFIB: "Фибрилляция предсердий", rh_AFL: "Трепетание предсердий", rh_SVT: "СВТ", rh_OTHER: "Другое / не определить",
    sc_eyebrow: "Скрининг", sc_title: "Скрининг: SpO₂, клинические признаки и тоны сердца", sc_sub: "Правила и ИИ работают вместе; решение — за врачом",
    sc_new: "Скрининг нового пациента", sc_cont: "Пациенты на этапе скрининга", sc_start: "Начать скрининг", sc_none: "Пациентов на этапе скрининга нет.",
    sc_wrongStage: "Скрининг проводится только на этапе «Скрининг».", sc_age: "Возраст", u_day: "дн.", u_month: "мес.", u_year: "лет",
    sc_spo2: "Сатурация (SpO₂)", sc_spo2Hint: "У новорождённых (24–48 ч) — правая рука и нога. У взрослых — только «в покое».",
    sc_rh: "Правая рука, %", sc_foot: "Нога, %", sc_attempt: "Попытка", sc_rest: "В покое, %", sc_flags: "Клинические признаки", sc_major: "серьёзный",
    sc_ausc: "Записи тонов сердца", sc_auscHint: "Нажмите точку или выберите файл. WAV, не менее 5 с в точке (лучше 15–20). Достаточно одной точки.",
    sc_device: "Модель стетоскопа", sc_consent: "Получено письменное согласие пациента (или родителей) — сохранить записи для исследования",
    sc_short: "Слишком коротко (< 5 с)", sc_ready: "Готово", sc_needAge: "Укажите возраст.", sc_needPair: "Нужны SpO₂ и правой руки, и ноги.",
    sc_result: "Результат скрининга", sc_findings: "Находки", sc_echo: "Следующий шаг: переведите пациента на этап «Обследование» (ЭхоКГ).",
    loc_AV: "Аорта", loc_PV: "Лёгочная артерия", loc_TV: "Трикуспидальная", loc_MV: "Митральная (верхушка)",
    locw_AV: "у правого края грудины, 2-е межреберье", locw_PV: "у левого края грудины, 2-е межреберье",
    locw_TV: "у левого края грудины, 4-е межреберье", locw_MV: "левая среднеключичная линия, 5-е межреберье",
    dl_sent: "Отправлено хирургу {t}", dl_failed: "Не дошло до хирурга — нет интернета, повтор автоматически (попытка {n})", dl_none: "Telegram не настроен — только в этом списке", dl_notSeen: "хирург ещё не нажал «Принято»", resend: "Отправить снова",
    gl_inr: "Варфарин (контроль МНО)", gl_hint: "Если выбрано, на странице пациента появится шаг отправки МНО.", gl_copy: "Скопировать ссылку", ind_none: "Не принимает варфарин", ind_mechanical_aortic: "Механический аортальный клапан", ind_mechanical_aortic_risk: "Механический аортальный + факторы риска", ind_mechanical_mitral: "Механический митральный клапан", ind_bioprosthetic: "Биопротез (первые месяцы)", ind_af: "Фибрилляция предсердий",
    nav_users: "Пользователи", us_title: "Пользователи и роли", us_sub: "Кто может войти и что может делать",
    us_authOff: "Вход сейчас выключен: программой пользуется любой на этом компьютере. Чтобы работали несколько врачей, включите вход.",
    us_authSteps: "Как включить: 1) создайте администратора в терминале: python -m core.auth_cli create-user --username admin --role admin  2) перезапустите с CARDIOPATH_AUTH=on.",
    us_add: "Добавить пользователя", us_login: "Логин", us_name: "Имя (видно на экране)", us_role: "Роль", us_pass: "Пароль (не менее 10 символов)", us_pass2: "Повторите пароль",
    us_patientCode: "Код пациента (только для роли «Пациент»)", us_status: "Статус", us_active: "Активен", us_disabled: "Отключён", us_actions: "Действия",
    us_disable: "Отключить", us_enable: "Включить", us_reset: "Новый пароль", us_changeRole: "Сменить роль", us_passMismatch: "Пароли не совпадают",
    us_noPatient: "Пациент с таким кодом не найден", us_log: "Журнал безопасности", us_logSub: "Входы, ошибки и изменения пользователей", us_me: "вы",
    role_admin: "Администратор", role_clinician: "Врач", role_cardiologist: "Кардиолог", role_surgeon: "Кардиохирург", role_icu: "Реанимация", role_patient: "Пациент",
    rd_admin: "пользователи, журнал; без клинических действий", rd_clinician: "пациенты, скрининг, загрузка файлов", rd_cardiologist: "+ оценка риска, консилиум, утверждение моделей",
    rd_surgeon: "+ приём оповещений", rd_icu: "этапы, риск, загрузка файлов", rd_patient: "только своё домашнее наблюдение",
    ev_auth_login: "Вход в систему", ev_auth_login_failed: "Неудачный вход", ev_auth_logout: "Выход", ev_auth_change_password: "Смена пароля", ev_auth_change_password_failed: "Пароль не изменён", ev_user_create: "Пользователь добавлен", ev_user_disable: "Пользователь отключён", ev_user_enable: "Пользователь включён", ev_user_reset_password: "Пароль сброшен", ev_user_set_role: "Роль изменена", ev_model_promote: "Модель утверждена", ev_model_rollback: "Откат модели",
    conc_not_comparable: "Несопоставимо (измерения в разное время)",
    bk_title: "Резервные копии", bk_sub: "База пациентов сохраняется автоматически каждые {h} ч; хранятся последние {k} копий.", bk_now: "Сделать копию сейчас", bk_none: "Копий пока нет.", bk_where: "Папка", bk_tip: "Важно: периодически копируйте их на флешку или другой диск.", bk_off: "Автоматическое копирование выключено.",
    nav_help: "Справка",
    skip: "Перейти к содержимому", research: "Исследовательский режим", search: "Поиск по коду пациента", newEpisode: "Новый пациент",
    nav_dash: "Панель", nav_eps: "Пациенты", nav_screen: "Скрининг", nav_alerts: "Оповещения", nav_models: "Модели", nav_shadow: "Испытание модели",
    welcome: "Добро пожаловать", signInTitle: "Вход в систему", tagline: "ИИ-помощник для кардиологии и кардиохирургии",
    username: "Имя пользователя", password: "Пароль", signIn: "Войти", signOut: "Выйти",
    loginNote: "Исследовательский режим. Данные пациентов остаются на этом компьютере. Окончательное решение — за врачом.",
    loginBad: "Неверный логин или пароль", loginLocked: "Слишком много попыток — повторите позже", loginNet: "Нет связи с сервером",
    actorPh: "Ваше имя (врач)", light: "Светлая", dark: "Тёмная",
    dashEyebrow: "Рабочая панель врача", dashSub: "Кардиология и кардиохирургия · все возрастные группы", urgent: "Срочно",
    noUrgent: "Открытых срочных оповещений нет.", openEp: "Открыть пациента", ack: "Принято", ackDone: "Принято",
    st_active: "Активные пациенты", st_ht: "Ожидают консилиума", st_icu: "Реанимация (ОРИТ)", st_guard: "Guardian 30 дней",
    st_active_s: "не закрыты", st_ht_s: "перед консилиумом", st_icu_s: "активное наблюдение", st_guard_s: "наблюдение на дому",
    episodes: "Пациенты", episodesSub: "Недавно обновлённые пациенты", allPop: "Все группы", allStages: "Все этапы",
    col_ref: "Код пациента", col_pop: "Группа", col_stage: "Этап", col_risk: "Риск", col_upd: "Изменён", col_disc: "Обсуждение",
    pop_adult: "Взрослый", pop_pediatric: "Ребёнок", disc_n: "Вопросов: {n}", noEpisodes: "Пациентов пока нет. Нажмите «Новый пациент».",
    risk_low: "Низкий", risk_normal: "Норма", risk_moderate: "Средний", risk_high: "Высокий", risk_very_high: "Очень высокий", risk_unknown: "Неизвестно",
    risk_none: "Не оценён", abstained: "ИИ не дал точного ответа",
    stage_screening: "Скрининг", stage_workup: "Обследование", stage_heart_team: "Консилиум", stage_procedure: "Операция", stage_icu: "Реанимация",
    stage_discharge: "Выписка", stage_guardian_30d: "Guardian 30 дней", stage_closed: "Закрыт",
    whatToDo: "Что делать", nextStage: "Перевести на следующий этап", journey: "Путь пациента",
    sec_overview: "Общие сведения", sec_risk: "Предоперационный риск", sec_ai: "Результаты ИИ", sec_disc: "Вопросы для обсуждения", sec_proto: "Протокол консилиума",
    sec_evidence: "История результатов", sec_conc: "Согласие правила и ИИ", details: "Подробнее",
    euroscore: "EuroSCORE II · взрослые", thakar: "Thakar · риск диализа", rachs: "RACHS-1 · <18 лет", notApplicable: "Не применяется", notDone: "Не рассчитан",
    points: "балл.", category: "-я категория", aiAssist: "ИИ помогает — окончательное решение подтверждает врач.",
    ai_pcg: "Тоны сердца (ФКГ)", ai_ecg: "Фибрилляция предсердий", ai_ecg_low_ef: "Вероятность низкой ФВ (≤45%)", ai_ecg_shd: "Признаки структурной патологии",
    ai_angio: "Ангиография: кандидаты стенозов", ai_echo_ef: "ФВ по видео ЭхоКГ", notRun: "Не выполнено", found: "Выявлено", notFound: "Не выявлено",
    noDisc: "Пунктов для обсуждения нет.", openQuestions: "Открытые вопросы", noEvidence: "Данных пока нет.",
    conc_agree: "Совпадает", conc_disagree: "Расхождение — нужно обсуждение", conc_ai_abstained: "ИИ не ответил", conc_rule_only: "Только правило",
    src_rule: "Правило", src_model: "ИИ", src_clinician: "Врач", src_patient: "Пациент",
    act_ecg: "Загрузить ЭКГ", act_risk: "Оценка риска", act_proto: "Протокол консилиума", act_screen: "Скрининг",
    tr_title: "Перевод на следующий этап", tr_to: "На какой этап", tr_note: "Комментарий (что и почему)", tr_q: "Открытые вопросы (каждый с новой строки)",
    tr_go: "Перевести", cancel: "Отмена", tr_none: "Дальше этапов нет (путь пациента завершён).",
    ne_title: "Новый пациент", ne_ref: "Код пациента (псевдоним)", ne_refHint: "Не вводите ФИО — только код.", ne_pop: "Группа", ne_go: "Создать",
    needActor: "Сначала введите своё имя слева внизу.", saved: "Сохранено", failed: "Ошибка",
    ecgTitle: "Загрузка ЭКГ и анализ ИИ", ecgSub: "Исследовательский режим · результаты проверяет врач", ecgUpload: "Загрузка файла ЭКГ",
    ecgDrop: "Выберите CSV-файл ЭКГ", ecgFmt: "CSV · 1-я строка — отведения (I, II, … V6) · значения в мВ", choose: "Выбрать файл",
    fs: "Частота", age: "Возраст (лет)", analyze: "Анализировать", analyzing: "Идёт анализ · начат в {t}",
    preview: "ЭКГ в 12 отведениях · просмотр", previewNote: "Построено из вашего файла · не для диагностики", aiResults: "Результаты ИИ",
    sig_quality: "Проверка сигнала", leadsN: "{n} отведений", seconds: "{n} с", source: "Источник и модель",
    m_model: "Модель", m_version: "Версия", m_dataset: "Данные", m_license: "Лицензия", m_file: "Файл",
    escal: "Эскалация Guardian", backToEp: "К странице пациента",
    riskTitle: "Оценка предоперационного риска", riskSub: "Каждая шкала применяется в своей популяции и по своим критериям",
    tab_es: "EuroSCORE II", tab_es_s: "(взрослые) + Thakar", tab_rachs: "RACHS-1", tab_rachs_s: "(<18 лет)",
    f_patient: "Данные пациента", f_heart: "Сердце и клиника", f_op: "Данные операции", f_aki: "Почки (Thakar)",
    f_age: "Возраст", f_sex: "Пол", f_female: "Женский", f_male: "Мужской", f_weight: "Вес, кг", f_creat: "Креатинин, мкмоль/л",
    f_nyha: "Класс NYHA", f_lvef: "ФВ ЛЖ, % (измерение врача ЭхоКГ)", f_pa: "Систолическое давление в ЛА, мм рт. ст.", f_urg: "Срочность", f_weightop: "Объём вмешательства",
    f_surgery: "Тип операции (Thakar)", notEntered: "— не указано —", assumedChip: "если не указано — берётся наименьший риск",
    urg_elective: "Плановая", urg_urgent: "Срочная", urg_emergency: "Экстренная", urg_salvage: "Спасительная",
    w_isolated_cabg: "Изолированное АКШ", w_single_non_cabg: "Одно, не АКШ", w_two: "Два вмешательства", w_three_plus: "Три и более",
    s_cabg: "АКШ", s_valve: "Клапан", s_cabg_valve: "АКШ + клапан", s_other: "Другое",
    fl_dialysis: "На диализе", fl_arteriopathy: "Внесердечная артериопатия", fl_mobility: "Ограничена подвижность", fl_prevsurg: "Ранее операция на сердце",
    fl_lung: "Хроническая болезнь лёгких", fl_endo: "Активный эндокардит", fl_critical: "Критическое состояние", fl_insulin: "Инсулинозависимый диабет",
    fl_ccs4: "Стенокардия CCS 4", fl_mi: "ИМ ≤ 90 дней", fl_aorta: "Операция на грудной аорте", fl_chf: "Сердечная недостаточность", fl_iabp: "ВАБК до операции",
    calc: "Рассчитать", esResult: "EuroSCORE II · результат", esMort: "Риск операционной летальности · взрослые", factors: "Основные факторы",
    assumedWarn: "Не указано полей: {n} — риск может быть занижен.", rachsAge: "Возраст (дни)", premature: "Недоношенный (< 37 нед.)",
    rachsProcs: "Операция(и)", rachsResult: "RACHS-1 · результат", stageWarn: "Оценка риска — только на этапе «Консилиум» или «Реанимация».",
    protoTitle: "Протокол консилиума (Heart Team)", protoSub: "Формат A4 · данные, обсуждение и решение", readiness: "Готовность",
    rd_risk: "Шкала риска внесена", rd_ai: "Есть данные ИИ", rd_disc: "Пункты обсуждения решены (открыто: {n})", print: "Печать · A4",
    rd_block: "Открыто пунктов обсуждения: {n} — обязательно рассмотрите на консилиуме.",
    alertsTitle: "Оповещения", alertsSub: "Guardian, послеоперационное наблюдение и клинические сигналы", ackNote: "«Принято» означает, что оповещение просмотрено, а не что проблема решена.",
    tab_open: "Открытые", tab_acked: "Принятые", lvl_all: "Уровень: все", lvl_red: "Красный", lvl_amber: "Жёлтый",
    ackedBy: "Принял: {who} · {t}", noAlerts: "Оповещений нет.", refresh: "Обновить",
    ago_now: "только что", loadErr: "Не удалось загрузить данные", notFoundEp: "Пациент не найден", noPerm: "Нет прав для этого раздела.",
    kind_screening_triage: "Итог скрининга", kind_screening_cchd: "Пульсоксиметрия", kind_screening_pcg: "Тоны сердца (ИИ)", kind_screening_red_flags: "Клинические признаки",
    kind_screening_rule: "Правило скрининга", kind_risk_euroscore2: "EuroSCORE II", kind_risk_aki_rule: "Thakar (ОПП)", kind_risk_aki_model: "ОПП (ИИ)",
    kind_risk_rachs1: "RACHS-1", kind_risk_assumptions: "Принятые допущения", kind_ecg_afib: "ЭКГ (ИИ)", kind_ecg_low_ef: "ИИ-ЭКГ · низкая ФВ", kind_ecg_shd: "ИИ-ЭКГ · структура сердца",
    kind_angio_stenosis_assist: "Ангиография (ИИ)", kind_echo_ef: "ФВ ЭхоКГ (ИИ)", kind_clinician_lvef: "ЭхоКГ · ФВ ЛЖ", kind_workup_echo_dx: "Диагноз ЭхоКГ",
    kind_guardian_hf: "Guardian · сердечная недостаточность", kind_guardian_wound: "Guardian · рана", kind_guardian_weight: "Guardian · вес", kind_guardian_inr: "Guardian · МНО",
    kind_research_recordings: "Исследовательские записи",
  },
  en: {
    vit_spo2: "SpO₂", vit_pcg: "Heart sounds", vit_ef: "EF (LVEF)", vit_risk: "Risk", notEnteredShort: "Not entered", aiAdvice: "AI advice", nextStep: "Next step", noAdvice: "No AI finding needs discussion yet.", heartMap: "Auscultation points", heartNote: "Recorded points; the point with the highest murmur probability is marked.", notRecorded: "No heart sounds recorded", v_aorta: "Aortic", v_pulm: "Pulmonary", v_tric: "Tricuspid", v_mitral: "Mitral", topPoint: "highest",
    hello_m: "Good morning", hello_d: "Good afternoon", hello_e: "Good evening", hello_sub: "Today's clinical picture at a glance", chart_stages: "Patients by stage", chart_risk: "Risk distribution", total: "total", quick_alerts: "Alerts",
    act_glink: "Patient link (home follow-up)", act_kdigo: "KDIGO AKI", act_consent: "Clinical consent", glinkCopied: "Link copied — send it to the patient",
    mg_eyebrow: "Model oversight", mg_title: "AI model governance", mg_sub: "Versions, licences, acceptance gates, clinical approval and rollback history",
    mg_need: "Cardiologist approval required", st_live: "Live", st_shadow: "On trial", st_blocked: "Blocked", st_off: "Not loaded",
    mg_metric: "Accuracy (AUROC)", mg_license: "Licence", mg_data: "Dataset", mg_version: "Version", mg_research: "research only", mg_ok_com: "open",
    mg_learning: "Heart-sound model: supervised self-learning", mg_running: "Running", mg_current: "Approved", mg_restart: "A new version was approved — restart the app.",
    mg_cand: "Candidate model", mg_noCand: "No candidate yet. The app prepares one once enough new confirmed cases are collected.",
    mg_gates: "Acceptance gates (pre-registered)", mg_pass: "Passed", mg_fail: "Failed", mg_failNote: "A gate failed — cannot be approved.",
    mg_approve: "Approve", mg_rollback: "Roll back · give a reason", mg_reason: "Reason (at least 5 characters)", mg_note: "Note", mg_authOff: "Approval needs sign-in enabled. Command:",
    mg_history: "Change history", mg_noHistory: "No history", mg_confirm: "Make this version current?", mg_rbConfirm: "Roll back to the previous version?",
    mg_blockedTitle: "Not loaded or rejected", mg_shadowTitle: "Models on trial", mg_shadowNote: "Output is never shown; compared with the clinician's blinded reading.",
    sh_eyebrow: "Model trial · blinded reading", sh_title: "Independent ECG rhythm labelling", sh_sub: "Candidate model outputs are hidden from the reader",
    sh_queue: "Reading queue", sh_waiting: "{n} ECGs waiting", sh_blind: "The model's answer is deliberately hidden — blinded reading.", sh_rate: "Clinician's independent rhythm reading",
    sh_orig: "Read the ECG from the original tracing (device or paper) — the app does not store ECGs.", sh_save: "Save reading", sh_none: "No ECGs awaiting a reading.",
    sh_report: "Summary report", sh_early: "Too early — not enough cases yet.", sh_ready: "Enough cases collected.", sh_afib: "With AF", sh_nonafib: "Without AF",
    sh_compare: "Final comparison", sh_locked: "Not available yet", sh_lockedNote: "Working model vs model on trial vs clinician comparison opens once enough ECGs are collected.",
    sh_live: "Working model", sh_shadowM: "Model on trial", sh_sens: "AF sensitivity", sh_spec: "Specificity", sh_fast: "Fast rhythm → AF", sh_agree: "Rhythm agreement", sh_selected: "Selected",
    rh_SR: "Sinus rhythm", rh_SBRAD: "Sinus bradycardia", rh_STACH: "Sinus tachycardia", rh_AFIB: "Atrial fibrillation", rh_AFL: "Atrial flutter", rh_SVT: "SVT", rh_OTHER: "Other / cannot tell",
    sc_eyebrow: "Screening", sc_title: "Screening: SpO₂, clinical signs and heart sounds", sc_sub: "Rules and AI work together; the clinician decides",
    sc_new: "Screen a new patient", sc_cont: "Patients at the screening stage", sc_start: "Start screening", sc_none: "No patients at the screening stage.",
    sc_wrongStage: "Screening is only done at the Screening stage.", sc_age: "Age", u_day: "days", u_month: "months", u_year: "years",
    sc_spo2: "Oxygen saturation (SpO₂)", sc_spo2Hint: "Newborns (24–48 h): right hand and foot. Adults: resting only.",
    sc_rh: "Right hand, %", sc_foot: "Foot, %", sc_attempt: "Attempt", sc_rest: "At rest, %", sc_flags: "Clinical signs", sc_major: "major",
    sc_ausc: "Heart sound recordings", sc_auscHint: "Tap a point or choose a file. WAV, at least 5 s per point (15–20 is better). One point is enough.",
    sc_device: "Stethoscope model", sc_consent: "Written consent from the patient (or parents) — keep recordings for research",
    sc_short: "Too short (< 5 s)", sc_ready: "Ready", sc_needAge: "Enter the age.", sc_needPair: "Both right-hand and foot SpO₂ are needed.",
    sc_result: "Screening result", sc_findings: "Findings", sc_echo: "Next step: move the patient to Work-up (echocardiography).",
    loc_AV: "Aortic", loc_PV: "Pulmonary", loc_TV: "Tricuspid", loc_MV: "Mitral (apex)",
    locw_AV: "right sternal border, 2nd intercostal space", locw_PV: "left sternal border, 2nd intercostal space",
    locw_TV: "left sternal border, 4th intercostal space", locw_MV: "left midclavicular line, 5th intercostal space",
    dl_sent: "Sent to the surgeon {t}", dl_failed: "Not delivered — no internet, retrying automatically (attempt {n})", dl_none: "Telegram not set up — this list only", dl_notSeen: "surgeon has not acknowledged yet", resend: "Resend now",
    gl_inr: "Warfarin (INR monitoring)", gl_hint: "If chosen, the patient page gets an INR step.", gl_copy: "Copy link", ind_none: "Not on warfarin", ind_mechanical_aortic: "Mechanical aortic valve", ind_mechanical_aortic_risk: "Mechanical aortic + risk factors", ind_mechanical_mitral: "Mechanical mitral valve", ind_bioprosthetic: "Bioprosthesis (early months)", ind_af: "Atrial fibrillation",
    nav_users: "Users", us_title: "Users and roles", us_sub: "Who can sign in and what they can do",
    us_authOff: "Sign-in is off: anyone at this computer can use the app. Turn sign-in on so several clinicians can work.",
    us_authSteps: "To turn on: 1) create an admin in the terminal: python -m core.auth_cli create-user --username admin --role admin  2) restart with CARDIOPATH_AUTH=on.",
    us_add: "Add user", us_login: "Login", us_name: "Name (shown on screen)", us_role: "Role", us_pass: "Password (at least 10 characters)", us_pass2: "Repeat password",
    us_patientCode: "Patient code (Patient role only)", us_status: "Status", us_active: "Active", us_disabled: "Disabled", us_actions: "Actions",
    us_disable: "Disable", us_enable: "Enable", us_reset: "New password", us_changeRole: "Change role", us_passMismatch: "Passwords do not match",
    us_noPatient: "No patient with this code", us_log: "Security log", us_logSub: "Sign-ins, failures and user changes", us_me: "you",
    role_admin: "Administrator", role_clinician: "Clinician", role_cardiologist: "Cardiologist", role_surgeon: "Cardiac surgeon", role_icu: "Intensive care", role_patient: "Patient",
    rd_admin: "users, log; no clinical actions", rd_clinician: "patients, screening, uploads", rd_cardiologist: "+ risk, Heart Team, model approval",
    rd_surgeon: "+ acknowledge alerts", rd_icu: "stages, risk, uploads", rd_patient: "own home follow-up only",
    ev_auth_login: "Signed in", ev_auth_login_failed: "Failed sign-in", ev_auth_logout: "Signed out", ev_auth_change_password: "Changed password", ev_auth_change_password_failed: "Password not changed", ev_user_create: "User added", ev_user_disable: "User disabled", ev_user_enable: "User enabled", ev_user_reset_password: "Password reset", ev_user_set_role: "Role changed", ev_model_promote: "Model approved", ev_model_rollback: "Model rolled back",
    conc_not_comparable: "Not comparable (measured at different times)",
    bk_title: "Backups", bk_sub: "The patient database is saved automatically every {h} h; the last {k} copies are kept.", bk_now: "Back up now", bk_none: "No backups yet.", bk_where: "Folder", bk_tip: "Important: copy them to a USB drive or another disk from time to time.", bk_off: "Automatic backups are off.",
    nav_help: "Help",
    skip: "Skip to content", research: "Research mode", search: "Search by patient code", newEpisode: "New patient",
    nav_dash: "Dashboard", nav_eps: "Patients", nav_screen: "Screening", nav_alerts: "Alerts", nav_models: "Models", nav_shadow: "Model trial",
    welcome: "Welcome", signInTitle: "Sign in", tagline: "AI assistant for cardiology and cardiac surgery",
    username: "Username", password: "Password", signIn: "Sign in", signOut: "Sign out",
    loginNote: "Research mode. Patient data stays on this computer. The final decision is the doctor's.",
    loginBad: "Wrong username or password", loginLocked: "Too many attempts — try again later", loginNet: "No connection to the server",
    actorPh: "Your name (clinician)", light: "Light", dark: "Dark",
    dashEyebrow: "Clinician workspace", dashSub: "Cardiology and cardiac surgery · all ages", urgent: "Urgent",
    noUrgent: "No open urgent alerts right now.", openEp: "Open patient", ack: "Acknowledge", ackDone: "Acknowledged",
    st_active: "Active patients", st_ht: "Awaiting Heart Team", st_icu: "Intensive care", st_guard: "Guardian 30 days",
    st_active_s: "not closed", st_ht_s: "before the board", st_icu_s: "active monitoring", st_guard_s: "home follow-up",
    episodes: "Patients", episodesSub: "Recently updated patients", allPop: "All groups", allStages: "All stages",
    col_ref: "Patient code", col_pop: "Group", col_stage: "Stage", col_risk: "Risk", col_upd: "Updated", col_disc: "To discuss",
    pop_adult: "Adult", pop_pediatric: "Child", disc_n: "Questions: {n}", noEpisodes: "No patients yet. Press “New patient”.",
    risk_low: "Low", risk_normal: "Normal", risk_moderate: "Moderate", risk_high: "High", risk_very_high: "Very high", risk_unknown: "Unknown",
    risk_none: "Not assessed", abstained: "AI gave no clear answer",
    stage_screening: "Screening", stage_workup: "Work-up", stage_heart_team: "Heart Team", stage_procedure: "Procedure", stage_icu: "Intensive care",
    stage_discharge: "Discharge", stage_guardian_30d: "Guardian 30 days", stage_closed: "Closed",
    whatToDo: "What to do", nextStage: "Move to next stage", journey: "Patient journey",
    sec_overview: "Overview", sec_risk: "Pre-operative risk", sec_ai: "AI results", sec_disc: "Questions to discuss", sec_proto: "Heart Team protocol",
    sec_evidence: "Results history", sec_conc: "Rule vs AI agreement", details: "Details",
    euroscore: "EuroSCORE II · adults", thakar: "Thakar · dialysis risk", rachs: "RACHS-1 · <18 years", notApplicable: "Not applicable", notDone: "Not calculated",
    points: "pts", category: " category", aiAssist: "AI assists — the doctor confirms the final decision.",
    ai_pcg: "Heart sounds (PCG)", ai_ecg: "Atrial fibrillation", ai_ecg_low_ef: "Low EF (≤45%) probability", ai_ecg_shd: "Structural heart disease signs",
    ai_angio: "Angiography: stenosis candidates", ai_echo_ef: "EF from echo video", notRun: "Not run", found: "Found", notFound: "Not found",
    noDisc: "Nothing needs discussion.", openQuestions: "Open questions", noEvidence: "No evidence yet.",
    conc_agree: "Agree", conc_disagree: "Disagree — must discuss", conc_ai_abstained: "AI abstained", conc_rule_only: "Rule only",
    src_rule: "Rule", src_model: "AI", src_clinician: "Clinician", src_patient: "Patient",
    act_ecg: "Upload ECG", act_risk: "Assess risk", act_proto: "Protocol", act_screen: "Screening",
    tr_title: "Move to next stage", tr_to: "Target stage", tr_note: "Note (what and why)", tr_q: "Open questions (one per line)",
    tr_go: "Move", cancel: "Cancel", tr_none: "No further stages (patient pathway completed).",
    ne_title: "New patient", ne_ref: "Patient code (pseudonym)", ne_refHint: "Do not enter names — code only.", ne_pop: "Group", ne_go: "Create",
    needActor: "Enter your name at the bottom left first.", saved: "Saved", failed: "Error",
    ecgTitle: "ECG upload and AI analysis", ecgSub: "Research mode · results are reviewed by a doctor", ecgUpload: "Upload ECG file",
    ecgDrop: "Choose an ECG CSV file", ecgFmt: "CSV · first row = leads (I, II, … V6) · values in mV", choose: "Choose file",
    fs: "Sampling rate", age: "Age (years)", analyze: "Analyse", analyzing: "Analysis in progress · started {t}",
    preview: "12-lead ECG · preview", previewNote: "Drawn from your file · not for diagnosis", aiResults: "AI results",
    sig_quality: "Signal check", leadsN: "{n} leads", seconds: "{n} s", source: "Source and model",
    m_model: "Model", m_version: "Version", m_dataset: "Dataset", m_license: "Licence", m_file: "File",
    escal: "Guardian escalation", backToEp: "Back to patient",
    riskTitle: "Pre-operative risk assessment", riskSub: "Each score is used only in its own population and criteria",
    tab_es: "EuroSCORE II", tab_es_s: "(adults) + Thakar", tab_rachs: "RACHS-1", tab_rachs_s: "(<18 years)",
    f_patient: "Patient", f_heart: "Heart and clinical state", f_op: "Operation", f_aki: "Kidney (Thakar)",
    f_age: "Age", f_sex: "Sex", f_female: "Female", f_male: "Male", f_weight: "Weight, kg", f_creat: "Creatinine, µmol/L",
    f_nyha: "NYHA class", f_lvef: "LVEF, % (echo clinician's measurement)", f_pa: "PA systolic pressure, mmHg", f_urg: "Urgency", f_weightop: "Weight of intervention",
    f_surgery: "Surgery type (Thakar)", notEntered: "— not entered —", assumedChip: "if not entered, lowest risk is assumed",
    urg_elective: "Elective", urg_urgent: "Urgent", urg_emergency: "Emergency", urg_salvage: "Salvage",
    w_isolated_cabg: "Isolated CABG", w_single_non_cabg: "Single non-CABG", w_two: "Two procedures", w_three_plus: "Three or more",
    s_cabg: "CABG", s_valve: "Valve", s_cabg_valve: "CABG + valve", s_other: "Other",
    fl_dialysis: "On dialysis", fl_arteriopathy: "Extracardiac arteriopathy", fl_mobility: "Poor mobility", fl_prevsurg: "Previous cardiac surgery",
    fl_lung: "Chronic lung disease", fl_endo: "Active endocarditis", fl_critical: "Critical pre-op state", fl_insulin: "Insulin-treated diabetes",
    fl_ccs4: "CCS 4 angina", fl_mi: "MI ≤ 90 days", fl_aorta: "Thoracic aorta surgery", fl_chf: "Heart failure", fl_iabp: "Pre-op IABP",
    calc: "Calculate", esResult: "EuroSCORE II · result", esMort: "Operative mortality · adults", factors: "Main factors",
    assumedWarn: "{n} fields not entered — risk may be underestimated.", rachsAge: "Age (days)", premature: "Premature (< 37 weeks)",
    rachsProcs: "Procedure(s)", rachsResult: "RACHS-1 · result", stageWarn: "Risk assessment only at the Heart Team or Intensive care stage.",
    protoTitle: "Heart Team protocol", protoSub: "A4 · evidence, discussion and decision", readiness: "Readiness",
    rd_risk: "Risk score entered", rd_ai: "AI evidence available", rd_disc: "Discussion items resolved ({n} open)", print: "Print · A4",
    rd_block: "{n} discussion items open — be sure to address them at the board.",
    alertsTitle: "Alerts", alertsSub: "Guardian, post-operative follow-up and clinical signals", ackNote: "“Acknowledge” means the alert was seen, not that the problem is solved.",
    tab_open: "Open", tab_acked: "Acknowledged", lvl_all: "Level: all", lvl_red: "Red", lvl_amber: "Amber",
    ackedBy: "Acknowledged by {who} · {t}", noAlerts: "No alerts.", refresh: "Refresh",
    ago_now: "just now", loadErr: "Could not load data", notFoundEp: "Patient not found", noPerm: "You do not have access to this section.",
    kind_screening_triage: "Screening summary", kind_screening_cchd: "Pulse oximetry", kind_screening_pcg: "Heart sounds (AI)", kind_screening_red_flags: "Clinical signs",
    kind_screening_rule: "Screening rule", kind_risk_euroscore2: "EuroSCORE II", kind_risk_aki_rule: "Thakar (AKI)", kind_risk_aki_model: "AKI (AI)",
    kind_risk_rachs1: "RACHS-1", kind_risk_assumptions: "Assumed values", kind_ecg_afib: "ECG (AI)", kind_ecg_low_ef: "AI-ECG · low EF", kind_ecg_shd: "AI-ECG · structure",
    kind_angio_stenosis_assist: "Angiography (AI)", kind_echo_ef: "Echo EF (AI)", kind_clinician_lvef: "Echo · LVEF", kind_workup_echo_dx: "Echo diagnosis",
    kind_guardian_hf: "Guardian · heart failure", kind_guardian_wound: "Guardian · wound", kind_guardian_weight: "Guardian · weight", kind_guardian_inr: "Guardian · INR",
    kind_research_recordings: "Research recordings",
  },
};
let lang = store.get("lang") in I ? store.get("lang") : "uz";
const t = (k, vars) => { let s = I[lang][k] ?? I.uz[k] ?? k; if (vars) for (const [a, b] of Object.entries(vars)) s = s.replace(`{${a}}`, b); return s; };
const LOCALE = () => ({ uz: "uz-UZ", ru: "ru-RU", en: "en-GB" }[lang]);
const STAGES = ["screening", "workup", "heart_team", "procedure", "icu", "discharge", "guardian_30d", "closed"];
const kindLabel = (k) => I[lang]["kind_" + k.replace(/\./g, "_")] || k;

function ago(iso) {
  if (!iso) return "—";
  const d = new Date(iso), s = (Date.now() - d.getTime()) / 1000;
  if (s < 60) return t("ago_now");
  if (lang === "uz") {
    if (s < 3600) return `${Math.round(s / 60)} daqiqa oldin`;
    if (s < 86400) return `${Math.round(s / 3600)} soat oldin`;
  } else {
    const rtf = new Intl.RelativeTimeFormat(LOCALE(), { numeric: "auto" });
    if (s < 3600) return rtf.format(-Math.round(s / 60), "minute");
    if (s < 86400) return rtf.format(-Math.round(s / 3600), "hour");
  }
  if (lang === "uz") return `${d.getDate()}-${UZ_MONTHS[d.getMonth()]}, ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  return d.toLocaleString(LOCALE(), { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}
const UZ_MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"];
const UZ_DAYS = ["yakshanba", "dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba"];
const longDate = (d) => lang === "uz" ? `${UZ_DAYS[d.getDay()]}, ${d.getDate()}-${UZ_MONTHS[d.getMonth()]}`
  : d.toLocaleDateString(LOCALE(), { weekday: "long", day: "numeric", month: "long" });
const hm = (iso) => iso ? new Date(iso).toLocaleTimeString(LOCALE(), { hour: "2-digit", minute: "2-digit" }) : "";

/* ------------------------------------------------------------------ xavf belgilari: har doim belgi + matn */
const RISK_ICON = { low: "✓", normal: "✓", moderate: "!", high: "!", very_high: "⛔", unknown: "?" };
function riskBadge(risk, abstained) {
  if (abstained) return `<span class="cp-risk cp-risk--abstained"><span aria-hidden="true">◇</span>${esc(t("abstained"))}</span>`;
  if (!risk) return `<span class="cp-risk cp-risk--unknown"><span aria-hidden="true">?</span>${esc(t("risk_none"))}</span>`;
  const cls = risk === "normal" ? "low" : risk.replace("_", "-");
  return `<span class="cp-risk cp-risk--${cls}"><span aria-hidden="true">${RISK_ICON[risk] || "?"}</span>${esc(t("risk_" + risk))}</span>`;
}
const levelToRisk = { green: "low", yellow: "moderate", red: "high", grey: "unknown" };

/* xavf shkalasi: EuroSCORE II foizi 0–20% oralig'ida; rang serverdan kelgan xavf darajasidan (brauzer hisoblamaydi) */
function gauge(pct, risk) {
  const v = Math.max(0, Math.min(20, Number(pct) || 0)) / 20, a = Math.PI * (1 - v);
  const x = 60 + 48 * Math.cos(a), y = 58 - 48 * Math.sin(a);
  const col = risk === "high" || risk === "very_high" ? "var(--cp-danger)" : risk === "moderate" ? "var(--cp-warning)" : "var(--cp-success)";
  return `<svg class="gauge" viewBox="0 0 120 70" role="img" aria-label="${esc(pct)}%"><path class="track" d="M12 58A48 48 0 0 1 108 58" fill="none" stroke-width="10" stroke-linecap="round"/>
    ${v > 0 ? `<path d="M12 58A48 48 0 0 1 ${x.toFixed(1)} ${y.toFixed(1)}" fill="none" stroke="${col}" stroke-width="10" stroke-linecap="round"/>` : ""}
    <text x="60" y="56" text-anchor="middle">${esc(pct)}%</text></svg>`;
}
const VALVES = [["AV", "v_aorta", 104, 62], ["PV", "v_pulm", 176, 58], ["TV", "v_tric", 92, 150], ["MV", "v_mitral", 178, 156]];
function heartMap(pcg) {
  const recs = (pcg && pcg.value && pcg.value.recordings) || [], top = pcg && pcg.value && pcg.value.max_location;
  const hot = pcg && !pcg.abstained && (pcg.risk === "high" || pcg.risk === "very_high" || pcg.risk === "moderate");
  const pts = VALVES.map(([loc, key, x, y]) => {
    const rec = recs.find((r) => r.location === loc), isTop = rec && loc === top;
    const fill = !rec ? "var(--cp-border-control)" : isTop && hot ? "var(--cp-danger)" : "var(--cp-brand)";
    return `<circle class="pt" cx="${x}" cy="${y}" r="${isTop ? 11 : 9}" fill="${fill}"/><text x="${x + (x < 140 ? -16 : 16)}" y="${y + 4}" text-anchor="${x < 140 ? "end" : "start"}">${esc(t(key))}${isTop ? " · " + esc(t("topPoint")) : ""}</text>`;
  }).join("");
  return `<svg class="heartmap" viewBox="0 0 280 230" role="img" aria-label="${esc(t("heartMap"))}">
    <path class="vessel" d="M128 70 C128 30 150 20 168 26"/><path class="vessel" d="M150 74 C156 44 186 36 204 46"/>
    <path class="body" d="M140 214 C84 182 60 140 66 100 C70 70 96 54 120 64 C130 68 136 74 140 82 C146 72 156 64 170 62 C200 58 222 84 216 118 C210 154 182 186 140 214Z"/>
    ${pts}</svg>`;
}

/* ------------------------------------------------------------------ kirish va so'rovlar */
let session = null, authOn = false, health = null;
try { session = JSON.parse(sessionStorage.getItem("auth") || "null"); } catch (e) { session = null; }
function saveSession() { try { session ? sessionStorage.setItem("auth", JSON.stringify(session)) : sessionStorage.removeItem("auth"); } catch (e) { /* */ } }
const can = (p) => !authOn || (!!session && session.permissions.includes(p));
const actor = () => (session ? session.user.username : (store.get("actor") || "").trim());

async function api(url, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (session) headers.Authorization = "Bearer " + session.token;
  if (opts.json !== undefined) { headers["Content-Type"] = "application/json"; opts = { ...opts, body: JSON.stringify(opts.json) }; }
  const r = await fetch(url, { ...opts, headers });
  if (r.status === 401 && authOn) { session = null; saveSession(); showLogin(); throw new Error("401"); }
  if (!r.ok) {
    let d = ""; try { d = (await r.json()).detail; } catch (e) { /* */ }
    const err = new Error(typeof d === "string" ? d : JSON.stringify(d || r.statusText)); err.status = r.status; throw err;
  }
  const ct = r.headers.get("content-type") || "";
  return ct.includes("json") ? r.json() : r.text();
}
const toast = (msg, kind) => window.CardioPathUI && window.CardioPathUI.toast(msg, { kind });

function showLogin() {
  $("login").hidden = false; $("lgPass").value = ""; $("loginErr").textContent = "";
  setTimeout(() => $("lgUser").focus(), 0);
}
$("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault(); $("lgGo").disabled = true; $("loginErr").textContent = "";
  try {
    const r = await fetch("/auth/login", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: $("lgUser").value.trim(), password: $("lgPass").value }) });
    if (r.ok) {
      const b = await r.json(); session = { token: b.token, user: b.user, permissions: b.permissions }; saveSession();
      $("login").hidden = true; paintChrome(); route();
    } else { $("loginErr").textContent = t(r.status === 429 ? "loginLocked" : "loginBad"); }
  } catch (err) { $("loginErr").textContent = t("loginNet"); }
  $("lgGo").disabled = false;
});

/* ------------------------------------------------------------------ qobiq: menyu, til, mavzu, foydalanuvchi */
let openAlerts = 0;
function navItems() {
  return [
    { href: "#/", key: "nav_dash", icon: "grid", on: (h) => h === "#/" || h === "" },
    { href: "#/episodes", key: "nav_eps", icon: "folder", on: (h) => h.startsWith("#/episodes") || h.startsWith("#/e/"), perm: "episode.read" },
    { href: "#/screening", key: "nav_screen", icon: "steth", on: (h) => h.startsWith("#/screening") || /^#\/e\/[^/]+\/screening/.test(h), perm: "screening.run" },
    { href: "#/alerts", key: "nav_alerts", icon: "bell", on: (h) => h.startsWith("#/alerts"), perm: "alerts.read", count: true },
    { href: "#/models", key: "nav_models", icon: "layers", on: (h) => h.startsWith("#/models"), perm: "learning.read" },
    { href: "#/shadow", key: "nav_shadow", icon: "pulse", on: (h) => h.startsWith("#/shadow"), perm: "shadow.label", alt: "shadow.report" },
    { href: "#/users", key: "nav_users", icon: "user", on: (h) => h.startsWith("#/users"), perm: "users.manage" },
    { href: "#/help", key: "nav_help", icon: "doc", on: (h) => h.startsWith("#/help") },
  ].filter((n) => (!n.perm || can(n.perm) || (n.alt && can(n.alt))));
}
function paintNav() {
  const h = location.hash || "#/";
  const items = navItems();
  $("nav").innerHTML = items.map((n) => `<a href="${n.href}" ${n.on && n.on(h) ? 'aria-current="page"' : ""}>${ic(n.icon)}<span>${esc(t(n.key))}</span>${n.count && openAlerts ? `<span class="count">${openAlerts}</span>` : ""}</a>`).join("");
  const tabs = items.filter((n) => ["nav_dash", "nav_eps", "nav_screen", "nav_alerts", "nav_models"].includes(n.key));
  $("tabbar").innerHTML = tabs.map((n) => `<a href="${n.href}" ${n.on && n.on(h) ? 'aria-current="page"' : ""}>${ic(n.icon)}<span>${esc(t(n.key))}</span>${n.count && openAlerts ? `<span class="count">${openAlerts}</span>` : ""}</a>`).join("");
  $("mnav").innerHTML = items.map((n) => `<a href="${n.href}" ${n.on && n.on(h) ? 'aria-current="page"' : ""}>${esc(t(n.key))}${n.count && openAlerts ? ` · ${openAlerts}` : ""}</a>`).join("");
}
function paintChrome() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i]").forEach((el) => { el.textContent = t(el.dataset.i); });
  document.querySelectorAll("[data-icon]").forEach((el) => { el.innerHTML = ic(el.dataset.icon); });
  $("q").placeholder = t("search");
  const langBtns = ["uz", "ru", "en"].map((L) => `<button type="button" data-lang="${L}" aria-pressed="${L === lang}">${L.toUpperCase()}</button>`).join("");
  $("langSeg").innerHTML = langBtns; $("loginLang").innerHTML = langBtns;
  const dark = (document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark";
  $("themeSeg").innerHTML = `<button type="button" data-th="light" aria-pressed="${!dark}">${ic("sun")}${esc(t("light"))}</button><button type="button" data-th="dark" aria-pressed="${dark}">${ic("moon")}${esc(t("dark"))}</button>`;
  if (session) {
    const n = session.user.display_name || session.user.username;
    $("userchip").innerHTML = `<span class="avatar">${esc(n.slice(0, 2).toUpperCase())}</span><span style="min-width:0"><b>${esc(n)}</b><small>${esc(session.user.role)}</small></span>
      <button type="button" class="cp-btn cp-btn--ghost" id="logout" aria-label="${esc(t("signOut"))}" title="${esc(t("signOut"))}">${ic("logout")}</button>`;
    $("logout").onclick = async () => { try { await api("/auth/logout", { method: "POST" }); } catch (e) { /* */ } session = null; saveSession(); showLogin(); };
  } else {
    $("userchip").innerHTML = `<span class="avatar">${ic("user")}</span><label class="cp-sr-only" for="actorIn">${esc(t("actorPh"))}</label><input id="actorIn" maxlength="64" placeholder="${esc(t("actorPh"))}" value="${esc(store.get("actor") || "")}">`;
    $("actorIn").oninput = (e) => store.set("actor", e.target.value);
  }
  $("newEp").hidden = !can("episode.create");
  paintNav();
}
document.addEventListener("click", (e) => {
  const lb = e.target.closest("[data-lang]");
  if (lb) { lang = lb.dataset.lang; store.set("lang", lang); paintChrome(); route(); return; }
  const tb = e.target.closest("[data-th]");
  if (tb) { window.CardioPathUI ? window.CardioPathUI.setTheme(tb.dataset.th) : (document.documentElement.dataset.theme = tb.dataset.th); paintChrome(); }
});
$("searchForm").addEventListener("submit", (e) => { e.preventDefault(); location.hash = "#/episodes?q=" + encodeURIComponent($("q").value.trim()); });
$("newEp").addEventListener("click", () => newEpisodeDialog());

/* ------------------------------------------------------------------ dialog yordamchisi (native <dialog>) */
function dialog(html, onSubmit) {
  const d = $("dlg"), f = $("dlgForm");
  f.innerHTML = html;
  f.onsubmit = async (e) => {
    if (e.submitter && e.submitter.value === "cancel") return;
    e.preventDefault();
    const btn = f.querySelector("[type=submit]:not([value=cancel])"); if (btn) btn.disabled = true;
    try { await onSubmit(new FormData(f)); d.close(); }
    catch (err) { const m = f.querySelector(".cp-field__error"); if (m) m.textContent = err.message; }
    if (btn) btn.disabled = false;
  };
  d.showModal();
  const first = f.querySelector("input, select, textarea"); if (first) first.focus();
}
function requireActor() { if (!actor()) { toast(t("needActor"), "error"); const a = $("actorIn"); if (a) a.focus(); return false; } return true; }
function newEpisodeDialog() {
  if (!requireActor()) return;
  dialog(`<h2 class="cp-dialog__title">${esc(t("ne_title"))}</h2>
    <div class="cp-field"><label class="cp-field__label" for="neRef">${esc(t("ne_ref"))}</label><input class="cp-input" id="neRef" name="ref" required maxlength="64" autocomplete="off">
      <span class="cp-field__hint">${esc(t("ne_refHint"))}</span></div>
    <div class="cp-field" style="margin-top:.8rem"><label class="cp-field__label" for="nePop">${esc(t("ne_pop"))}</label>
      <select class="cp-select" id="nePop" name="pop"><option value="adult">${esc(t("pop_adult"))}</option><option value="pediatric">${esc(t("pop_pediatric"))}</option></select></div>
    <p class="cp-field__error" role="alert"></p>
    <div class="cp-dialog__actions"><button class="cp-btn cp-btn--secondary" value="cancel" formnovalidate>${esc(t("cancel"))}</button><button class="cp-btn" type="submit">${esc(t("ne_go"))}</button></div>`,
  async (fd) => {
    const ep = await api("/episodes", { method: "POST", json: { patient_ref: fd.get("ref").trim(), population: fd.get("pop"), actor: actor() } });
    location.hash = "#/e/" + ep.id;
  });
}

/* ------------------------------------------------------------------ marshrutlash */
const view = $("view");
function setBottom(html) { $("bottomBar").innerHTML = html || ""; $("bottomBar").classList.toggle("on", !!html); }
async function route() {
  if (authOn && !session) { showLogin(); return; }
  const h = location.hash || "#/";
  paintNav(); setBottom("");
  const [path, query] = h.slice(1).split("?");
  const params = new URLSearchParams(query || "");
  const parts = path.split("/").filter(Boolean);
  try {
    if (parts.length === 0) await dashboard();
    else if (parts[0] === "episodes") await episodesPage(params);
    else if (parts[0] === "alerts") await alertsPage(params);
    else if (parts[0] === "models") await modelsPage(params);
    else if (parts[0] === "screening") await screeningStart();
    else if (parts[0] === "users") await usersPage();
    else if (parts[0] === "help") helpPage();
    else if (parts[0] === "shadow") await shadowPage(params);
    else if (parts[0] === "e" && parts[1]) {
      const sub = parts[2];
      if (sub === "ecg") await ecgPage(parts[1]);
      else if (sub === "screening") await screeningPage(parts[1]);
      else if (sub === "risk") await riskPage(parts[1], params);
      else if (sub === "protocol") await protocolPage(parts[1]);
      else await episodePage(parts[1]);
    } else await dashboard();
  } catch (err) {
    if (err.message === "401") return;
    view.innerHTML = `<div class="cp-card"><h2>${esc(err.status === 404 ? t("notFoundEp") : err.status === 403 ? t("noPerm") : t("loadErr"))}</h2><p class="sub">${esc(err.message)}</p></div>`;
  }
  refreshAlertCount();
}
window.addEventListener("hashchange", () => { route(); view.focus({ preventScroll: true }); window.scrollTo({ top: 0 }); });
async function refreshAlertCount() {
  if (!can("alerts.read")) return;
  try { const a = await api("/alerts?status=open&limit=1"); if (a.total !== openAlerts) { openAlerts = a.total; paintNav(); } } catch (e) { /* */ }
}

/* yetkazish holati: «yuborildi» ≠ «jarroh ko'rdi»; yetkazilmasa ochiq aytiladi */
function deliveryLine(a) {
  const d = a.delivery || { status: "none" };
  if (d.status === "sent") return `<span class="dl dl--ok">${ic("check")}${esc(t("dl_sent", { t: hm(d.delivered_at) }))}${a.acknowledged ? "" : " · " + esc(t("dl_notSeen"))}</span>`;
  if (d.status === "failed") return `<span class="dl dl--bad">${ic("alert")}${esc(t("dl_failed", { n: d.attempts }))}</span>`;
  return `<span class="dl">${ic("bell")}${esc(t("dl_none"))}</span>`;
}

/* ------------------------------------------------------------------ 1. Bosh panel */
function alertCard(a) {
  const red = a.level === "red";
  return `<article class="urgent ${red ? "" : "urgent--amber"}" ${red ? "data-clinical-urgent" : ""}>
    <div class="urgent__title">${ic(red ? "alert" : "alert")}<span>${esc(a.patient_ref)} · ${esc((a.reasons || [])[0] || a.source)}</span></div>
    <div class="urgent__meta">${esc(ago(a.created_at))} · ${esc(a.source)}</div>${deliveryLine(a)}
    ${(a.reasons || []).length > 1 ? `<div style="font-size:var(--cp-text-sm)">${esc(a.reasons.slice(1).join("; "))}</div>` : ""}
    <div class="actions"><a class="cp-btn ${red ? "btn-danger-solid" : "btn-warn-solid"}" href="#/e/${esc(a.episode_id)}">${ic("open")}${esc(t("openEp"))}</a>
      ${can("alerts.ack") ? `<button class="cp-btn cp-btn--secondary" type="button" data-ack="${a.id}">${ic("check")}${esc(t("ack"))}</button>` : ""}</div></article>`;
}
function bindAck(after) {
  view.querySelectorAll("[data-ack]").forEach((b) => b.addEventListener("click", async () => {
    if (!requireActor()) return;
    b.disabled = true;
    try { await api(`/alerts/${b.dataset.ack}/ack`, { method: "POST", json: { actor: actor(), note: "" } }); toast(t("ackDone")); after(); }
    catch (e) { toast(`${t("failed")}: ${e.message}`, "error"); b.disabled = false; }
  }));
}
function episodeRows(items, suffix = "") {
  if (!items.length) return `<div class="empty-note">${esc(t("noEpisodes"))}</div>`;
  return `<div class="cp-table-scroll"><table class="cp-table"><thead><tr><th scope="col">${esc(t("col_ref"))}</th><th scope="col">${esc(t("col_pop"))}</th><th scope="col">${esc(t("col_stage"))}</th>
    <th scope="col">${esc(t("col_risk"))}</th><th scope="col">${esc(t("col_upd"))}</th><th scope="col">${esc(t("col_disc"))}</th></tr></thead><tbody>
    ${items.map((e) => `<tr><td><span class="pt-ava" aria-hidden="true">${esc(e.patient_ref.replace(/[^A-Za-z0-9]/g, "").slice(0, 2).toUpperCase())}</span><a href="#/e/${esc(e.id)}${suffix}">${esc(e.patient_ref)}</a>${e.open_alert_level ? ` <span class="badge-n" title="alerts">${e.open_alerts}</span>` : ""}</td>
      <td>${esc(t("pop_" + e.population))}</td><td><span class="pill">${esc(t("stage_" + e.stage))}</span></td>
      <td>${riskBadge(e.overall_risk)}</td><td>${esc(ago(e.updated_at))}</td>
      <td><span class="pill ${e.n_discussion ? "" : "pill--muted"}">${esc(t("disc_n", { n: e.n_discussion }))}</span></td></tr>`).join("")}
    </tbody></table></div>`;
}
const STAGE_COLORS = { screening: "#22c1e6", workup: "#2f7cf6", heart_team: "#8b6cff", procedure: "#ff8a3d", icu: "#ff5d73",
  discharge: "#3fd19a", guardian_30d: "#1fb5a8", closed: "#8a99ad" };
const RISK_COLORS = { very_high: "var(--cp-danger)", high: "var(--cp-danger)", moderate: "var(--cp-warning)", low: "var(--cp-success)", normal: "var(--cp-success)", none: "var(--cp-abstain)" };
function ring(n, total) {
  const c = 2 * Math.PI * 22, frac = total ? Math.min(1, n / total) : 0;
  return `<svg class="ring" viewBox="0 0 54 54" aria-hidden="true"><circle class="bg" cx="27" cy="27" r="22"/>
    <circle class="fg" cx="27" cy="27" r="22" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${(c * (1 - frac)).toFixed(1)}"/>
    <text x="27" y="31" text-anchor="middle">${Math.round(frac * 100)}%</text></svg>`;
}
function donut(counts) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0), r = 60, c = 2 * Math.PI * r;
  let off = 0;
  const segs = STAGES.filter((s) => counts[s]).map((s) => {
    const len = (counts[s] / total) * c, seg = `<circle cx="80" cy="80" r="${r}" fill="none" stroke="${STAGE_COLORS[s]}" stroke-width="18"
      stroke-dasharray="${len.toFixed(2)} ${(c - len).toFixed(2)}" stroke-dashoffset="${(-off).toFixed(2)}" transform="rotate(-90 80 80)"/>`;
    off += len; return seg;
  }).join("");
  return `<svg class="donut" viewBox="0 0 160 160" role="img" aria-label="${esc(t("chart_stages"))}"><circle cx="80" cy="80" r="${r}" fill="none" stroke="var(--cp-surface-2)" stroke-width="18"/>
    ${segs}<text class="n" x="80" y="84" text-anchor="middle">${total}</text><text class="l" x="80" y="102" text-anchor="middle">${esc(t("total"))}</text></svg>`;
}
function liveEcg() {
  const beat = (x) => `L${x} 40 L${x + 10} 40 L${x + 16} 34 L${x + 22} 40 L${x + 30} 40 L${x + 35} 48 L${x + 41} 8 L${x + 47} 60 L${x + 53} 40 L${x + 68} 40 L${x + 78} 30 L${x + 90} 40`;
  let d = "M0 40"; for (let x = 0; x < 1180; x += 118) d += " " + beat(x);
  return `<svg class="live-ecg" viewBox="0 0 1180 70" preserveAspectRatio="none" aria-hidden="true"><path class="ghost" d="${d}"/><path class="trace" d="${d}"/></svg>`;
}
let clockTimer = null;
async function dashboard() {
  const canEp = can("episode.read"), canAl = can("alerts.read");
  const [al, eps] = await Promise.all([
    canAl ? api("/alerts?status=open&limit=6") : { items: [], total: 0 },
    canEp ? api("/episodes?limit=200") : { items: [], total: 0 },
  ]);
  openAlerts = al.total;
  const items = eps.items, byStage = {}, byRisk = {};
  items.forEach((e) => { byStage[e.stage] = (byStage[e.stage] || 0) + 1; const k = e.overall_risk || "none"; byRisk[k] = (byRisk[k] || 0) + 1; });
  const active = items.filter((e) => e.stage !== "closed").length;
  const hour = new Date().getHours(), hello = hour < 11 ? t("hello_m") : hour < 17 ? t("hello_d") : t("hello_e");
  const who = session ? (session.user.display_name || session.user.username) : (store.get("actor") || "");
  const stat = (icon, label, n, s, kpi) => `<div class="stat" style="--kpi:${kpi}"><span class="stat__icon">${ic(icon)}</span><div><small>${esc(label)}</small><b>${n}</b>
    <small style="font-weight:500">${esc(s)}</small></div>${ring(n, Math.max(active, 1))}</div>`;
  const riskRows = ["very_high", "high", "moderate", "low", "none"].filter((k) => byRisk[k] || k === "none").map((k) => {
    const n = byRisk[k] || 0, w = items.length ? (n / items.length) * 100 : 0;
    return `<div class="bars__row"><span>${k === "none" ? esc(t("risk_none")) : riskBadge(k)}</span><div class="bars__track"><div class="bars__fill" style="width:${w}%;background:${RISK_COLORS[k]}"></div></div><b>${n}</b></div>`;
  }).join("");
  view.innerHTML = `<div class="pm-in">
    <section class="hello"><div class="hello__row"><div><p class="eyebrow">${esc(t("dashEyebrow"))}</p><h1>${esc(hello)}${who ? ", " + esc(who) : ""}</h1><p>${esc(t("hello_sub"))}</p></div>
        <div class="hello__clock" id="clock"></div></div>
      ${liveEcg()}
      <div class="hello__actions">${can("episode.create") ? `<button class="cp-btn" type="button" id="heroNew">${ic("plus")}${esc(t("newEpisode"))}</button>` : ""}
        ${canAl ? `<a class="cp-btn" href="#/alerts">${ic("bell")}${esc(t("quick_alerts"))}${al.total ? ` · ${al.total}` : ""}</a>` : ""}
        ${can("screening.run") ? `<a class="cp-btn" href="#/screening">${ic("steth")}${esc(t("nav_screen"))}</a>` : ""}</div></section>
    ${canAl ? `<h2 class="section-title">${ic("alert")}${esc(t("urgent"))} <span class="badge-n">${al.total}</span></h2>
      ${al.items.length ? `<div class="urgent-grid">${al.items.slice(0, 3).map(alertCard).join("")}</div>` : `<div class="cp-card" style="margin-bottom:1rem;padding:1rem"><span class="cp-risk cp-risk--low"><span aria-hidden="true">✓</span>${esc(t("noUrgent"))}</span></div>`}` : ""}
    ${canEp ? `<div class="stats">${stat("folder", t("st_active"), active, t("st_active_s"), "linear-gradient(135deg,#2f7cf6,#22c1e6)")}
      ${stat("user", t("st_ht"), byStage.heart_team || 0, t("st_ht_s"), "linear-gradient(135deg,#8b6cff,#5a8bff)")}
      ${stat("pulse", t("st_icu"), byStage.icu || 0, t("st_icu_s"), "linear-gradient(135deg,#ff5d73,#ff8a3d)")}
      ${stat("heart", t("st_guard"), byStage.guardian_30d || 0, t("st_guard_s"), "linear-gradient(135deg,#1fb5a8,#3fd19a)")}</div>
    <div class="charts"><section class="cp-card lift"><h2 class="cp-card__title" style="margin-bottom:1rem">${esc(t("chart_stages"))}</h2>
        <div class="donut-wrap">${donut(byStage)}<ul class="legend">${STAGES.filter((s) => byStage[s]).map((s) => `<li><i style="background:${STAGE_COLORS[s]}"></i>${esc(t("stage_" + s))}<b>${byStage[s]}</b></li>`).join("") || `<li>—</li>`}</ul></div></section>
      <section class="cp-card lift"><h2 class="cp-card__title" style="margin-bottom:1rem">${esc(t("chart_risk"))}</h2><div class="bars">${riskRows}</div></section></div>
    <section class="cp-card"><div class="tablebar"><div><h2 class="cp-card__title">${esc(t("episodes"))}</h2><p class="sub">${esc(t("episodesSub"))}</p></div>
      <a class="cp-btn cp-btn--secondary" href="#/episodes">${ic("list")}${esc(t("nav_eps"))}</a></div>${episodeRows(items.slice(0, 10))}</section>` : ""}</div>`;
  if ($("heroNew")) $("heroNew").onclick = () => newEpisodeDialog();
  const tick = () => { const c = $("clock"); if (!c) { clearInterval(clockTimer); return; } const d = new Date();
    c.innerHTML = `${d.toLocaleTimeString(LOCALE(), { hour: "2-digit", minute: "2-digit" })}<small>${esc(longDate(d))}</small>`; };
  clearInterval(clockTimer); tick(); clockTimer = setInterval(tick, 15000);
  bindAck(dashboard);
  paintNav();
}

/* ------------------------------------------------------------------ 2. Epizodlar ro'yxati */
async function episodesPage(params) {
  const q = params.get("q") || "", stage = params.get("stage") || "";
  const data = await api(`/episodes?limit=100${q ? "&q=" + encodeURIComponent(q) : ""}${stage ? "&stage=" + stage : ""}`);
  view.innerHTML = `<div class="pagehead"><div><p class="eyebrow">CardioPath</p><h1>${esc(t("episodes"))} <small>· ${data.total}</small></h1></div></div>
    <section class="cp-card"><div class="tablebar"><div class="cp-cluster">
      <label class="cp-sr-only" for="fStage">${esc(t("col_stage"))}</label>
      <select class="cp-select" id="fStage"><option value="">${esc(t("allStages"))}</option>${STAGES.map((s) => `<option value="${s}" ${s === stage ? "selected" : ""}>${esc(t("stage_" + s))}</option>`).join("")}</select>
      ${q ? `<span class="pill">${ic("search")}${esc(q)}</span>` : ""}</div></div>${episodeRows(data.items)}</section>`;
  $("fStage").onchange = (e) => { location.hash = `#/episodes?${q ? "q=" + encodeURIComponent(q) + "&" : ""}stage=${e.target.value}`; };
  $("q").value = q;
}

/* ------------------------------------------------------------------ 3. Epizod ish joyi */
function stepper(stage) {
  const cur = STAGES.indexOf(stage);
  return `<ol class="stepper" aria-label="${esc(t("journey"))}">${STAGES.map((s, i) => {
    const cls = stage === "closed" ? (s === "closed" ? "step--cur" : "") : i < cur ? "step--done" : i === cur ? "step--cur" : "";
    return `<li class="step ${cls}" ${i === cur ? 'aria-current="step"' : ""}><span class="step__n">${i < cur && stage !== "closed" ? ic("check") : i + 1}</span>${esc(t("stage_" + s))}</li>`;
  }).join("")}</ol>`;
}
function scoreBox(label, ev, fmt) {
  if (!ev) return `<div class="score"><small>${esc(label)}</small><b>—</b><span class="pill pill--muted">${esc(t("notDone"))}</span></div>`;
  if (ev.abstained) return `<div class="score"><small>${esc(label)}</small><b>—</b>${riskBadge(null, true)}</div>`;
  return `<div class="score"><small>${esc(label)}</small><b>${esc(fmt(ev))}</b>${riskBadge(ev.risk)}</div>`;
}
function aiRow(name, st, latest) {
  let badge;
  if (st.state === "not_run") badge = `<span class="pill pill--muted">${esc(t("notRun"))}</span>`;
  else if (st.state === "abstained") badge = riskBadge(null, true);
  else badge = riskBadge(st.risk);
  const ev = latest[{ pcg: "screening.pcg", ecg: "ecg.afib", ecg_low_ef: "ecg.low_ef", ecg_shd: "ecg.shd", angio: "angio.stenosis_assist", echo_ef: "echo.ef" }[name]];
  return `<div class="row"><span>${esc(t("ai_" + name))}${ev ? `<span class="model-line" style="display:block">${esc(ev.model)} · v${esc(ev.model_version)}</span>` : ""}</span>${badge}</div>`;
}
function concChip(c) {
  const st = c.status, cls = st === "agree" ? "agree" : st === "disagree" ? "disagree" : st === "ai_abstained" ? "abstained" : "";
  const icon = st === "agree" ? "✓" : st === "disagree" ? "!" : st === "ai_abstained" ? "◇" : st === "not_comparable" ? "≠" : "·";
  return `<div class="row"><span class="cp-concordance cp-concordance--${cls}"><span aria-hidden="true">${icon}</span>${esc(t("conc_" + st) || st)}</span>
    <small class="cp-meta" style="flex-basis:100%">${esc(c.question || "")}${st === "not_comparable" && c.message ? " — " + esc(c.message) : ""}</small></div>`;
}
async function episodePage(id) {
  const [ep, d] = await Promise.all([api(`/episodes/${id}`), api(`/episodes/${id}/digest`)]);
  const L = d.latest, es = L["risk.euroscore2"], th = L["risk.aki.rule"], ra = L["risk.rachs1"], kd = L["risk.kdigo"], ecg_int = L["ecg.intervals"];
  const redAlert = (d.open_alerts || []).find((a) => a.level === "red") || (d.open_alerts || [])[0];
  const firstDisc = d.discussion[0];
  const urgentBox = redAlert ? `<div class="urgentbox" data-clinical-urgent>${ic("alert")}<div><b>${esc(t("whatToDo"))}: ${esc((redAlert.reasons || []).join("; ") || redAlert.source)}</b><p>${esc(ago(redAlert.created_at))} · ${esc(redAlert.source)}</p></div></div>`
    : firstDisc ? `<div class="urgentbox ${d.overall_risk === "high" || d.overall_risk === "very_high" ? "" : "urgentbox--warn"}">${ic("alert")}<div><b>${esc(t("whatToDo"))}: ${esc(firstDisc.topic)}</b><p>${esc(firstDisc.reason)}</p></div></div>` : "";
  const evidence = [...ep.evidence].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")).slice(0, 14);
  const canRisk = can("risk.assess"), canUp = can("ai.upload"), canTr = can("episode.transition"), canProto = can("protocol.read");
  const spo2 = L["screening.spo2"], cchd = L["screening.cchd"], pcg = L["screening.pcg"], ef = L["clinician.lvef"] || L["echo.ef"];
  const vital = (label, main, badge) => `<div class="vital"><small>${esc(label)}</small>${main}${badge || ""}</div>`;
  const vitals = [
    vital(t("vit_spo2"), spo2 ? `<b>${esc(spo2.value)}%</b>` : cchd ? `<b>${esc(cchd.value)}</b>` : `<b>—</b>`, spo2 ? riskBadge(spo2.risk) : cchd ? riskBadge(cchd.risk) : `<small>${esc(t("notEnteredShort"))}</small>`),
    vital(t("vit_pcg"), pcg ? "" : `<b>—</b>`, pcg ? riskBadge(pcg.abstained ? null : pcg.risk, pcg.abstained) : `<small>${esc(t("notRecorded"))}</small>`),
    vital(t("vit_ef"), ef ? `<b>${esc(Math.round(ef.value))}%</b>` : `<b>—</b>`, ef ? riskBadge(ef.risk) : `<small>${esc(t("notEnteredShort"))}</small>`),
    vital(t("vit_risk"), es && !es.abstained ? gauge(es.value, es.risk) : ra && !ra.abstained ? `<b>${esc(ra.value)}${esc(t("category"))}</b>` : `<b>—</b>`,
      es && !es.abstained ? riskBadge(es.risk) : ra && !ra.abstained ? riskBadge(ra.risk) : `<small>${esc(t("notDone"))}</small>`),
  ].join("");
  // AI tavsiyasi: faqat AI manbali muhokama punktlari (qoida/kiritish punktlari bu yerda takrorlanmaydi)
  const AI_CODES = ["afib_high", "lowef_echo_needed", "shd_echo", "angio_candidates", "ecg_lvef_disagree", "ef_disagree", "ef_ai_abstained", "screening_disagree", "screening_ai_abstained", "aki_disagree", "aki_ai_abstained"];
  const aiDisc = d.discussion.find((x) => AI_CODES.includes(x.code) || x.code === "ai_result_unavailable");
  const advice = aiDisc ? `<b style="color:var(--cp-ink)">${esc(aiDisc.topic)}:</b> ${esc(aiDisc.reason)}` : esc(t("noAdvice"));
  const nxt = d.next_stages.filter((s) => STAGES.indexOf(s) > STAGES.indexOf(d.episode.stage)).sort((a, b) => STAGES.indexOf(a) - STAGES.indexOf(b))[0];
  view.innerHTML = `
    <p class="eyebrow"><a href="#/episodes">${esc(t("episodes"))}</a> / ${esc(d.episode.patient_ref)}</p>
    <section class="cp-card hero" style="margin-top:.5rem;animation:pm-rise .5s var(--cp-ease-out) both">
      <div class="hero__id"><span class="hero__avatar">${ic("user")}</span><div style="min-width:0"><h1>${esc(d.episode.patient_ref)}</h1>
        <p class="sub">${esc(t("pop_" + d.episode.population))} · ${esc(t("stage_" + d.episode.stage))}</p>
        <div class="cp-cluster">${riskBadge(d.overall_risk)}${canTr && d.next_stages.length ? `<button class="cp-btn" type="button" id="trBtn">${ic("arrow")}${esc(t("nextStage"))}</button>` : ""}</div></div></div>
      <div class="vitals">${vitals}</div></section>
    ${urgentBox}
    ${stepper(d.episode.stage)}
    <div class="guide"><section class="cp-card"><span class="guide__icon guide__icon--ai">${ic("pulse")}</span><div><h3>${esc(t("aiAdvice"))}</h3><p>${advice}</p>
        <p class="model-line" style="margin-top:.4rem">${esc(t("aiAssist"))}</p></div></section>
      <section class="cp-card"><span class="guide__icon guide__icon--next">${ic("check")}</span><div><h3>${esc(t("nextStep"))}</h3>
        <p>${nxt ? esc(t("stage_" + nxt)) : "—"}${d.discussion.length ? " · " + esc(t("disc_n", { n: d.discussion.length })) : ""}</p></div></section></div>
    <div class="ws">
      <nav class="ws__nav cp-card cp-card--flat" style="padding:.75rem" aria-label="sections">
        <a href="#sec-risk">${ic("chart")}${esc(t("sec_risk"))}</a><a href="#sec-ai">${ic("pulse")}${esc(t("sec_ai"))}</a>
        <a href="#sec-disc">${ic("list")}${esc(t("sec_disc"))}</a><a href="#sec-ev">${ic("clock")}${esc(t("sec_evidence"))}</a>
        ${canProto ? `<a href="#/e/${id}/protocol">${ic("doc")}${esc(t("sec_proto"))}</a>` : ""}
        <hr style="border:0;border-top:1px solid var(--cp-border);margin:.5rem 0">
        ${canUp ? `<a href="#/e/${id}/ecg">${ic("upload")}${esc(t("act_ecg"))}</a>` : ""}${canRisk ? `<a href="#/e/${id}/risk">${ic("chart")}${esc(t("act_risk"))}</a>` : ""}<a href="/episodes/${id}/report" target="_blank">${ic("printer")}${esc(t("print"))}</a><a href="/episodes/${id}/fhir" target="_blank">${ic("download")}HL7 FHIR R4</a>
      </nav>
      <div class="cp-stack">
        <section class="cp-card" id="sec-risk"><div class="cp-card__header"><h2 class="cp-card__title">${esc(t("sec_risk"))}</h2>${canRisk ? `<a href="#/e/${id}/risk">${esc(t("details"))} →</a>` : ""}</div>
          <div class="scores">${scoreBox(t("euroscore"), es, (e) => e.value + "%")}${scoreBox(t("thakar"), th, (e) => e.value + " " + t("points"))}
            ${d.episode.population === "adult" && !ra ? `<div class="score"><small>${esc(t("rachs"))}</small><b>—</b><span class="pill pill--muted">${esc(t("notApplicable"))}</span></div>` : scoreBox(t("rachs"), ra, (e) => e.value + t("category"))}${kd ? scoreBox("KDIGO AKI", kd, (e) => (typeof e.value === "object" && e.value.stage != null ? "Stage " + e.value.stage : "AKI")) : ""}${ecg_int ? scoreBox("QTc (Bazett)", ecg_int, (e) => (e.value && e.value.qtc_bazett_ms ? Math.round(e.value.qtc_bazett_ms) + " ms" : "—")) : ""}</div></section>
        ${pcg || d.episode.population === "pediatric" ? `<section class="cp-card"><h2 class="cp-card__title" style="margin-bottom:.5rem">${esc(t("heartMap"))}</h2>${heartMap(pcg)}
          <p class="cp-meta" style="text-align:center;margin:.25rem 0 0">${esc(pcg ? t("heartNote") : t("notRecorded"))}</p></section>` : ""}
        <section class="cp-card" id="sec-ai"><div class="cp-card__header"><h2 class="cp-card__title">${esc(t("sec_ai"))}</h2>${canUp ? `<a href="#/e/${id}/ecg">${esc(t("act_ecg"))} →</a>` : ""}</div>
          ${Object.entries(d.ai).map(([n, st]) => aiRow(n, st, L)).join("")}
          <div class="cp-doctor-notice" style="margin-top:.75rem">${esc(t("aiAssist"))}</div></section>
        <section class="cp-card" id="sec-disc"><h2 class="cp-card__title" style="margin-bottom:.5rem">${esc(t("sec_disc"))} <span class="badge-n">${d.discussion.length}</span></h2>
          ${d.discussion.length ? d.discussion.map((x) => `<div class="disc"><span class="cp-risk cp-risk--moderate" style="padding:.1rem .45rem"><span aria-hidden="true">!</span></span><div><b>${esc(x.topic)}</b><div class="cp-meta">${esc(x.reason)}</div></div></div>`).join("") : `<p class="sub">${esc(t("noDisc"))}</p>`}
          ${d.open_questions.length ? `<h3 style="font-size:var(--cp-text-sm);margin:1rem 0 .3rem">${esc(t("openQuestions"))}</h3><ul class="cp-meta">${d.open_questions.map((q) => `<li>${esc(q)}</li>`).join("")}</ul>` : ""}
          <div class="actions" style="margin-top:1rem">${canUp ? `<a class="cp-btn cp-btn--secondary" href="#/e/${id}/ecg">${ic("upload")}${esc(t("act_ecg"))}</a>` : ""}
            ${canRisk ? `<a class="cp-btn cp-btn--secondary" href="#/e/${id}/risk">${ic("chart")}${esc(t("act_risk"))}</a>` : ""}
            ${canProto ? `<a class="cp-btn cp-btn--secondary" href="#/e/${id}/protocol">${ic("doc")}${esc(t("act_proto"))}</a>` : ""}<button class="cp-btn cp-btn--secondary" type="button" id="csBtn">${ic("doc")}${esc(t("act_consent"))}</button>${["icu", "discharge", "guardian_30d"].includes(d.episode.stage) && canRisk ? `<button class="cp-btn cp-btn--secondary" type="button" id="kdBtn">${ic("chart")}${esc(t("act_kdigo"))}</button>` : ""}<a class="cp-btn cp-btn--secondary" href="/episodes/${id}/report" target="_blank">${ic("printer")}${esc(t("print"))}</a><a class="cp-btn cp-btn--secondary" href="/episodes/${id}/fhir" target="_blank">${ic("download")}FHIR R4</a>
            ${d.episode.stage === "screening" && can("screening.run") ? `<a class="cp-btn cp-btn--secondary" href="#/e/${id}/screening">${ic("steth")}${esc(t("act_screen"))}</a>` : ""}
            ${d.episode.stage === "guardian_30d" ? `<button class="cp-btn cp-btn--secondary" type="button" id="gLink">${ic("heart")}${esc(t("act_glink"))}</button>` : ""}</div></section>
      </div>
      <div class="cp-stack">
        <section class="cp-card" id="sec-ev"><div class="cp-card__header"><h2 class="cp-card__title">${esc(t("sec_evidence"))}</h2><span class="pill">${ep.evidence.length}</span></div>
          ${evidence.length ? `<ol class="timeline">${evidence.map((e) => `<li><div><b>${esc(kindLabel(e.kind))}${e.abstained ? "" : typeof e.value === "number" ? " · " + esc(e.value) + (e.unit && e.unit.length < 12 ? " " + esc(e.unit) : "") : ""}</b>
            <small>${esc(t("src_" + e.source))} · ${esc(hm(e.created_at))}${e.provenance && e.provenance.version ? " · " + esc(e.provenance.name) + " v" + esc(e.provenance.version) : ""}</small>
            ${e.abstained ? riskBadge(null, true) : ""}</div><span class="src src--${esc(e.source)}">${esc(t("src_" + e.source))}</span></li>`).join("")}</ol>` : `<p class="sub">${esc(t("noEvidence"))}</p>`}</section>
        ${d.concordance.length ? `<section class="cp-card"><h2 class="cp-card__title" style="margin-bottom:.5rem">${esc(t("sec_conc"))}</h2>${d.concordance.map(concChip).join("")}</section>` : ""}
      </div>
    </div>`;
  if ($("trBtn")) $("trBtn").onclick = () => transitionDialog(d);
  if ($("csBtn")) $("csBtn").onclick = () => consentDialog(d);
  if ($("kdBtn")) $("kdBtn").onclick = () => kdigoDialog(d);
  if ($("gLink")) $("gLink").onclick = () => dialog(`<h2 class="cp-dialog__title">${esc(t("act_glink"))}</h2>
      <div class="cp-field"><label class="cp-field__label" for="gInr">${esc(t("gl_inr"))}</label><select class="cp-select" id="gInr" name="inr">
        ${["", "mechanical_aortic", "mechanical_aortic_risk", "mechanical_mitral", "bioprosthetic", "af"].map((v) => `<option value="${v}">${esc(t("ind_" + (v || "none")))}</option>`).join("")}</select>
        <span class="cp-field__hint">${esc(t("gl_hint"))}</span></div><p class="cp-field__error" role="alert"></p>
      <div class="cp-dialog__actions"><button class="cp-btn cp-btn--secondary" value="cancel" formnovalidate>${esc(t("cancel"))}</button><button class="cp-btn" type="submit">${esc(t("gl_copy"))}</button></div>`,
    async (fd) => {
      const url = `${location.origin}/guardian?e=${d.episode.id}${fd.get("inr") ? "&inr=" + fd.get("inr") : ""}`;
      try { await navigator.clipboard.writeText(url); toast(t("glinkCopied")); } catch (e) { window.prompt(t("act_glink"), url); }
    });
}
function consentDialog(d) {
  if (!requireActor()) return;
  dialog(`<h2 class="cp-dialog__title">Bemor Yozma Klinik Roziligi</h2>
    <div class="cp-field"><label class="cp-field__label" for="csDoc">Shifokor (F.I.Sh.)</label><input class="cp-input" id="csDoc" name="clinician" required maxlength="120" value="${esc(actor())}"></div>
    <div class="cp-field" style="margin-top:.8rem"><label class="cp-field__label" for="csRef">Qog'oz blank raqami / formasi</label><input class="cp-input" id="csRef" name="paper_ref" required maxlength="60" placeholder="ROZ-2026/012"></div>
    <div class="cp-field" style="margin-top:.8rem"><label class="cp-field__label" for="csType">Rozilik turi</label><select class="cp-select" id="csType" name="consent_type">
      <option value="treatment_and_ai">Davolash va Sun'iy intellekt tahlili</option>
      <option value="surgery_and_ai">Jarrohlik amaliyoti va AI tahlili</option>
      <option value="telemedicine_guardian">Masofaviy monitoring (Guardian)</option>
    </select></div>
    <div class="cp-field" style="margin-top:.8rem"><label class="cp-field__label" for="csNote">Qo'shimcha izohlar</label><textarea class="cp-textarea" id="csNote" name="notes" maxlength="500"></textarea></div>
    <p class="cp-field__error" role="alert"></p>
    <div class="cp-dialog__actions"><button class="cp-btn cp-btn--secondary" value="cancel" formnovalidate>${esc(t("cancel"))}</button><button class="cp-btn" type="submit">Rasmiylashtirish</button></div>`,
  async (fd) => {
    await api(`/episodes/${d.episode.id}/consent`, {
      method: "POST",
      json: {
        actor: actor(),
        clinician: fd.get("clinician").trim(),
        paper_ref: fd.get("paper_ref").trim(),
        consent_type: fd.get("consent_type"),
        notes: fd.get("notes") ? fd.get("notes").trim() : null,
      }
    });
    toast("Yozma rozilik muhrlandi");
    route();
  });
}
function kdigoDialog(d) {
  if (!requireActor()) return;
  dialog(`<h2 class="cp-dialog__title">KDIGO 2012 AKI Baholash</h2>
    <div class="cp-field"><label class="cp-field__label" for="kdBase">Boshlang'ich kreatinin (mkmol/l)</label><input class="cp-input" type="number" step="0.1" id="kdBase" name="baseline" required min="10" max="1500" value="80"></div>
    <div class="cp-field" style="margin-top:.8rem"><label class="cp-field__label" for="kdCurr">Hozirgi kreatinin (mkmol/l)</label><input class="cp-input" type="number" step="0.1" id="kdCurr" name="current" required min="10" max="1500" value="120"></div>
    <div class="cp-field" style="margin-top:.8rem"><label class="cp-field__label" for="kdRise">48 soatlik o'sish (mkmol/l, ixtiyoriy)</label><input class="cp-input" type="number" step="0.1" id="kdRise" name="rise_48h" min="0" max="500"></div>
    <div class="cp-field" style="margin-top:.8rem"><label class="cp-field__label" for="kdDiurez">Soatlik diurez (ml/kg/soat, ixtiyoriy)</label><input class="cp-input" type="number" step="0.05" id="kdDiurez" name="urine_rate" min="0" max="10"></div>
    <div class="cp-field" style="margin-top:.8rem"><label class="cp-field__label"><input type="checkbox" name="rrt" value="true"> O'tkir gemodializ (RRT) o'tkazilmoqda</label></div>
    <p class="cp-field__error" role="alert"></p>
    <div class="cp-dialog__actions"><button class="cp-btn cp-btn--secondary" value="cancel" formnovalidate>${esc(t("cancel"))}</button><button class="cp-btn" type="submit">Baholash</button></div>`,
  async (fd) => {
    const payload = {
      actor: actor(),
      baseline_creatinine: parseFloat(fd.get("baseline")),
      current_creatinine: parseFloat(fd.get("current")),
      creatinine_48h_rise: fd.get("rise_48h") ? parseFloat(fd.get("rise_48h")) : null,
      urine_output_ml_kg_h: fd.get("urine_rate") ? parseFloat(fd.get("urine_rate")) : null,
      urine_hours: 6.0,
      rrt: fd.get("rrt") === "true",
    };
    await api(`/episodes/${d.episode.id}/kdigo`, { method: "POST", json: payload });
    toast("KDIGO AKI baholandi");
    route();
  });
}
function transitionDialog(d) {
  if (!requireActor()) return;
  const order = (s) => STAGES.indexOf(s);
  const next = [...d.next_stages].sort((a, b) => (order(a) > order(d.episode.stage) ? 0 : 1) - (order(b) > order(d.episode.stage) ? 0 : 1) || order(a) - order(b));
  dialog(`<h2 class="cp-dialog__title">${esc(t("tr_title"))}</h2>
    <div class="cp-field"><label class="cp-field__label" for="trTo">${esc(t("tr_to"))}</label><select class="cp-select" id="trTo" name="to">${next.map((s) => `<option value="${s}">${esc(t("stage_" + s))}</option>`).join("")}</select></div>
    <div class="cp-field" style="margin-top:.8rem"><label class="cp-field__label" for="trNote">${esc(t("tr_note"))}</label><textarea class="cp-textarea" id="trNote" name="note" maxlength="1000" required></textarea></div>
    <div class="cp-field" style="margin-top:.8rem"><label class="cp-field__label" for="trQ">${esc(t("tr_q"))}</label><textarea class="cp-textarea" id="trQ" name="q" maxlength="2000"></textarea></div>
    <p class="cp-field__error" role="alert"></p>
    <div class="cp-dialog__actions"><button class="cp-btn cp-btn--secondary" value="cancel" formnovalidate>${esc(t("cancel"))}</button><button class="cp-btn" type="submit">${esc(t("tr_go"))}</button></div>`,
  async (fd) => {
    await api(`/episodes/${d.episode.id}/transition`, { method: "POST", json: { from_stage: d.episode.stage, to_stage: fd.get("to"), author: actor(),
      note: fd.get("note").trim(), open_questions: fd.get("q").split("\n").map((s) => s.trim()).filter(Boolean) } });
    toast(t("saved")); route();
  });
}

/* ------------------------------------------------------------------ 4. EKG yuklash */
function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const names = lines[0].split(/[,;\t]/).map((s) => s.trim());
  const cols = names.map(() => []);
  for (let i = 1; i < lines.length; i++) { const v = lines[i].split(/[,;\t]/); for (let j = 0; j < names.length; j++) cols[j].push(parseFloat(v[j])); }
  return { names, cols };
}
function ecgSvg(names, cols, fs) {
  const W = 760, rowH = 42, H = rowH * names.length + 10, n = cols[0].length, secs = Math.min(n / fs, 10), pts = Math.min(n, Math.round(secs * fs));
  const step = Math.max(1, Math.floor(pts / 700));
  let grid = ""; for (let x = 40; x <= W; x += 36) grid += `<line class="grid" x1="${x}" y1="0" x2="${x}" y2="${H}"/>`;
  const rows = names.map((nm, r) => {
    const c = cols[r], y0 = 26 + r * rowH, p = [];
    for (let i = 0; i < pts; i += step) { const v = isFinite(c[i]) ? c[i] : 0; p.push(`${(40 + (i / pts) * (W - 50)).toFixed(1)},${(y0 - Math.max(-2, Math.min(2, v)) * 14).toFixed(1)}`); }
    return `<text x="4" y="${y0 + 4}">${esc(nm)}</text><polyline points="${p.join(" ")}"/>`;
  }).join("");
  return `<svg class="ecg-preview" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(t("preview"))}">${grid}${rows}</svg>`;
}
function plainCard(block, title) {
  const ev = block.evidence, p = block.plain;
  const risk = ev.abstained ? null : (levelToRisk[p.level] || ev.risk);
  const cls = ev.abstained ? "abstained" : p.level === "red" ? "high" : p.level === "yellow" ? "moderate" : p.level === "green" ? "low" : "unknown";
  return `<article class="cp-card cp-result cp-result--${cls}" ${cls === "high" ? "data-clinical-urgent" : ""}>
    <div class="cp-card__header" style="margin-bottom:.25rem"><span class="cp-meta" style="font-weight:700">${esc(title || (p.items[0] && p.items[0].title))}</span>${riskBadge(risk, ev.abstained)}</div>
    <h3 class="cp-result__headline">${esc(p.headline)}</h3>
    <p class="cp-result__action">${esc(t("whatToDo"))}: <span style="font-weight:500">${esc(p.todo)}</span></p>
    ${p.attention ? `<p class="cp-meta">${esc(p.attention)}</p>` : ""}
    <details class="cp-result__details"><summary class="cp-result__summary">${esc(t("details"))}</summary><ul class="cp-meta">${(ev.explanation || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></details>
    <p class="model-line">${esc(ev.provenance.name)} · v${esc(ev.provenance.version)}</p>
    <p class="cp-result__disclaimer">${esc(t("aiAssist"))}</p></article>`;
}
async function ecgPage(id) {
  const [d, models] = await Promise.all([api(`/episodes/${id}/digest`), api("/models")]);
  const card = models.ecg;
  view.innerHTML = `
    <div class="pagehead"><div><p class="eyebrow"><a href="#/e/${id}">${esc(d.episode.patient_ref)}</a> / ${esc(t("stage_" + d.episode.stage))}</p><h1>${esc(t("ecgTitle"))}</h1><p class="sub">${esc(t("ecgSub"))}</p></div>
      <a class="cp-btn cp-btn--secondary" href="#/e/${id}">${ic("back")}${esc(t("backToEp"))}</a></div>
    <div class="split3">
      <section class="cp-card"><h2 class="cp-card__title" style="margin-bottom:1rem">${esc(t("ecgUpload"))}</h2>
        <form id="ecgForm"><label class="cp-dropzone" id="drop">${ic("upload")}<b>${esc(t("ecgDrop"))}</b><span class="cp-meta">${esc(t("ecgFmt"))}</span>
          <input class="cp-dropzone__input" id="ecgFile" type="file" accept=".csv,text/csv" required></label>
          <div class="form-grid" style="margin-top:1rem"><div class="cp-field"><label class="cp-field__label" for="ecgFs">${esc(t("fs"))}</label>
            <select class="cp-select" id="ecgFs">${[500, 1000, 250, 100].map((f) => `<option value="${f}">${f} Hz</option>`).join("")}</select></div>
            <div class="cp-field"><label class="cp-field__label" for="ecgAge">${esc(t("age"))}</label><input class="cp-input" id="ecgAge" required type="number" min="0" max="120" step="1" inputmode="numeric"></div></div>
          <div class="cp-field"><label for="ecgMeasured">${esc(({uz:"EKG olingan sana va vaqt",ru:"Дата и время записи ЭКГ",en:"ECG acquisition date and time"})[lang])}</label><input class="cp-input" id="ecgMeasured" type="datetime-local"><span class="cp-field__hint">${esc(({uz:"Sana noma’lum bo‘lsa, bo‘sh qoldiring: natijalar vaqt bo‘yicha solishtirilmaydi.",ru:"Если дата неизвестна, оставьте пустым: сравнение по времени недоступно.",en:"Leave blank if unknown: temporal comparison will be unavailable."})[lang])}</span></div><div id="sig" class="cp-meta" style="margin-top:1rem"></div>
          <button class="cp-btn cp-btn--block" style="margin-top:1rem" type="submit" id="ecgGo" ${can("ai.upload") ? "" : "disabled"}>${ic("pulse")}${esc(t("analyze"))}</button>
          <p class="cp-field__error" id="ecgErr" role="alert"></p></form></section>
      <section><h2 class="section-title">${esc(t("aiResults"))}</h2><div id="ecgOut" class="cp-stack" aria-live="polite"><div class="cp-empty">${ic("pulse")}<span class="cp-meta">${esc(t("ecgDrop"))}</span></div></div></section>
      <div class="cp-stack"><section class="cp-card"><h2 class="cp-card__title" style="margin-bottom:.75rem">${esc(t("preview"))}</h2><div id="ecgPrev"><div class="cp-empty" style="padding:1.5rem"><span class="cp-meta">—</span></div></div>
          <p class="cp-meta" style="margin:.5rem 0 0">${esc(t("previewNote"))}</p></section>
        <section class="cp-card"><h2 class="cp-card__title" style="margin-bottom:.5rem">${esc(t("source"))}</h2><div class="kv">
          ${card ? `<div class="row"><span>${esc(t("m_model"))}</span><b>${esc(card.name)}</b></div><div class="row"><span>${esc(t("m_version"))}</span><b>v${esc(card.version)}</b></div>
          <div class="row"><span>${esc(t("m_dataset"))}</span><b>${esc(card.dataset)}</b></div><div class="row"><span>${esc(t("m_license"))}</span><b>${esc(card.dataset_license)}</b></div>` : `<p class="sub">—</p>`}
          <div class="row"><span>${esc(t("m_file"))}</span><b id="ecgName">—</b></div></div></section></div>
    </div>`;
  let parsed = null;
  const paintPreview = () => {
    if (!parsed) return;
    const fs = Number($("ecgFs").value), n = parsed.cols[0] ? parsed.cols[0].length : 0;
    $("ecgPrev").innerHTML = ecgSvg(parsed.names, parsed.cols, fs);
    $("sig").innerHTML = `<b>${esc(t("sig_quality"))}</b><div class="row"><span>${esc(t("leadsN", { n: parsed.names.length }))}</span>${parsed.names.length >= 12 ? '<span class="chk-ok">✓</span>' : '<span class="chk-no">!</span>'}</div>
      <div class="row"><span>${esc(t("seconds", { n: (n / fs).toFixed(1) }))}</span>${n / fs >= 8 ? '<span class="chk-ok">✓</span>' : '<span class="chk-no">!</span>'}</div>`;
  };
  $("ecgFile").addEventListener("change", async (e) => {
    const f = e.target.files[0]; if (!f) return;
    $("ecgName").textContent = f.name;
    try { parsed = parseCsv(await f.text()); paintPreview(); } catch (err) { parsed = null; }
  });
  $("ecgFs").addEventListener("change", paintPreview);
  $("ecgForm").addEventListener("submit", async (e) => {
    e.preventDefault(); $("ecgErr").textContent = "";
    if (!requireActor()) return;
    const f = $("ecgFile").files[0]; if (!f) return;
    const fd = new FormData(); fd.append("actor", actor()); fd.append("lang", lang); fd.append("fs", $("ecgFs").value);
    if ($("ecgAge").value !== "") fd.append("age_years", $("ecgAge").value);
    if ($("ecgMeasured").value) fd.append("measured_at", new Date($("ecgMeasured").value).toISOString());
    fd.append("file", f);
    const btn = $("ecgGo"); btn.disabled = true; btn.classList.add("cp-btn--loading");
    $("ecgOut").innerHTML = `<div class="cp-card cp-card--flat"><span class="cp-meta">${esc(t("analyzing", { t: hm(new Date().toISOString()) }))}</span></div>`;
    try {
      const r = await api(`/episodes/${id}/ecg`, { method: "POST", body: fd });
      const blocks = [plainCard(r, t("ai_ecg"))];
      if (r.low_ef) blocks.push(plainCard(r.low_ef, t("ai_ecg_low_ef")));
      if (r.structural) blocks.push(plainCard(r.structural, t("ai_ecg_shd")));
      if (r.escalation) blocks.unshift(`<div class="urgentbox" data-clinical-urgent>${ic("alert")}<div><b>${esc(t("escal"))}: ${esc(r.escalation.alert)}</b><p>${esc((r.escalation.reasons || []).join("; "))}</p></div></div>`);
      // natijalar darhol ko'rsatiladi: hech qanday kechiktirish yoki animatsiya yo'q
      $("ecgOut").innerHTML = blocks.join("");
    } catch (err) {
      $("ecgOut").innerHTML = ""; $("ecgErr").textContent = `${t("failed")}: ${err.message}`;
    }
    btn.disabled = false; btn.classList.remove("cp-btn--loading");
  });
}

/* ------------------------------------------------------------------ 5. Xavf baholash */
const ES_FLAGS = [["on_dialysis", "fl_dialysis"], ["extracardiac_arteriopathy", "fl_arteriopathy"], ["poor_mobility", "fl_mobility"], ["previous_cardiac_surgery", "fl_prevsurg"],
  ["chronic_lung_disease", "fl_lung"], ["active_endocarditis", "fl_endo"], ["critical_preop_state", "fl_critical"], ["insulin_diabetes", "fl_insulin"],
  ["ccs4_angina", "fl_ccs4"], ["recent_mi", "fl_mi"], ["thoracic_aorta", "fl_aorta"]];
async function riskPage(id, params) {
  const tab = params.get("tab") || "es";
  const d = await api(`/episodes/${id}/digest`);
  const okStage = ["heart_team", "icu"].includes(d.episode.stage);
  const tabs = `<div class="cp-tabs" role="tablist" style="margin-bottom:1rem">
    <a class="cp-tabs__tab" role="tab" aria-selected="${tab === "es"}" href="#/e/${id}/risk?tab=es" style="text-decoration:none">${esc(t("tab_es"))} <small class="cp-muted">${esc(t("tab_es_s"))}</small></a>
    <a class="cp-tabs__tab" role="tab" aria-selected="${tab === "rachs"}" href="#/e/${id}/risk?tab=rachs" style="text-decoration:none">${esc(t("tab_rachs"))} <small class="cp-muted">${esc(t("tab_rachs_s"))}</small></a></div>`;
  view.innerHTML = `<div class="pagehead"><div><p class="eyebrow"><a href="#/e/${id}">${esc(d.episode.patient_ref)}</a> / ${esc(t("stage_" + d.episode.stage))}</p><h1>${esc(t("riskTitle"))}</h1><p class="sub">${esc(t("riskSub"))}</p></div>
      <a class="cp-btn cp-btn--secondary" href="#/e/${id}">${ic("back")}${esc(t("backToEp"))}</a></div>
    ${okStage ? "" : `<div class="urgentbox urgentbox--warn">${ic("alert")}<div><b>${esc(t("stageWarn"))}</b></div></div>`}
    ${tabs}<div class="split"><section class="cp-card" id="riskForm"></section><section class="cp-card" id="riskOut" aria-live="polite"><p class="sub">—</p></section></div>`;
  if (tab === "rachs") return rachsForm(id, d, okStage);
  const sel = (name, opts, assumed) => `<select class="cp-select ${assumed ? "assumed" : ""}" id="${name}" name="${name}">${assumed ? `<option value="">${esc(t("notEntered"))}</option>` : ""}${opts.map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join("")}</select>`;
  const field = (id_, label, inner, hint) => `<div class="cp-field"><label class="cp-field__label" for="${id_}">${esc(label)}</label>${inner}${hint ? `<span class="cp-field__hint">${esc(hint)}</span>` : ""}</div>`;
  const num = (n, min, max, step) => `<input class="cp-input" id="${n}" name="${n}" type="number" min="${min}" max="${max}" step="${step}" inputmode="decimal" required>`;
  $("riskForm").innerHTML = `<form id="esForm">
    <fieldset><legend>${esc(t("f_patient"))}</legend><div class="form-grid">
      ${field("age", t("f_age"), num("age", 18, 95, 1))}${field("female", t("f_sex"), sel("female", [["false", t("f_male")], ["true", t("f_female")]]))}
      ${field("weight_kg", t("f_weight"), num("weight_kg", 20, 250, 0.1))}${field("creatinine_umol_l", t("f_creat"), num("creatinine_umol_l", 10, 2000, 1))}</div></fieldset>
    <fieldset><legend>${esc(t("f_heart"))}</legend><div class="form-grid">
      ${field("nyha", t("f_nyha"), sel("nyha", [["1", "I"], ["2", "II"], ["3", "III"], ["4", "IV"]], true), t("assumedChip"))}
      ${field("lvef_percent", t("f_lvef"), num("lvef_percent", 5, 90, 1))}
      ${field("lvef_measured_at", ({uz:"ExoKG o‘lchangan sana va vaqt (ma’lum bo‘lsa)",ru:"Дата и время измерения ЭхоКГ (если известны)",en:"Echo measurement date and time (if known)"})[lang], `<input class="cp-input" id="lvef_measured_at" name="lvef_measured_at" type="datetime-local">`)}
      ${field("pa_systolic_mmhg", t("f_pa"), `<input class="cp-input assumed" id="pa_systolic_mmhg" name="pa_systolic_mmhg" type="number" min="5" max="150" step="1">`, t("assumedChip"))}</div>
      <div class="form-grid" style="margin-top:.6rem">${[...ES_FLAGS, ["congestive_heart_failure", "fl_chf"], ["preop_iabp", "fl_iabp"]].map(([k, l]) => `<label class="check"><input type="checkbox" name="${k}">${esc(t(l))}</label>`).join("")}</div></fieldset>
    <fieldset><legend>${esc(t("f_op"))}</legend><div class="form-grid">
      ${field("urgency", t("f_urg"), sel("urgency", ["elective", "urgent", "emergency", "salvage"].map((u) => [u, t("urg_" + u)]), true), t("assumedChip"))}
      ${field("weight_of_intervention", t("f_weightop"), sel("weight_of_intervention", ["isolated_cabg", "single_non_cabg", "two", "three_plus"].map((w) => [w, t("w_" + w)]), true), t("assumedChip"))}
      ${field("surgery", t("f_surgery"), sel("surgery", ["cabg", "valve", "cabg_valve", "other"].map((s) => [s, t("s_" + s)])))}</div></fieldset>
    <button class="cp-btn" type="submit" ${okStage && can("risk.assess") ? "" : "disabled"}>${ic("chart")}${esc(t("calc"))}</button>
    <p class="cp-field__error" id="esErr" role="alert"></p></form>`;
  const es = d.latest["risk.euroscore2"]; if (es) paintEs({ evidence: [es], assumed_defaults: d.latest["risk.assumptions"] ? d.latest["risk.assumptions"].value : [] }, true);
  $("esForm").addEventListener("submit", async (e) => {
    e.preventDefault(); $("esErr").textContent = "";
    if (!requireActor()) return;
    const f = new FormData(e.target), b = (k) => f.get(k) === "on", n = (k) => Number(f.get(k));
    const euro = { age: n("age"), female: f.get("female") === "true", weight_kg: n("weight_kg"), creatinine_umol_l: n("creatinine_umol_l"),
      ...Object.fromEntries(ES_FLAGS.map(([k]) => [k, b(k)])) };
    if (f.get("nyha")) euro.nyha = n("nyha");
    if (f.get("urgency")) euro.urgency = f.get("urgency");
    if (f.get("weight_of_intervention")) euro.weight_of_intervention = f.get("weight_of_intervention");
    if (f.get("pa_systolic_mmhg")) euro.pa_systolic_mmhg = n("pa_systolic_mmhg");
    const aki = { female: euro.female, congestive_heart_failure: b("congestive_heart_failure"), lvef_percent: n("lvef_percent"), preop_iabp: b("preop_iabp"),
      copd: b("chronic_lung_disease"), insulin_diabetes: b("insulin_diabetes"), previous_cardiac_surgery: b("previous_cardiac_surgery"),
      emergency: ["emergency", "salvage"].includes(f.get("urgency")), surgery: f.get("surgery"), creatinine_umol_l: euro.creatinine_umol_l };
    try { paintEs(await api(`/episodes/${id}/risk`, { method: "POST", json: { actor: actor(), euroscore: euro, aki, lvef_measured_at: f.get("lvef_measured_at") ? new Date(f.get("lvef_measured_at")).toISOString() : null } })); }
    catch (err) { $("esErr").textContent = `${t("failed")}: ${err.message}`; }
  });
}
function paintEs(r, old) {
  const ev = r.evidence.find((e) => e.kind === "risk.euroscore2"), th = r.evidence.find((e) => e.kind === "risk.aki.rule"), ml = r.evidence.find((e) => e.kind === "risk.aki.model");
  const miss = r.assumed_defaults || [];
  const risk = ev && ev.risk, prov = ev && (ev.provenance || {});
  $("riskOut").innerHTML = `<div class="cp-card__header"><h2 class="cp-card__title">${esc(t("esResult"))}</h2>${miss.length ? `<span class="cp-risk cp-risk--moderate"><span aria-hidden="true">!</span>${esc(t("assumedWarn", { n: miss.length }).split(" — ")[0])}</span>` : ""}</div>
    ${ev && !ev.abstained ? `<p class="sub">${esc(t("esMort"))}</p><div style="max-width:220px">${gauge(ev.value, risk)}</div>${riskBadge(risk)}
      <p class="cp-meta">${esc(prov.name || ev.model || "euroscore2")} · ${esc(prov.version || ev.model_version || "")}</p>
      <h3 style="font-size:var(--cp-text-md);margin:1rem 0 .3rem">${esc(t("factors"))}</h3><div class="kv">${(ev.explanation || []).filter((x) => !x.startsWith("konstanta")).slice(0, 10).map((x) => `<div class="row"><span>${esc(x)}</span></div>`).join("")}</div>`
      : ev ? `${riskBadge(null, true)}<p class="cp-meta">${esc((ev.explanation || []).join("; "))}</p>` : ""}
    ${th ? `<div class="row" style="margin-top:.75rem"><span>${esc(t("thakar"))}</span><span>${th.abstained ? riskBadge(null, true) : `<b>${esc(th.value)} ${esc(t("points"))}</b> ${riskBadge(th.risk)}`}</span></div>` : ""}
    ${ml ? `<div class="row"><span>AKI (AI)</span>${ml.abstained ? riskBadge(null, true) : riskBadge(ml.risk)}</div>` : ""}
    ${miss.length ? `<div class="urgentbox urgentbox--warn" style="margin-top:1rem">${ic("alert")}<div><b>${esc(t("assumedWarn", { n: miss.length }))}</b><p>${esc(miss.join(", "))}</p></div></div>` : ""}
    <p class="cp-result__disclaimer">${esc(t("aiAssist"))}</p>`;
  if (!old) toast(t("saved"));
}
async function rachsForm(id, d, okStage) {
  const procs = (await api("/rachs1/procedures")).items;
  const byCat = {}; procs.forEach((p) => { (byCat[p.category_gt30d] = byCat[p.category_gt30d] || []).push(p); });
  $("riskForm").innerHTML = `<form id="raForm"><div class="form-grid">
      <div class="cp-field"><label class="cp-field__label" for="raAge">${esc(t("rachsAge"))}</label><input class="cp-input" id="raAge" type="number" min="0" max="6575" step="1" required></div>
      <label class="check" style="align-self:end"><input type="checkbox" id="raPrem">${esc(t("premature"))}</label></div>
    <fieldset style="margin-top:1rem"><legend>${esc(t("rachsProcs"))}</legend>
      ${Object.keys(byCat).sort().map((c) => `<div class="proc-group"><h4>${c}${esc(t("category"))}</h4>${byCat[c].map((p) => `<label class="check"><input type="checkbox" name="proc" value="${esc(p.code)}">${esc(p.name)}</label>`).join("")}</div>`).join("")}</fieldset>
    <button class="cp-btn" type="submit" ${okStage && can("risk.assess") ? "" : "disabled"}>${ic("chart")}${esc(t("calc"))}</button><p class="cp-field__error" id="raErr" role="alert"></p></form>`;
  const paint = (ev) => {
    $("riskOut").innerHTML = `<h2 class="cp-card__title">${esc(t("rachsResult"))}</h2>
      ${ev.abstained ? `${riskBadge(null, true)}<p>${esc((ev.explanation || []).join("; "))}</p>` : `<div class="big">${esc(ev.value)}<small style="font-size:1rem">${esc(t("category"))}</small></div>${riskBadge(ev.risk)}
      <div class="kv" style="margin-top:1rem">${(ev.explanation || []).map((x) => `<div class="row"><span>${esc(x)}</span></div>`).join("")}</div>`}
      <p class="cp-meta">Jenkins KJ et al. 2002</p>`;
  };
  if (d.latest["risk.rachs1"]) paint(d.latest["risk.rachs1"]);
  $("raForm").addEventListener("submit", async (e) => {
    e.preventDefault(); $("raErr").textContent = "";
    if (!requireActor()) return;
    const procedures = [...e.target.querySelectorAll("[name=proc]:checked")].map((c) => c.value);
    try { const r = await api(`/episodes/${id}/rachs1`, { method: "POST", json: { actor: actor(), procedures, age_days: Number($("raAge").value), premature: $("raPrem").checked } }); paint(r.evidence); toast(t("saved")); }
    catch (err) { $("raErr").textContent = `${t("failed")}: ${err.message}`; }
  });
}

/* ------------------------------------------------------------------ 6. Heart Team protokoli (server matni → A4 hujjat) */
function md(text) {
  const out = []; let table = null, list = null;
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`(.+?)`/g, "<code>$1</code>");
  const flush = () => { if (table) { out.push(`<table>${table.map((r, i) => `<tr>${r.map((c) => i === 0 ? `<th>${inline(c)}</th>` : `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</table>`); table = null; }
    if (list) { out.push(`<ul>${list.join("")}</ul>`); list = null; } };
  for (const line of text.split("\n")) {
    if (line.startsWith("|")) { if (/^\|[-\s|]+\|$/.test(line)) continue; (table = table || []).push(line.slice(1, -1).split("|").map((c) => c.trim())); continue; }
    if (/^- /.test(line)) { const m = line.match(/^- \[ \] (.*)/); (list = list || []).push(`<li>${m ? "☐ " + inline(m[1]) : inline(line.slice(2))}</li>`); continue; }
    flush();
    if (line.startsWith("# ")) out.push(`<h1>${inline(line.slice(2))}</h1>`);
    else if (line.startsWith("## ")) out.push(`<h2>${inline(line.slice(3))}</h2>`);
    else if (line.startsWith("> ")) out.push(`<blockquote>${inline(line.slice(2))}</blockquote>`);
    else if (line.trim()) out.push(`<p>${inline(line)}</p>`);
  }
  flush(); return out.join("");
}
async function protocolPage(id) {
  const [text, d] = await Promise.all([api(`/episodes/${id}/heart-team-protocol`), api(`/episodes/${id}/digest`)]);
  const hasRisk = !!(d.latest["risk.euroscore2"] || d.latest["risk.rachs1"]), hasAi = Object.values(d.ai).some((a) => a.state !== "not_run"), nDisc = d.discussion.length;
  const item = (ok, label) => `<li><span class="${ok ? "chk-ok" : "chk-no"}">${ok ? "✓" : "✕"}</span>${esc(label)}</li>`;
  view.innerHTML = `<div class="pagehead no-print"><div><p class="eyebrow"><a href="#/e/${id}">${esc(d.episode.patient_ref)}</a> / ${esc(t("stage_" + d.episode.stage))}</p><h1>${esc(t("protoTitle"))}</h1><p class="sub">${esc(t("protoSub"))}</p></div>
      <a class="cp-btn cp-btn--secondary" href="#/e/${id}">${ic("back")}${esc(t("backToEp"))}</a></div>
    <div class="split"><article class="doc">${md(text)}</article>
      <aside class="cp-card no-print"><h2 class="cp-card__title">${esc(t("readiness"))}</h2><ul class="ready">${item(hasRisk, t("rd_risk"))}${item(hasAi, t("rd_ai"))}${item(nDisc === 0, t("rd_disc", { n: nDisc }))}</ul>
        ${nDisc ? `<div class="urgentbox urgentbox--warn">${ic("alert")}<div><b>${esc(t("rd_block", { n: nDisc }))}</b></div></div>` : ""}
        <button class="cp-btn cp-btn--block" type="button" id="printBtn">${ic("printer")}${esc(t("print"))}</button></aside></div>`;
  $("printBtn").onclick = () => window.print();
}

/* ------------------------------------------------------------------ 7. Ogohlantirishlar */
async function alertsPage(params) {
  const status = params.get("status") || "open", level = params.get("level") || "";
  const data = await api(`/alerts?status=${status}${level ? "&level=" + level : ""}&limit=100`);
  if (status === "open" && !level) openAlerts = data.total;
  const link = (s, l) => `#/alerts?status=${s}${l ? "&level=" + l : ""}`;
  view.innerHTML = `<div class="pagehead"><div><p class="eyebrow">CardioPath</p><h1>${esc(t("alertsTitle"))} ${status === "open" && data.total ? `<span class="cp-risk cp-risk--high" style="font-size:var(--cp-text-sm);vertical-align:middle"><span aria-hidden="true">!</span>${data.total}</span>` : ""}</h1><p class="sub">${esc(t("alertsSub"))}</p></div>
      <button class="cp-btn cp-btn--secondary" type="button" id="refresh">${ic("pulse")}${esc(t("refresh"))}</button></div>
    <div class="infobar">${ic("shield")}<span>${esc(t("ackNote"))}</span></div>
    <div class="tablebar"><div class="cp-cluster"><a class="cp-btn ${status === "open" ? "" : "cp-btn--secondary"}" href="${link("open", level)}">${esc(t("tab_open"))}</a>
      <a class="cp-btn ${status === "acknowledged" ? "" : "cp-btn--secondary"}" href="${link("acknowledged", level)}">${esc(t("tab_acked"))}</a></div>
      <select class="cp-select" id="lvl" aria-label="level"><option value="">${esc(t("lvl_all"))}</option><option value="red" ${level === "red" ? "selected" : ""}>${esc(t("lvl_red"))}</option><option value="amber" ${level === "amber" ? "selected" : ""}>${esc(t("lvl_amber"))}</option></select></div>
    <div id="alertList">${data.items.length ? data.items.map((a) => `<article class="alert-item ${a.level === "red" ? "alert-item--red" : ""}" ${a.level === "red" ? "data-clinical-urgent" : ""}>
        <span class="alert-item__icon">${ic("alert")}</span>
        <div><h3>${esc(a.patient_ref)} · ${esc((a.reasons || [])[0] || a.source)} ${riskBadge(a.level === "red" ? "high" : "moderate")}</h3>
          <div class="cp-meta">${esc(ago(a.created_at))} · ${esc(a.source)}</div>
          ${(a.reasons || []).length > 1 ? `<p style="margin:.4rem 0 0">${esc(a.reasons.slice(1).join("; "))}</p>` : ""}
          <p style="margin:.4rem 0 0">${deliveryLine(a)}</p>
          ${a.acknowledged ? `<p class="cp-alert__status" style="color:var(--cp-success);margin:.4rem 0 0">${esc(t("ackedBy", { who: a.ack_by, t: ago(a.ack_at) }))}</p>` : ""}</div>
        <div class="acts"><a class="cp-btn" href="#/e/${esc(a.episode_id)}">${ic("open")}${esc(t("openEp"))}</a>
          ${!a.acknowledged && can("alerts.ack") ? `<button class="cp-btn cp-btn--secondary" type="button" data-ack="${a.id}">${ic("check")}${esc(t("ack"))}</button>` : ""}
          ${!a.acknowledged && a.delivery && a.delivery.status === "failed" ? `<button class="cp-btn cp-btn--secondary" type="button" data-resend="${a.id}">${ic("arrow")}${esc(t("resend"))}</button>` : ""}</div></article>`).join("")
      : `<div class="cp-empty">${ic("bell")}<span>${esc(t("noAlerts"))}</span></div>`}</div>`;
  $("lvl").onchange = (e) => { location.hash = link(status, e.target.value); };
  $("refresh").onclick = () => route();
  bindAck(() => route());
  view.querySelectorAll("[data-resend]").forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true;
    try { const a = await api(`/alerts/${b.dataset.resend}/resend`, { method: "POST" }); toast(a.delivery.status === "sent" ? t("saved") : t("dl_failed", { n: a.delivery.attempts }), a.delivery.status === "sent" ? undefined : "error"); route(); }
    catch (e) { toast(`${t("failed")}: ${e.message}`, "error"); b.disabled = false; }
  }));
  paintNav();
}


/* ------------------------------------------------------------------ 8. Modellar (governance) */
function keyMetric(card) {
  const m = card.metrics || {}, test = m.test || m.external_ptbxl || {};
  const find = (o, d = 0) => { if (!o || typeof o !== "object" || d > 2) return null;
    for (const [k, v] of Object.entries(o)) { if (/auroc/i.test(k) && typeof v === "number") return [k, v]; }
    for (const v of Object.values(o)) { const r = find(v, d + 1); if (r) return r; } return null; };
  if (typeof m.val_mae_pct === "number") return ["MAE", m.val_mae_pct + "%"];
  const r = find(test) || find(m); return r ? ["AUROC", Number(r[1]).toFixed(3)] : null;
}
async function modelsPage(params) {
  const [models, health_, learn, shadow] = await Promise.all([api("/models"), api("/health"),
    api("/learning/status").catch(() => null), can("shadow.report") || can("shadow.label") ? api("/shadow/report").catch(() => null) : null]);
  const cards = [];
  if (health_.pcg_model) cards.push({ key: "pcg", c: health_.pcg_model, st: "live", icon: "steth" });
  [["ecg", "pulse"], ["ecg_low_ef", "heart"], ["ecg_shd", "heart"], ["angio", "chart"], ["echo_ef", "heart"]].forEach(([k, icon]) => {
    if (models[k]) cards.push({ key: k, c: models[k], st: "live", icon });
  });
  (shadow && shadow.shadow_models || []).forEach((m) => cards.push({ key: "shadow:" + m, c: { name: m.split("@")[0], version: m.split("@")[1], dataset: "PTB-XL + Chapman + CPSC 2018 + Georgia", dataset_license: "CC-BY 4.0 / CC0", commercial_use: true, metrics: {} }, st: "shadow", icon: "pulse" }));
  Object.entries(models.blocked || {}).forEach(([k, why]) => cards.push({ key: "blocked:" + k, c: { name: k, version: "—", dataset: why }, st: "blocked", icon: "x" }));
  const sel = params.get("m") || (learn ? "pcg" : cards[0] && cards[0].key);
  const stPill = (st) => `<span class="pill ${st === "live" ? "pill--ok" : st === "blocked" ? "pill--bad" : "pill--ai"}">${esc(t("st_" + st))}</span>`;
  const grid = cards.map((x) => { const km = x.st === "live" ? keyMetric(x.c) : null;
    return `<a class="mcard ${x.key === sel ? "is-sel" : ""}" href="#/models?m=${encodeURIComponent(x.key)}"><div class="mcard__top"><span class="mcard__icon">${ic(x.icon)}</span>${stPill(x.st)}</div>
      <b>${esc(x.c.name)}</b><small>${esc(x.st === "blocked" ? x.c.dataset : (x.c.dataset || "") + " · v" + (x.c.version || ""))}</small>${km ? `<span class="mcard__metric">${esc(km[0])} <b>${esc(km[1])}</b></span>` : ""}</a>`; }).join("");
  const cur = cards.find((x) => x.key === sel);
  let detail = "";
  if (sel === "pcg" && learn) {
    const c = learn.latest_candidate;
    detail = `<section class="cp-card"><h2 class="cp-card__title">${esc(t("mg_learning"))}</h2>
      <div class="mg-kv"><div><small>${esc(t("mg_running"))}</small><b>${esc(learn.running_version)}</b></div><div><small>${esc(t("mg_current"))}</small><b>${esc(learn.current_version)}</b></div>
        ${learn.data ? `<div><small>Data</small><b>${learn.data.confirmed_children}</b></div>` : ""}</div>
      ${learn.restart_needed ? `<div class="urgentbox urgentbox--warn">${ic("alert")}<div><b>${esc(t("mg_restart"))}</b></div></div>` : ""}
      <h3 class="mg-h">${esc(t("mg_cand"))}</h3>
      ${!c ? `<p class="sub">${esc(t("mg_noCand"))}</p>` : `<p class="cp-meta">v${esc(c.version)} · ${esc(c.created_at || "")}</p><h3 class="mg-h">${esc(t("mg_gates"))}</h3>
        ${c.gates.map((g) => `<div class="cp-gate cp-gate--${g.passed ? "pass" : "fail"}"><span class="cp-gate__state">${g.passed ? "✓ " + esc(t("mg_pass")) : "✕ " + esc(t("mg_fail"))}</span><div><b>${esc(g.name)}</b><div class="cp-meta">${esc(g.detail)}</div></div></div>`).join("")}
        ${c.passed ? "" : `<div class="urgentbox" style="margin-top:1rem">${ic("alert")}<div><b>${esc(t("mg_failNote"))}</b></div></div>`}
        ${!authOn ? `<div class="cp-doctor-notice">${esc(t("mg_authOff"))} <code>${esc(c.promote_command || "")}</code></div>`
          : can("learning.approve") ? `<div class="actions" style="margin-top:1rem"><button class="cp-btn" type="button" id="mgApprove" ${c.passed ? "" : "disabled"}>${ic("check")}${esc(t("mg_approve"))}</button></div>` : ""}`}
      ${authOn && can("learning.approve") ? `<div class="actions" style="margin-top:1rem"><button class="cp-btn btn-danger-solid" type="button" id="mgRollback">${ic("back")}${esc(t("mg_rollback"))}</button></div>` : ""}
    </section>
    <section class="cp-card"><h2 class="cp-card__title" style="margin-bottom:1rem">${esc(t("mg_history"))}</h2>
      ${learn.history.length ? `<ol class="timeline">${[...learn.history].reverse().map((h) => `<li><div><b>${esc(h.event)} · ${esc(h.version || "")}</b><small>${esc(ago(h.at))} · ${esc(h.by || "")}${h.note ? " · " + esc(h.note) : ""}</small></div></li>`).join("")}</ol>` : `<p class="sub">${esc(t("mg_noHistory"))}</p>`}</section>`;
  } else if (cur) {
    const c = cur.c, km = keyMetric(c);
    detail = `<section class="cp-card"><div class="cp-card__header"><h2 class="cp-card__title">${esc(c.name)}</h2>${stPill(cur.st)}</div>
      ${cur.st === "blocked" ? `<p>${esc(c.dataset)}</p>` : `<div class="mg-kv"><div><small>${esc(t("mg_version"))}</small><b>v${esc(c.version)}</b></div><div><small>${esc(t("mg_data"))}</small><b>${esc(c.dataset)}</b></div>
        <div><small>${esc(t("mg_license"))}</small><b>${esc(c.dataset_license || "—")}</b><small>${esc(c.commercial_use ? t("mg_ok_com") : t("mg_research"))}</small></div>${km ? `<div><small>${esc(t("mg_metric"))}</small><b>${esc(km[0])} ${esc(km[1])}</b></div>` : ""}</div>
        ${c.task ? `<p class="cp-meta" style="margin-top:1rem">${esc(c.task)}</p>` : ""}
        ${cur.st === "shadow" ? `<div class="cp-doctor-notice" style="margin-top:1rem">${esc(t("mg_shadowNote"))}</div><a class="cp-btn" style="margin-top:1rem" href="#/shadow">${ic("pulse")}${esc(t("nav_shadow"))}</a>` : ""}`}</section>`;
  }
  view.innerHTML = `<div class="pm-in"><div class="pagehead"><div><p class="eyebrow">${esc(t("mg_eyebrow"))}</p><h1>${esc(t("mg_title"))}</h1><p class="sub">${esc(t("mg_sub"))}</p></div>
      <span class="pill pill--ai">${ic("shield")}${esc(t("mg_need"))}</span></div>
    <div class="mgrid">${grid}</div><div class="split">${detail}</div></div>`;
  const approve = $("mgApprove"), rb = $("mgRollback");
  if (approve) approve.onclick = () => dialog(`<h2 class="cp-dialog__title">${esc(t("mg_confirm"))}</h2>
      <div class="cp-field"><label class="cp-field__label" for="pn">${esc(t("mg_note"))}</label><input class="cp-input" id="pn" name="note" maxlength="300"></div><p class="cp-field__error" role="alert"></p>
      <div class="cp-dialog__actions"><button class="cp-btn cp-btn--secondary" value="cancel" formnovalidate>${esc(t("cancel"))}</button><button class="cp-btn" type="submit">${esc(t("mg_approve"))}</button></div>`,
    async (fd) => { await api("/learning/promote", { method: "POST", json: { version: learn.latest_candidate.version, note: fd.get("note") } }); toast(t("saved")); route(); });
  if (rb) rb.onclick = () => dialog(`<h2 class="cp-dialog__title">${esc(t("mg_rbConfirm"))}</h2>
      <div class="cp-field"><label class="cp-field__label" for="rn">${esc(t("mg_reason"))}</label><input class="cp-input" id="rn" name="note" minlength="5" maxlength="300" required></div><p class="cp-field__error" role="alert"></p>
      <div class="cp-dialog__actions"><button class="cp-btn cp-btn--secondary" value="cancel" formnovalidate>${esc(t("cancel"))}</button><button class="cp-btn btn-danger-solid" type="submit">${esc(t("mg_rollback"))}</button></div>`,
    async (fd) => { await api("/learning/rollback", { method: "POST", json: { note: fd.get("note") } }); toast(t("saved")); route(); });
}

/* ------------------------------------------------------------------ 9. Shadow — ko'r baholash */
async function shadowPage(params) {
  const canL = can("shadow.label"), canR = can("shadow.report");
  const [pend, rep] = await Promise.all([canL ? api("/shadow/pending?limit=200") : { items: [], labels: [] }, canR ? api("/shadow/report") : null]);
  const items = pend.items, sel = params.get("run") ? Number(params.get("run")) : (items[0] && items[0].run_id);
  const cur = items.find((x) => x.run_id === sel);
  const models = rep ? Object.entries(rep.models) : [];
  const first = models[0] && models[0][1];
  const nAf = first ? first.shadow_model.n_afib : 0, nNon = first ? first.shadow_model.n - first.shadow_model.n_afib : 0;
  const minA = rep ? rep.min_required.afib : 30, minN = rep ? rep.min_required.non_afib : 100;
  const pct = (v) => v === null || v === undefined ? "—" : (100 * v).toFixed(1) + "%";
  const prog = (label, n, m) => `<div class="sh-prog"><div><span>${esc(label)}</span><b>${n} / ${m}</b></div><div class="bars__track"><div class="bars__fill" style="width:${Math.min(100, (n / m) * 100)}%;background:var(--pm-grad)"></div></div></div>`;
  view.innerHTML = `<div class="pm-in"><div class="pagehead"><div><p class="eyebrow">${esc(t("sh_eyebrow"))}</p><h1>${esc(t("sh_title"))}</h1><p class="sub">${esc(t("sh_sub"))}</p></div>
      <span class="pill pill--ai">${ic("shield")}${esc(t("sh_blind"))}</span></div>
    <div class="split3">
      ${canL ? `<section class="cp-card"><h2 class="cp-card__title">${esc(t("sh_queue"))}</h2><p class="sub">${esc(t("sh_waiting", { n: items.length }))}</p>
        <div class="sh-queue">${items.length ? items.map((x) => `<a class="sh-item ${x.run_id === sel ? "is-sel" : ""}" href="#/shadow?run=${x.run_id}"><b>#${x.run_id}</b><small>${esc(hm(x.created_at))} · ${esc(ago(x.created_at))}</small></a>`).join("") : `<p class="sub">${esc(t("sh_none"))}</p>`}</div></section>` : ""}
      ${canL ? `<section class="cp-card"><h2 class="cp-card__title">${esc(t("sh_rate"))}</h2>
        <div class="infobar" style="margin:1rem 0">${ic("shield")}<span>${esc(t("sh_blind"))}</span></div>
        ${cur ? `<p class="cp-meta">${esc(t("sh_selected"))}: #${cur.run_id} · ${esc(hm(cur.created_at))}</p><p class="cp-doctor-notice">${esc(t("sh_orig"))}</p>
          <form id="shForm"><div class="rh-grid">${pend.labels.map((l) => `<label class="cp-guardian__choice rh"><input type="radio" name="rh" value="${l}" required>${esc(t("rh_" + l))}</label>`).join("")}</div>
          <p class="cp-field__error" id="shErr" role="alert"></p><button class="cp-btn" type="submit">${ic("check")}${esc(t("sh_save"))}</button></form>` : `<div class="cp-empty">${ic("check")}<span>${esc(t("sh_none"))}</span></div>`}</section>` : ""}
      ${canR ? `<section class="cp-card"><h2 class="cp-card__title">${esc(t("sh_report"))}</h2>
        <div class="${first && first.ready ? "infobar" : "urgentbox urgentbox--warn"}" style="margin:1rem 0">${ic("clock")}<div><b>${esc(first && first.ready ? t("sh_ready") : t("sh_early"))}</b></div></div>
        ${prog(t("sh_afib"), nAf, minA)}${prog(t("sh_nonafib"), nNon, minN)}
        <h3 class="mg-h">${esc(t("sh_compare"))}</h3>
        ${first && first.ready ? `<table class="cp-table" style="min-width:0"><tr><th></th><th>${esc(t("sh_live"))}</th><th>${esc(t("sh_shadowM"))}</th></tr>
            <tr><td>${esc(t("sh_sens"))}</td><td>${pct(first.live_model.sensitivity)}</td><td>${pct(first.shadow_model.sensitivity)}</td></tr>
            <tr><td>${esc(t("sh_spec"))}</td><td>${pct(first.live_model.specificity)}</td><td>${pct(first.shadow_model.specificity)}</td></tr>
            <tr><td>${esc(t("sh_fast"))}</td><td>${pct(first.live_model.fast_called_afib)}</td><td>${pct(first.shadow_model.fast_called_afib)}</td></tr>
            <tr><td>${esc(t("sh_agree"))}</td><td>—</td><td>${pct(first.rhythm_agreement)}</td></tr></table>`
          : `<div class="cp-empty">${ic("shield")}<b>${esc(t("sh_locked"))}</b><span class="cp-meta">${esc(t("sh_lockedNote"))}</span></div>`}
        <p class="cp-meta" style="margin-top:1rem">${esc(rep.shadow_models.join(", "))} · ${rep.runs} EKG · ${rep.labeled} ✓</p></section>` : ""}
    </div></div>`;
  const f = $("shForm");
  if (f) f.addEventListener("submit", async (e) => {
    e.preventDefault(); if (!requireActor()) return;
    const rh = new FormData(f).get("rh");
    try { await api(`/shadow/${cur.run_id}/label`, { method: "POST", json: { actor: actor(), rhythm: rh } }); toast(t("saved")); location.hash = "#/shadow"; route(); }
    catch (err) { $("shErr").textContent = `${t("failed")}: ${err.message}`; }
  });
}


/* ------------------------------------------------------------------ 10. Skrining (SpO₂ + klinik belgilar + yurak tovushi) */
async function screeningStart() {
  const data = can("episode.read") ? await api("/episodes?stage=screening&limit=50") : { items: [] };
  view.innerHTML = `<div class="pm-in"><div class="pagehead"><div><p class="eyebrow">${esc(t("sc_eyebrow"))}</p><h1>${esc(t("sc_title"))}</h1><p class="sub">${esc(t("sc_sub"))}</p></div></div>
    <div class="split"><section class="cp-card"><h2 class="cp-card__title">${esc(t("sc_cont"))}</h2>
        ${data.items.length ? episodeRows(data.items, "/screening") : `<p class="sub">${esc(t("sc_none"))}</p>`}</section>
      ${can("episode.create") ? `<section class="cp-card"><h2 class="cp-card__title" style="margin-bottom:1rem">${esc(t("sc_new"))}</h2><form id="scNew" class="cp-stack">
        <div class="cp-field"><label class="cp-field__label" for="scRef">${esc(t("ne_ref"))}</label><input class="cp-input" id="scRef" required maxlength="64" autocomplete="off"><span class="cp-field__hint">${esc(t("ne_refHint"))}</span></div>
        <div class="cp-field"><label class="cp-field__label" for="scPop">${esc(t("ne_pop"))}</label><select class="cp-select" id="scPop"><option value="pediatric">${esc(t("pop_pediatric"))}</option><option value="adult">${esc(t("pop_adult"))}</option></select></div>
        <p class="cp-field__error" id="scErr" role="alert"></p><button class="cp-btn" type="submit">${ic("arrow")}${esc(t("sc_start"))}</button></form></section>` : ""}</div></div>`;
  const f = $("scNew");
  if (f) f.onsubmit = async (e) => {
    e.preventDefault(); if (!requireActor()) return;
    try { const ep = await api("/episodes", { method: "POST", json: { patient_ref: $("scRef").value.trim(), population: $("scPop").value, actor: actor() } }); location.hash = `#/e/${ep.id}/screening`; }
    catch (err) { $("scErr").textContent = `${t("failed")}: ${err.message}`; }
  };
}
const LOC_POS = { AV: [104, 62], PV: [176, 58], TV: [92, 150], MV: [178, 156] };
async function audioInfo(file) {
  try {
    const Ctx = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    const audio = await new Ctx(1, 1, 44100).decodeAudioData(await file.arrayBuffer());
    const ch = audio.getChannelData(0), N = 48, step = Math.max(1, Math.floor(ch.length / N)), bars = [];
    for (let i = 0; i < N; i++) { let m = 0; for (let j = i * step; j < Math.min(ch.length, (i + 1) * step); j += 8) m = Math.max(m, Math.abs(ch[j])); bars.push(m); }
    const peak = Math.max(...bars, 1e-6); return { dur: audio.duration, bars: bars.map((b) => b / peak) };
  } catch (e) { return null; }
}
async function screeningPage(id) {
  const [d, flags] = await Promise.all([api(`/episodes/${id}/digest`), api(`/screening/red-flags?lang=${lang}`)]);
  const ped = d.episode.population === "pediatric";
  if (d.episode.stage !== "screening") {
    view.innerHTML = `<div class="pagehead"><div><p class="eyebrow"><a href="#/e/${id}">${esc(d.episode.patient_ref)}</a></p><h1>${esc(t("sc_title"))}</h1></div></div>
      <div class="urgentbox urgentbox--warn">${ic("alert")}<div><b>${esc(t("sc_wrongStage"))}</b></div></div><a class="cp-btn cp-btn--secondary" href="#/e/${id}">${ic("back")}${esc(t("backToEp"))}</a>`;
    return;
  }
  const files = {}, info = {};
  const num = (idn, min, max, ph) => `<input class="cp-input" id="${idn}" type="number" inputmode="numeric" min="${min}" max="${max}" step="1" ${ph ? `placeholder="${ph}"` : ""}>`;
  view.innerHTML = `<div class="pm-in"><div class="pagehead"><div><p class="eyebrow"><a href="#/e/${id}">${esc(d.episode.patient_ref)}</a> / ${esc(t("stage_screening"))}</p>
      <h1>${esc(t("sc_title"))}</h1><p class="sub">${esc(t("sc_sub"))}</p></div><a class="cp-btn cp-btn--secondary" href="#/e/${id}">${ic("back")}${esc(t("backToEp"))}</a></div>
    <form id="scForm" novalidate><div class="split3">
      <div class="cp-stack">
        <section class="cp-card"><h2 class="cp-card__title" style="margin-bottom:.75rem">${esc(t("sc_age"))}</h2>
          <div style="display:flex;gap:.5rem"><input class="cp-input" id="scAge" type="number" min="0" step="1" required inputmode="numeric" aria-label="${esc(t("sc_age"))}">
            <select class="cp-select" id="scUnit" style="max-width:8rem" aria-label="unit"><option value="1">${esc(t("u_day"))}</option><option value="30.44">${esc(t("u_month"))}</option><option value="365.25" selected>${esc(t("u_year"))}</option></select></div></section>
        <section class="cp-card"><h2 class="cp-card__title">${esc(t("sc_spo2"))}</h2><p class="cp-meta">${esc(t("sc_spo2Hint"))}</p>
          <div class="form-grid">${ped ? `<div class="cp-field"><label class="cp-field__label" for="scRh">${esc(t("sc_rh"))}</label>${num("scRh", 50, 100)}</div>
            <div class="cp-field"><label class="cp-field__label" for="scFoot">${esc(t("sc_foot"))}</label>${num("scFoot", 50, 100)}</div>
            <div class="cp-field"><label class="cp-field__label" for="scAtt">${esc(t("sc_attempt"))}</label><select class="cp-select" id="scAtt"><option>1</option><option>2</option></select></div>` : ""}
            <div class="cp-field"><label class="cp-field__label" for="scRest">${esc(t("sc_rest"))}</label>${num("scRest", 50, 100)}</div></div></section>
        <section class="cp-card"><h2 class="cp-card__title" style="margin-bottom:.5rem">${esc(t("sc_flags"))}</h2>
          ${Object.entries(flags).map(([code, f]) => `<label class="check"><input type="checkbox" name="flag" value="${esc(code)}">${esc(f.name)}${f.major ? ` <span class="pill pill--bad">${esc(t("sc_major"))}</span>` : ""}</label>`).join("")}</section>
      </div>
      <section class="cp-card"><h2 class="cp-card__title">${esc(t("sc_ausc"))}</h2><p class="cp-meta">${esc(t("sc_auscHint"))}</p>
        <div class="ausc"><svg class="heartmap" id="scMap" viewBox="0 0 280 230" role="group" aria-label="${esc(t("heartMap"))}"></svg><div id="scRows"></div></div>
        <div class="cp-field" style="margin-top:1rem"><label class="cp-field__label" for="scDev">${esc(t("sc_device"))}</label><input class="cp-input" id="scDev" maxlength="80"></div>
        <label class="check" style="margin-top:.5rem"><input type="checkbox" id="scConsent">${esc(t("sc_consent"))}</label>
        <p class="cp-field__error" id="scErr" role="alert"></p>
        <button class="cp-btn cp-btn--block" type="submit" id="scGo" style="margin-top:.75rem;min-height:52px">${ic("pulse")}${esc(t("analyze"))}</button></section>
      <section><h2 class="section-title">${esc(t("sc_result"))}</h2><div id="scOut" aria-live="polite"><div class="cp-empty">${ic("steth")}<span class="cp-meta">${esc(t("sc_auscHint"))}</span></div></div></section>
    </div></form></div>`;
  const paint = () => {
    $("scMap").innerHTML = `<path class="vessel" d="M128 70 C128 30 150 20 168 26"/><path class="vessel" d="M150 74 C156 44 186 36 204 46"/>
      <path class="body" d="M140 214 C84 182 60 140 66 100 C70 70 96 54 120 64 C130 68 136 74 140 82 C146 72 156 64 170 62 C200 58 222 84 216 118 C210 154 182 186 140 214Z"/>
      ${Object.entries(LOC_POS).map(([c, [x, y]]) => { const st = !files[c] ? "" : info[c] && info[c].dur < 5 ? "short" : "ok";
        return `<g class="loc-pt ${st}" data-loc="${c}" role="button" tabindex="0" aria-label="${esc(c)} — ${esc(t("loc_" + c))}"><circle class="pt" cx="${x}" cy="${y}" r="15"/><text x="${x}" y="${y + 4}" text-anchor="middle" class="pt-l">${c}</text></g>`; }).join("")}`;
    $("scRows").innerHTML = Object.keys(LOC_POS).map((c) => { const f = files[c], i = info[c];
      return `<div class="lrow2"><div><b>${c} · ${esc(t("loc_" + c))}</b><small>${esc(t("locw_" + c))}</small>
        ${f ? `<small>${esc(f.name)}${i ? ` · ${i.dur.toFixed(1)} s` : ""} · ${i && i.dur < 5 ? `<span class="chk-no">⚠ ${esc(t("sc_short"))}</span>` : `<span class="chk-ok">✓ ${esc(t("sc_ready"))}</span>`}</small>
          ${i ? `<svg class="wave" viewBox="0 0 48 10" preserveAspectRatio="none" aria-hidden="true">${i.bars.map((v, k) => `<rect x="${k}" y="${5 - v * 5}" width=".6" height="${Math.max(.5, v * 10)}"/>`).join("")}</svg>` : ""}` : ""}</div>
        <label class="cp-btn cp-btn--secondary" for="f_${c}" style="min-height:40px">${esc(t("choose"))}</label><input type="file" id="f_${c}" data-loc="${c}" accept=".wav,audio/wav,audio/x-wav" hidden></div>`; }).join("");
    view.querySelectorAll("input[type=file][data-loc]").forEach((inp) => inp.addEventListener("change", async () => {
      const c = inp.dataset.loc, f = inp.files[0]; if (!f) return; files[c] = f; info[c] = null; paint(); info[c] = await audioInfo(f); paint(); }));
    view.querySelectorAll(".loc-pt").forEach((g) => { const open = () => $("f_" + g.dataset.loc).click(); g.onclick = open; g.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } }; });
  };
  paint();
  $("scForm").addEventListener("submit", async (e) => {
    e.preventDefault(); $("scErr").textContent = "";
    if (!requireActor()) return;
    const age = $("scAge").value; if (age === "") { $("scErr").textContent = t("sc_needAge"); return; }
    const rh = $("scRh") ? $("scRh").value : "", foot = $("scFoot") ? $("scFoot").value : "";
    if (!!rh !== !!foot) { $("scErr").textContent = t("sc_needPair"); return; }
    const fd = new FormData();
    fd.append("actor", actor()); fd.append("lang", lang); fd.append("age_days", String(Math.round(Number(age) * Number($("scUnit").value))));
    if (rh) { fd.append("right_hand_spo2", rh); fd.append("foot_spo2", foot); fd.append("attempt", $("scAtt").value); }
    if ($("scRest").value) fd.append("resting_spo2", $("scRest").value);
    fd.append("red_flags", [...view.querySelectorAll("[name=flag]:checked")].map((c) => c.value).join(","));
    fd.append("research_consent", $("scConsent").checked ? "true" : "false"); fd.append("device", $("scDev").value.trim());
    Object.entries(files).forEach(([c, f]) => fd.append("recordings", f, `${c}.wav`));
    const btn = $("scGo"); btn.disabled = true; btn.classList.add("cp-btn--loading");
    $("scOut").innerHTML = `<div class="cp-card"><span class="cp-meta">${esc(t("analyzing", { t: hm(new Date().toISOString()) }))}</span></div>`;
    try {
      const r = await api(`/episodes/${id}/screening`, { method: "POST", body: fd });
      const p = (r.plain_i18n && r.plain_i18n[lang]) || r.plain;
      const cls = p.level === "red" ? "high" : p.level === "yellow" ? "moderate" : p.level === "green" ? "low" : "abstained";
      const risk = { red: "high", yellow: "moderate", green: "low" }[p.level];
      const icon = { red: "✕", yellow: "!", green: "✓" };
      // natija darhol; qizil bo'lsa animatsiyasiz (data-clinical-urgent)
      $("scOut").innerHTML = `<article class="cp-card cp-result cp-result--${cls}" ${cls === "high" ? "data-clinical-urgent" : ""}>
          <div class="cp-card__header" style="margin-bottom:.25rem"><span class="cp-meta" style="font-weight:700">${esc(t("sc_result"))}</span>${riskBadge(risk, !risk)}</div>
          <h3 class="cp-result__headline">${esc(p.headline)}</h3><p class="cp-result__action">${esc(t("whatToDo"))}: <span style="font-weight:500">${esc(p.todo)}</span></p>
          ${p.attention ? `<p class="cp-meta">${esc(p.attention)}</p>` : ""}${r.warning ? `<p class="cp-meta">${esc(r.warning)}</p>` : ""}
          <h4 style="margin:1rem 0 .3rem">${esc(t("sc_findings"))}</h4>
          ${p.items.map((i) => `<div class="disc"><span class="cp-risk cp-risk--${i.level === "red" ? "high" : i.level === "yellow" ? "moderate" : i.level === "green" ? "low" : "unknown"}" style="padding:.1rem .45rem"><span aria-hidden="true">${icon[i.level] || "?"}</span></span><div><b>${esc(i.title)}</b><div class="cp-meta">${esc(i.text)}</div></div></div>`).join("")}
          <p class="cp-result__disclaimer">${esc(t("aiAssist"))}</p></article>
        <div class="cp-card" style="margin-top:1rem;padding:1rem"><p style="margin:0">${esc(t("sc_echo"))}</p><a class="cp-btn" style="margin-top:.75rem" href="#/e/${id}">${ic("arrow")}${esc(t("backToEp"))}</a></div>`;
    } catch (err) { $("scOut").innerHTML = ""; $("scErr").textContent = `${t("failed")}: ${err.message}`; }
    btn.disabled = false; btn.classList.remove("cp-btn--loading");
  });
}


/* ------------------------------------------------------------------ 11. Foydalanuvchilar (administrator) */
const ROLE_LIST = ["clinician", "cardiologist", "surgeon", "icu", "admin", "patient"];

async function backupCard() {
  let b; try { b = await api("/backups"); } catch (e) { return ""; }
  const size = (n) => n > 1e6 ? (n / 1e6).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1e3)) + " KB";
  return `<section class="cp-card" style="margin-top:1rem"><div class="cp-card__header"><div><h2 class="cp-card__title">${esc(t("bk_title"))}</h2>
      <p class="sub">${esc(b.every_h > 0 ? t("bk_sub", { h: b.every_h, k: b.keep }) : t("bk_off"))}</p></div>
      <button class="cp-btn" type="button" id="bkNow">${ic("shield")}${esc(t("bk_now"))}</button></div>
    ${b.items.length ? `<ol class="timeline">${b.items.slice(0, 8).map((x) => `<li><div><b>${esc(x.created_at.replace("T", " "))}</b><small>${esc(x.name)} · ${size(x.size_bytes)}</small></div></li>`).join("")}</ol>` : `<p class="sub">${esc(t("bk_none"))}</p>`}
    <p class="cp-meta" style="margin-top:1rem">${esc(t("bk_where"))}: <code>${esc(b.dir)}</code></p><div class="cp-doctor-notice">${esc(t("bk_tip"))}</div></section>`;
}
function bindBackup() {
  const b = $("bkNow"); if (!b) return;
  b.onclick = async () => { b.disabled = true; try { await api("/backups", { method: "POST" }); toast(t("saved")); route(); } catch (e) { toast(`${t("failed")}: ${e.message}`, "error"); b.disabled = false; } };
}
async function usersPage() {
  if (!authOn) {
    view.innerHTML = `<div class="pm-in"><div class="pagehead"><div><p class="eyebrow">CardioPath</p><h1>${esc(t("us_title"))}</h1><p class="sub">${esc(t("us_sub"))}</p></div></div>
      <section class="cp-card"><div class="urgentbox urgentbox--warn">${ic("shield")}<div><b>${esc(t("us_authOff"))}</b><p>${esc(t("us_authSteps"))}</p></div></div>
      <h2 class="cp-card__title" style="margin:1rem 0 .5rem">${esc(t("us_role"))}</h2>
      ${ROLE_LIST.map((r) => `<div class="row"><b>${esc(t("role_" + r))}</b><span class="cp-meta">${esc(t("rd_" + r))}</span></div>`).join("")}</section>${await backupCard()}</div>`;
    bindBackup();
    return;
  }
  const [users, log] = await Promise.all([api("/users"), api("/audit/security?limit=40")]);
  const me = session && session.user.username;
  view.innerHTML = `<div class="pm-in"><div class="pagehead"><div><p class="eyebrow">CardioPath</p><h1>${esc(t("us_title"))}</h1><p class="sub">${esc(t("us_sub"))}</p></div>
      <button class="cp-btn" type="button" id="usAdd">${ic("plus")}${esc(t("us_add"))}</button></div>
    <section class="cp-card"><div class="cp-table-scroll"><table class="cp-table"><thead><tr><th>${esc(t("us_login"))}</th><th>${esc(t("us_role"))}</th><th>${esc(t("us_status"))}</th><th>${esc(t("us_actions"))}</th></tr></thead><tbody>
      ${users.map((u) => `<tr><td><span class="pt-ava" aria-hidden="true">${esc((u.display_name || u.username).slice(0, 2).toUpperCase())}</span><b>${esc(u.display_name)}</b>
          <div class="cp-meta">${esc(u.username)}${u.username === me ? " · " + esc(t("us_me")) : ""}</div></td>
        <td><span class="pill">${esc(t("role_" + u.role))}</span><div class="cp-meta">${esc(t("rd_" + u.role))}</div></td>
        <td>${u.active ? `<span class="pill pill--ok">✓ ${esc(t("us_active"))}</span>` : `<span class="pill pill--bad">✕ ${esc(t("us_disabled"))}</span>`}</td>
        <td><div class="actions">
          <button class="cp-btn cp-btn--secondary" type="button" data-role="${esc(u.username)}" data-cur="${esc(u.role)}">${esc(t("us_changeRole"))}</button>
          <button class="cp-btn cp-btn--secondary" type="button" data-reset="${esc(u.username)}">${esc(t("us_reset"))}</button>
          ${u.username === me ? "" : u.active ? `<button class="cp-btn cp-btn--secondary" type="button" data-off="${esc(u.username)}">${esc(t("us_disable"))}</button>`
            : `<button class="cp-btn" type="button" data-on="${esc(u.username)}">${esc(t("us_enable"))}</button>`}</div></td></tr>`).join("")}
    </tbody></table></div></section>
    <section class="cp-card" style="margin-top:1rem"><h2 class="cp-card__title">${esc(t("us_log"))}</h2><p class="sub">${esc(t("us_logSub"))}</p>
      <ol class="timeline" style="margin-top:1rem">${log.map((e) => { const key = "ev_" + e.action.replace(/\./g, "_"), d = e.detail || {};
        const extra = [d.username, d.role ? t("role_" + d.role) : null, d.version].filter(Boolean).join(" · ");
        return `<li><div><b>${esc(I[lang][key] ? t(key) : e.action)}</b><small>${esc(e.actor)} · ${esc(ago(e.at))}${extra ? " · " + esc(extra) : ""}</small></div>
          ${/failed/.test(e.action) ? `<span class="src" style="background:var(--cp-danger-bg);color:var(--cp-danger)">!</span>` : ""}</li>`; }).join("")}</ol></section>${await backupCard()}</div>`;
  bindBackup();
  const roleOpts = (cur) => ROLE_LIST.map((r) => `<option value="${r}" ${r === cur ? "selected" : ""}>${esc(t("role_" + r))} — ${esc(t("rd_" + r))}</option>`).join("");
  const patientId = async (code) => {
    if (!code) return null;
    const r = await api(`/episodes?q=${encodeURIComponent(code)}&limit=20`);
    const hit = r.items.find((e) => e.patient_ref.toLowerCase() === code.toLowerCase());
    if (!hit) throw new Error(t("us_noPatient"));
    return hit.id;
  };
  $("usAdd").onclick = () => dialog(`<h2 class="cp-dialog__title">${esc(t("us_add"))}</h2>
      <div class="cp-stack"><div class="cp-field"><label class="cp-field__label" for="uL">${esc(t("us_login"))}</label><input class="cp-input" id="uL" name="u" required maxlength="64" autocomplete="off"></div>
      <div class="cp-field"><label class="cp-field__label" for="uN">${esc(t("us_name"))}</label><input class="cp-input" id="uN" name="n" maxlength="80"></div>
      <div class="cp-field"><label class="cp-field__label" for="uR">${esc(t("us_role"))}</label><select class="cp-select" id="uR" name="r">${roleOpts("clinician")}</select></div>
      <div class="cp-field"><label class="cp-field__label" for="uC">${esc(t("us_patientCode"))}</label><input class="cp-input" id="uC" name="c" maxlength="64"></div>
      <div class="cp-field"><label class="cp-field__label" for="uP">${esc(t("us_pass"))}</label><input class="cp-input" id="uP" name="p" type="password" minlength="10" required autocomplete="new-password"></div>
      <div class="cp-field"><label class="cp-field__label" for="uP2">${esc(t("us_pass2"))}</label><input class="cp-input" id="uP2" name="p2" type="password" required autocomplete="new-password"></div></div>
      <p class="cp-field__error" role="alert"></p>
      <div class="cp-dialog__actions"><button class="cp-btn cp-btn--secondary" value="cancel" formnovalidate>${esc(t("cancel"))}</button><button class="cp-btn" type="submit">${esc(t("us_add"))}</button></div>`,
    async (fd) => {
      if (fd.get("p") !== fd.get("p2")) throw new Error(t("us_passMismatch"));
      const role = fd.get("r");
      await api("/users", { method: "POST", json: { username: fd.get("u").trim(), display_name: fd.get("n").trim(), role, password: fd.get("p"),
        episode_id: role === "patient" ? await patientId(fd.get("c").trim()) : null } });
      toast(t("saved")); route();
    });
  view.querySelectorAll("[data-off],[data-on]").forEach((b) => b.addEventListener("click", async () => {
    const u = b.dataset.off || b.dataset.on;
    try { await api(`/users/${encodeURIComponent(u)}/${b.dataset.off ? "disable" : "enable"}`, { method: "POST" }); toast(t("saved")); route(); }
    catch (e) { toast(`${t("failed")}: ${e.message}`, "error"); }
  }));
  view.querySelectorAll("[data-reset]").forEach((b) => b.addEventListener("click", () => dialog(`<h2 class="cp-dialog__title">${esc(t("us_reset"))} · ${esc(b.dataset.reset)}</h2>
      <div class="cp-field"><label class="cp-field__label" for="rP">${esc(t("us_pass"))}</label><input class="cp-input" id="rP" name="p" type="password" minlength="10" required autocomplete="new-password"></div>
      <div class="cp-field" style="margin-top:.8rem"><label class="cp-field__label" for="rP2">${esc(t("us_pass2"))}</label><input class="cp-input" id="rP2" name="p2" type="password" required autocomplete="new-password"></div>
      <p class="cp-field__error" role="alert"></p>
      <div class="cp-dialog__actions"><button class="cp-btn cp-btn--secondary" value="cancel" formnovalidate>${esc(t("cancel"))}</button><button class="cp-btn" type="submit">${esc(t("us_reset"))}</button></div>`,
    async (fd) => {
      if (fd.get("p") !== fd.get("p2")) throw new Error(t("us_passMismatch"));
      await api(`/users/${encodeURIComponent(b.dataset.reset)}/password`, { method: "POST", json: { new_password: fd.get("p") } }); toast(t("saved"));
    })));
  view.querySelectorAll("[data-role]").forEach((b) => b.addEventListener("click", () => dialog(`<h2 class="cp-dialog__title">${esc(t("us_changeRole"))} · ${esc(b.dataset.role)}</h2>
      <div class="cp-field"><label class="cp-field__label" for="cR">${esc(t("us_role"))}</label><select class="cp-select" id="cR" name="r">${roleOpts(b.dataset.cur)}</select></div>
      <div class="cp-field" style="margin-top:.8rem"><label class="cp-field__label" for="cC">${esc(t("us_patientCode"))}</label><input class="cp-input" id="cC" name="c" maxlength="64"></div>
      <p class="cp-field__error" role="alert"></p>
      <div class="cp-dialog__actions"><button class="cp-btn cp-btn--secondary" value="cancel" formnovalidate>${esc(t("cancel"))}</button><button class="cp-btn" type="submit">${esc(t("us_changeRole"))}</button></div>`,
    async (fd) => {
      const role = fd.get("r");
      await api(`/users/${encodeURIComponent(b.dataset.role)}/role`, { method: "POST", json: { role, episode_id: role === "patient" ? await patientId(fd.get("c").trim()) : null } });
      toast(t("saved")); route();
    })));
}


/* ------------------------------------------------------------------ 12. Yordam (qo'llanma) */
function helpPage() {
  const H = (window.CP_HELP || {})[lang] || (window.CP_HELP || {}).uz;
  if (!H) { view.innerHTML = ""; return; }
  view.innerHTML = `<div class="pm-in"><div class="pagehead"><div><p class="eyebrow">CardioPath</p><h1>${esc(H.title)}</h1><p class="sub">${esc(H.sub)}</p></div></div>
    <div class="help-grid">${H.sections.map((x, i) => `<section class="cp-card lift"><div class="help-h"><span class="mcard__icon">${ic(x.icon)}</span><h2 class="cp-card__title">${i + 1}. ${esc(x.h)}</h2></div>
      ${(x.p || []).map((t_) => `<p>${esc(t_)}</p>`).join("")}
      ${x.steps ? `<ol class="help-steps">${x.steps.map((t_) => `<li>${esc(t_)}</li>`).join("")}</ol>` : ""}
      ${x.list ? `<ul class="help-list">${x.list.map((t_) => `<li>${esc(t_)}</li>`).join("")}</ul>` : ""}</section>`).join("")}</div></div>`;
}

/* ------------------------------------------------------------------ ishga tushirish */
(async () => {
  if (!["light", "dark"].includes(store.get("theme"))) document.documentElement.dataset.theme = "dark";
  paintChrome();
  try { authOn = (await (await fetch("/auth/status")).json()).enabled; } catch (e) { /* */ }
  if (!authOn) { session = null; saveSession(); }
  else if (session) {
    try { const me = await api("/auth/me"); session.user = me.user; session.permissions = me.permissions; saveSession(); } catch (e) { session = null; saveSession(); }
  }
  try { health = await (await fetch("/health")).json(); } catch (e) { /* */ }
  paintChrome();
  route();
})();
})();

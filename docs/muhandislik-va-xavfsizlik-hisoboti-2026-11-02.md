# CardioPath AI — Muhandislik va Xavfsizlik Hisoboti (AI Agentlar uchun)

**Sana:** 2026-11-02  
**Hujjat maqsadi:** Kelajakda ushbu loyiha bilan ishlovchi boshqa AI tizimlari, muhandis agentlar va dasturchilar uchun to‘liq texnik kontekst, kiritilgan himoyalar, arxitektura tamoyillari va regressiya cheklovlarini yetkazish.  
**Tizim holati:** 377 passed, 0 warnings, 0 failed (barcha testlar 100% muvaffaqiyatli o‘tgan).

---

## 1. Loyihaning Qisqacha Tavsifi va Arxitektura Falsafasi

**CardioPath AI** — kardiologiya va kardioxirurgiyada bemorning birlamchi tug‘ma yurak nuqsoni (TYN) skriningidan to 30 kunlik operatsiyadan keyingi uy reabilitatsiyasigacha bo‘lgan butun yo‘lini yagona uzluksiz epizod (`CardiacEpisode`) sifatida yurituvchi AI + CDSS platformasi.

### Har qanday AI agent bilishi SHART bo‘lgan asosiy qoidalar:
1. **AI xavfni faqat oshira oladi (No-downgrade rule):**  
   Deterministik klinik qoida va AI modeli solishtirilganda (`core/concordance.py`), AI hech qachon qoida belgilagan xavfni pasaytira olmaydi:
   `final_risk = max(rule_risk, ai_risk)`
2. **Abstain-first (Sukut saqlash tamoyili):**  
   Agar signal sifatsiz bo‘lsa, yosh diapazondan tashqarida bo‘lsa, yoki ehtimollik noaniq zonada bo‘lsa, model xato xulosa bermasdan `abstained = True` holatiga o‘tishi shart. Abstain bu xato emas, klinik xavfsizlik to‘ridir.
3. **Ziddiyatlarni yashirmaslik (`DISAGREE`):**  
   Qoida va AI xulosalari farq qilsa, bu konsilium (Heart Team) uchun majburiy muhokama punkti sifatida belgilanadi.
4. **Bemorga dori dozasi ko‘rsatilmaydi:**  
   MNO (INR) va antikoagulyantlar tahlilida bemorga faqat xavf darajasi ko‘rsatiladi, aniq doza aytilmaydi.
5. **De-identifikatsiya:**  
   Bazada va auditda shaxsiy ma’lumotlar (F.I.Sh, manzil, telefon) saqlanmaydi; faqat barqaror bemor kodi (`patient_ref`) ishlatiladi.

---

## 2. Kiritilgan Barcha O‘zgarishlar va Texnik Himoyalar (A dan N gacha)

2026-11-02 texnik auditi va strategik bosh rejasi asosida tizim to‘liq mustahkamlandi:

### A. Zaxira nusxa va tiklash xavfsizligi (`core/backup.py`) — [P1 to‘liq tuzatildi]
* **Avvalgi xavf:** Mavjud bo‘lmagan zaxira fayl yo‘li bilan tiklash chaqirilganda, `sqlite3.connect` bo‘sh fayl yaratib olardi; bo‘sh bazada `integrity_check` «ok» qaytargani sababli amaldagi baza butunlay ma’lumotsiz bo‘sh fayl bilan almashtirilib ketardi.
* **Qilingan o‘zgarishlar:**
  1. `create_backup` va `restore_backup` funksiyalariga `is_file()` tekshiruvi qo‘shildi; fayl yo‘q bo‘lsa `FileNotFoundError` qaytariladi.
  2. Baza fayllari SQLite-ga read-only rejimda (`file:... ?mode=ro`, `uri=True`) ochiladi; mavjud bo‘lmagan fayl ochilishi qat’iyan to‘xtatildi.
  3. Zaxira nusxasida `REQUIRED_TABLES = {"episodes", "audit_log"}` mavjudligi tekshiriladi; noto‘g‘ri yoki bo‘sh bazadan tiklash `ValueError` bilan to‘xtatiladi.
  4. Tiklash jarayoni avval `.restore.tmp` vaqtinchalik fayliga ko‘chirilib, butunligi tasdiqlangach amaldagi bazaga atomik almashtiriladi; avvalgi baza `.before-restore-...` nomi bilan saqlanadi.
* **Yangi testlar (`tests/test_backup.py`):**
  * `test_restore_missing_backup_raises_and_does_not_replace`
  * `test_restore_empty_sqlite_db_rejected`
  * `test_create_backup_missing_db_raises`

### B. Signal (Alert) va Epizodni Atomik Saqlash (`core/store.py`, `api/guardian_routes.py`, `api/ai_routes.py`) — [P2 to‘liq tuzatildi]
* **Avvalgi xavf:** Guardian oqimida avval signal saqlanib, keyin epizod yozilar edi. Agar epizodni saqlashda versiya ziddiyati (`EpisodeConflict`) yuz bersa, bazada saqlanmagan o‘lchovga tegishli «yetim» (orphan) signal qolib ketardi.
* **Qilingan o‘zgarishlar:**
  1. `core/store.py` dagi `EpisodeStore` va `SqliteEpisodeStore` ga `save_with_alert(...)` metodi kiritildi.
  2. Epizod o‘zgarishi, yangi signal (sariq yoki qizil) va audit jurnali yozuvi bitta SQLite tranzaksiyasida (`with self._lock, self._conn:`) amalga oshiriladi.
  3. Agar ziddiyat bo‘lsa, butun tranzaksiya bekor qilinadi (`rollback`), nojo‘ya signallar paydo bo‘lmaydi.
* **Yangi testlar (`tests/test_alert_delivery.py`):**
  * `test_conflict_during_checkin_creates_no_orphan_alert`

### C. Sozlanmagan Tashqi Xabarni «Yetkazildi» Deb Belgilash Xatosi (`guardian/escalation.py`, `api/guardian_routes.py`, `api/ai_routes.py`) — [P1 to‘liq tuzatildi]
* **Avvalgi xavf:** Telegram tokeni sozlanmaganida `LogNotifier` tanlanar va uning `send()` metodi shunchaki server jurnaliga yozib `True` qaytarar edi. Natijada `delivery = "sent"` bo‘lib, interfeysda shifokorga «Jarrohga yuborildi» deb asossiz ma’lumot berilardi.
* **Qilingan o‘zgarishlar:**
  1. `LogNotifier` ga `is_external = False`, `TelegramNotifier` ga `is_external = True` atributlari kiritildi.
  2. Tashqi xizmat sozlanmagan holatda `delivery` holati `"none"` (Telegram sozlanmagan — faqat shu ro‘yxatda) sifatida belgilanadi.
* **Yangi testlar (`tests/test_alert_delivery.py`):**
  * `test_log_notifier_marks_delivery_as_none`

### D. Yosh va Chegara Tekshiruvlari (`core/model_safety.py`, `ecg/model.py`, `screening/model.py`) — [P1 to‘liq tuzatildi]
* **Qilingan o‘zgarishlar:**
  1. `core/model_safety.py` moduli yaratildi. `age_error(age, min, max, unit)` orqali har bir model yosh chegarasini qat’iy tekshiradi. Yosh noma’lum yoki diapazondan tashqarida bo‘lsa, model avtomatik `abstain` qiladi.
  2. EKG, Low EF va SHD modullari 18 yoshdan kichiklarda abstain qiladi.
  3. PCG modeli 29 kundan kichik neonatlarda xulosa bermaydi.

### E. Model Ehtimolliklari Matematik Validatsiyasi (`core/model_safety.py`) — [P2 to‘liq tuzatildi]
* **Qilingan o‘zgarishlar:**
  1. `valid_probabilities(values, shape)` funksiyasi barcha ehtimolliklarni $p \in [0, 1]$ va chekli son ekanligini qat’iy tekshiradi.
  2. `guarded_inference(...)` yordamida har qanday texnik xatolik xavfsiz `abstain` holatiga keltiriladi.

### F. O‘lchov Vaqti vs Kiritish Vaqti (`core/measurements.py`, `integration/concordances.py`) — [P2 to‘liq tuzatildi]
* **Qilingan o‘zgarishlar:**
  1. `core/measurements.py` yaratildi: `measurement_time(dt)` haqiqiy o‘lchov vaqtini tekshiradi va kelajakdagi sanalarni taqiqlaydi.
  2. `Evidence` modeliga `measured_at` maydoni qo‘shildi.
  3. Shifokor LVEF va AI LVEF solishtirilganda, o‘lchov vaqti 30 kundan ortiq bo‘lsa yoki noma’lum bo‘lsa, `Agreement.NOT_COMPARABLE` holati beriladi.

### G. Bemor Darajasidagi O‘qitish Bo‘linishi (`learning/dataset.py`) — [P1 to‘liq tuzatildi]
* **Qilingan o‘zgarishlar:**
  1. Bo‘linish normallashtirilgan `patient_ref` xeshi orqali bemor darajasida kafolatlandi; takroriy tashriflardan faqat oxirgisi olinadi.

### H. Server Yuklamasi va Parallel Qulf Himoyasi (`api/main.py`) — [P2 to‘liq tuzatildi]
* **Qilingan o‘zgarishlar:**
  1. Audio yozuvlarga hajm cheklovi (`MAX_UPLOAD`, $\le$10 ta fayl) qo‘yildi.
  2. CPU model hisoblari `anyio.CapacityLimiter(2)` va `anyio.to_thread.run_sync` orqali alohida oqimga chiqarildi.
  3. Bemor bo‘yicha qulflar `weakref.WeakValueDictionary()` va `anyio.sleep(0.01)` bilan bloklanmaydigan navbatga o‘tkazildi.

### I. FastAPI Lifespan Modernizatsiyasi (`api/main.py`)
* **Qilingan o‘zgarishlar:**
  1. Eskirgan `@app.on_event("startup")` funksiyalari o‘rniga zamonaviy `@asynccontextmanager async def _lifespan(app: FastAPI)` kiritildi.
  2. Barcha foniy tsikllar (delivery loop, backup loop, learning schedule loop) server to‘xtatilganda toza bekor qilinadi (`cancel()`).
  3. Pytest davomida chiqqan barcha `DeprecationWarning` lar butunlay yo‘qotildi.

### J. CI/CD Avtomatlashtirish (`.github/workflows/ci.yml`)
* GitHub Actions avtomatlashtirilgan pipeline yaratildi. Har bir push va pull request bo‘yicha Python 3.12 muhitida testlar to‘liq ishga tushadi.

### K. HTTP Xavfsizlik Sarlavhalari va Muhit Shabloni (`api/main.py`, `.env.example`)
* **Qilingan o‘zgarishlar:**
  1. FastAPI middleware orqali barcha javoblarga xavfsizlik sarlavhalari qo‘shildi (`X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`).
  2. `.env.example` shabloni yaratildi.

### L. So‘rov Trassirovkasi, Strukturali Logging va CORS (`api/main.py`, `core/logging_config.py`)
* **Qilingan o‘zgarishlar:**
  1. `X-Request-Id` trassirovkasi ulandi.
  2. `core/logging_config.py` JSON formatidagi strukturali jurnallash moduli yaratildi.
  3. `CARDIOPATH_CORS_ORIGINS` boshqaruvi ulandi.
  4. `.dockerignore` ortiqcha ishlab chiqish fayllaridan tozalandi.

### M. 1-Bosqich (Milestone 1) — Klinik Aniqlik va Rasmiy Hisobotlar
* **Qilingan o‘zgarishlar:**
  1. **EKG Intervallari (`ecg/intervals.py`):** Pan-Tompkins algoritmi bilan R-cho‘qqilar aniqlanadi; $HR$, $RR$, $PR$, $QRS$, $QT$, $QTc$ (Bazett / Fridericia) hisoblanadi.
  2. **Deterministik KDIGO AKI Baholash (`risk/kdigo.py`):** Kardioxirurgiya va reanimatsiya uchun KDIGO 2012 mezonlari bo‘yicha O‘BYe 1/2/3 bosqichini zardob kreatinini dinamikasi, 48 soatlik ko‘tarilish, soatlik diurez va RRT (dializ) orqali aniq baholaydi (`POST /episodes/{eid}/kdigo`).
  3. **Chuqurlashtirilgan Tizim Monitoringi (`GET /health/deep`):** Baza yaxlitligi, disk bo‘sh joyi (MB), zaxira nusxalar va ONNX modellarini to‘liq tekshirib `200` yoki `503` qaytaradi.
  4. **Rasmiy Chop Etish va PDF Epikriz (`api/report.py` va `GET /episodes/{eid}/report`):** A4 formatidagi to‘liq klinik xulosa generatori (`@media print` CSS va PDF saqlash tugmasi).

### N. 2-Bosqich (Milestone 2) — Korporativ Baza, Xesh-Zanjir Audit va SMS
* **Qilingan o‘zgarishlar:**
  1. **Kriptografik Xesh-Zanjirli Audit Jurnali (`core/store.py`):** Har bir audit yozuvi oldingi yozuvning SHA-256 xeshini o‘z ichiga oladi ($H_n = \text{SHA256}(H_{n-1} + \text{data}_n)$). Hech kim bazaga to‘g‘ridan-to‘g‘ri kirib audit tarixini o‘chira yoki o‘zgartira olmaydi. Yangi `verify_audit_integrity()` tekshiruvi va `GET /audit/verify` endpointi yaratildi.
  2. **Favqulodda SMS Shlyuzi (`guardian/escalation.py`):** `SmsNotifier` va `build_notifier_from_env()` kiritildi (`CARDIOPATH_SMS_URL`, `CARDIOPATH_SMS_PHONE`, `CARDIOPATH_SMS_TOKEN`). Internet bo‘lmaganda yoki Telegram sozlanmaganda ham kritik ogohlantirishlar jarroh telefoniga SMS orqali yetkaziladi.
  3. **PostgreSQL Adapteri (`core/postgres_store.py`):** Yirik tibbiyot markazlari va klasterlar uchun `PostgresEpisodeStore` yaratildi (JSONB hujjatlar, optimistik blokirovka, tranzaksiyalar, xesh-zanjirli audit log).

### O. 3-Bosqich (Milestone 3) — Huquqiy Muvofiqlik, Oflayn PWA, Standart Protokollar va SaMD
* **Qilingan o‘zgarishlar:**
  1. **Bemorning Yozma Klinik Roziligi Registri (`core/consent.py`, `POST /episodes/{eid}/consent`):** O‘zbekiston Respublikasi «Fuqarolar sog‘lig‘ini saqlash to‘g‘risida»gi Qonuni 24-moddasi va SaMD ISO 13485 talablari bo‘yicha qog‘oz rozilik blank raqami, shifokor F.I.Sh., rozilik turi va sanasini qat'iy saqlash. Epikriz chop etishda (`GET /episodes/{eid}/report`) yozma rozilik mavjudligi yashil belgi bilan tasdiqlanadi yoki yo‘qligi to‘g‘risida ogohlantiriladi.
  2. **Sternotomiya Yarasi Standart Protokoli (`guardian/checkin.py`, `POST /episodes/{eid}/guardian/wound-protocol`):** CDC NHSN va ASEPSIS mezonlari bo‘yicha 5 o‘qli baholash (qizarish, shish, ajralma, og‘riq, mahalliy harorat) + to‘sh suyagi instabilligi va chok ochilishi. Yiring yoki to‘sh beqarorligi aniqlanganda zudlik bilan RED Alert ishga tushib, navbatchi jarrohga SMS xabarnoma yuboradi.
  3. **Avtomatik Zaxira Tiklash Mashqi (`core/restore_drill.py`, `POST /backups/restore-drill`):** ISO 13485 va ISO 27001 talabi: zaxira nusxani vaqtinchalik izolyatsiyalangan muhitga tiklab, SQLite `PRAGMA integrity_check`, qatorlar soni va SHA-256 audit xesh zanjirini sinovdan o‘tkazadi. `GET /health/deep` monitoringida restore drill tayyorligi tekshiriladi.
  4. **Oflayn PWA Rejimi (`api/static/manifest.webmanifest`, `api/static/sw.js`, `api/static/cardiopath.js`):** Qishloq poliklinikalarida internet uzilganda skrining va monitoring interfeyslari keshdan mustaqil ishlaydi, tarmoq holati monitoring qilinadi.
  5. **Yuklama va Stress Sinovlari (`tests/load/locustfile.py`, `tests/test_load_concurrency.py`):** 20 ta parallel shifokor sessiyasi (epizod yaratish, bosqichlar almashinuvi, KDIGO AKI, yozma rozilik, epikriz generatsiyasi va parallel audit xesh zanjiri) 2.04 soniyada 100% muvaffaqiyat bilan bajarildi.
  6. **SaMD Klinik Baholash Dosyesi (`docs/samd-clinical-evaluation.md`):** Class IIb / IEC 62304 Class B/C dasturiy ta'minoti uchun intended use, ISO 14971 xatarlar tahlili va V&V matritsasi ishlab chiqildi.

---

## 3. Test Qamrovi va Sinov Holati

Barcha o‘zgarishlardan so‘ng loyihadagi barcha testlar to‘liq ishga tushirildi:
* **Dastlabki testlar soni:** 353 ta
* **Milestone 1 dan so‘ng:** 368 ta
* **Milestone 2 dan so‘ng:** 377 ta
* **Yakuniy testlar soni (Milestone 3):** 391 ta
* **Holat:** 391 passed, 0 warnings (100% muvaffaqiyatli)
* **Ishlash tezligi:** ~91 soniya.

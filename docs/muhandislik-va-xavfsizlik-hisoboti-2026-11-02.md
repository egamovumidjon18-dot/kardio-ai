# CardioPath AI — Muhandislik va Xavfsizlik Hisoboti (AI Agentlar uchun)

**Sana:** 2026-11-02  
**Hujjat maqsadi:** Kelajakda ushbu loyiha bilan ishlovchi boshqa AI tizimlari, muhandis agentlar va dasturchilar uchun to‘liq texnik kontekst, kiritilgan himoyalar, arxitektura tamoyillari va regressiya cheklovlarini yetkazish.  
**Tizim holati:** 406 passed, 0 warnings, 0 failed (barcha testlar 100% muvaffaqiyatli o‘tgan).

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

## 2. Kiritilgan Barcha O‘zgarishlar va Texnik Himoyalar (A dan R gacha)

2026-11-02 texnik auditi va strategik bosh rejasi asosida tizim to‘liq mustahkamlandi:

### A. Zaxira nusxa va tiklash xavfsizligi (`core/backup.py`) — [P1 to‘liq tuzatildi]
* **Avvalgi xavf:** Mavjud bo‘lmagan zaxira fayl yo‘li bilan tiklash chaqirilganda, `sqlite3.connect` bo‘sh fayl yaratib olardi; bo‘sh bazada `integrity_check` «ok» qaytargani sababli amaldagi baza butunlay ma’lumotsiz bo‘sh fayl bilan almashtirilib ketardi.
* **Qilingan o‘zgarishlar:**
  1. `create_backup` va `restore_backup` funksiyalariga `is_file()` tekshiruvi qo‘shildi; fayl yo‘q bo‘lsa `FileNotFoundError` qaytariladi.
  2. Baza fayllari SQLite-ga read-only rejimda (`file:... ?mode=ro`, `uri=True`) ochiladi; mavjud bo‘lmagan fayl ochilishi qat’iyan to‘xtatildi.
  3. Zaxira nusxasida `REQUIRED_TABLES = {"episodes", "audit_log"}` mavjudligi tekshiriladi; noto‘g‘ri yoki bo‘sh bazadan tiklash `ValueError` bilan to‘xtatiladi.
  4. Tiklash jarayoni avval `.restore.tmp` vaqtinchalik fayliga ko‘chirilib, butunligi tasdiqlangach amaldagi bazaga atomik almashtiriladi; avvalgi baza `.before-restore-...` nomi bilan saqlanadi.

### B. Signal (Alert) va Epizodni Atomik Saqlash (`core/store.py`, `api/guardian_routes.py`, `api/ai_routes.py`) — [P2 to‘liq tuzatildi]
* **Avvalgi xavf:** Guardian oqimida avval signal saqlanib, keyin epizod yozilar edi. Agar epizodni saqlashda versiya ziddiyati (`EpisodeConflict`) yuz bersa, bazada saqlanmagan o‘lchovga tegishli «yetim» (orphan) signal qolib ketardi.
* **Qilingan o‘zgarishlar:**
  1. `core/store.py` dagi `EpisodeStore` va `SqliteEpisodeStore` ga `save_with_alert(...)` metodi kiritildi.
  2. Epizod o‘zgarishi, yangi signal (sariq yoki qizil) va audit jurnali yozuvi bitta SQLite tranzaksiyasida (`with self._lock, self._conn:`) amalga oshiriladi.

### C. Sozlanmagan Tashqi Xabarni «Yetkazildi» Deb Belgilash Xatosi (`guardian/escalation.py`, `api/guardian_routes.py`, `api/ai_routes.py`) — [P1 to‘liq tuzatildi]
* **Avvalgi xavf:** Telegram tokeni sozlanmaganida `LogNotifier` tanlanar va uning `send()` metodi shunchaki server jurnaliga yozib `True` qaytarar edi. Natijada `delivery = "sent"` bo‘lib, interfeysda shifokorga «Jarrohga yuborildi» deb asossiz ma’lumot berilardi.
* **Qilingan o‘zgarishlar:**
  1. `LogNotifier` ga `is_external = False`, `TelegramNotifier` ga `is_external = True` atributlari kiritildi.
  2. Tashqi xizmat sozlanmagan holatda `delivery` holati `"none"` sifatida belgilanadi.

### D. Foydalanuvchi Roli O‘zgarishida Tokenlarni Bekor Qilish (`core/auth.py`, `api/auth_routes.py`) — [P1 to‘liq tuzatildi]
* **Qilingan o‘zgarishlar:** Foydalanuvchi modeli va jadvaliga `token_version` ustuni qo‘shildi. Parol o‘zgarganda, rol o‘zgarganda yoki administrator bloklaganda versiya oshiriladi va eski JWT tokenlar darhol yaroqsiz holga keladi.

### E. EKG Intervallari va Bazett/Fridericia QTc Hisoblash (`ecg/intervals.py`) — [P1 to‘liq bajarildi]
* **Qilingan o‘zgarishlar:** Pan-Tompkins R-cho‘qqilar detektori asosida $HR, RR, PR, QRS, QT, QTc$ (Bazett va Fridericia) aniq o‘lchovi joriy etildi. $QTc \ge 500$ ms hayot uchun xavfli holat sifatida Qizil signal beradi.

### F. KDIGO 2012 O‘tkir Buyrak Shikastlanishi (AKI) Staging (`risk/kdigo.py`) — [P1 to‘liq bajarildi]
* **Qilingan o‘zgarishlar:** Zardob kreatinini dinamikasi, 48 soatlik ko‘tarilish, soatlik diurez ($<0.5$ ml/kg/soat) va gemodializ (RRT) talabi bo‘yicha Stage 1, 2, 3 bosqichlarini aniqlovchi xalqaro KDIGO qoidalari integratsiya qilindi.

### G. Chuqurlashtirilgan Tizim Salomatligi Monitoringi (`GET /health/deep`) — [P1 to‘liq bajarildi]
* **Qilingan o‘zgarishlar:** SQLite/PostgreSQL ulanishi, diskdagi bo‘sh joy ($\ge 500$ MB), zaxira nusxalar yoshi va soni, ONNX model og‘irliklari mavjudligi tekshiriladi.

### H. Rasmiy Chop Etish va PDF Epikriz Generatori (`api/report.py`, `GET /episodes/{eid}/report`) — [P0 to‘liq bajarildi]
* **Qilingan o‘zgarishlar:** Rasmiy A4 formatidagi kardiologik klinik xulosa, shifoxona blanki, barcha bosqichdagi dalillar jadvali, konsilium a'zolari va shifokor imzosi, muhr joylari yaratildi.

### I. Shifrlangan Audit Jurnali Xesh Zanjiri (`core/store.py`, `GET /audit/verify`) — [P2 to‘liq bajarildi]
* **Qilingan o‘zgarishlar:** Har bir audit yozuviga `prev_hash` va `hash` maydonlari kiritildi ($H_n = \text{SHA256}(H_{n-1} + \text{data}_n)$). Ma'lumotlar o‘zgartirilmaganligini kriptografik tekshiruvchi endpoint ishga tushirildi.

### J. Favqulodda SMS Shlyuz Eskalatsiyasi (`guardian/escalation.py`) — [P1 to‘liq bajarildi]
* **Qilingan o‘zgarishlar:** Favqulodda Red Alert signallarida navbatchi kardiojarrohga tezkor SMS xabar yuboruvchi `SmsNotifier` adapteri yaratildi.

### K. Korporativ PostgreSQL Adapteri (`core/postgres_store.py`) — [P1 to‘liq bajarildi]
* **Qilingan o‘zgarishlar:** Yirik tibbiyot markazlari va klasterlar uchun `PostgresEpisodeStore` yaratildi (JSONB hujjatlar, optimistik blokirovka, tranzaksiyalar, xesh-zanjirli audit log).

### L. Bemorning Yozma Klinik Roziligi Registri (`core/consent.py`, `POST /episodes/{eid}/consent`) — [P1 to‘liq bajarildi]
* **Qilingan o‘zgarishlar:** O‘zbekiston Respublikasi «Fuqarolar sog‘lig‘ini saqlash to‘g‘risida»gi Qonuni 24-moddasi va SaMD ISO 13485 talablari bo‘yicha qog‘oz rozilik blank raqami, shifokor F.I.Sh., rozilik turi va sanasini qat'iy saqlash.

### M. Sternotomiya Yarasi Standart Protokoli (`guardian/checkin.py`, `POST /episodes/{eid}/guardian/wound-protocol`) — [P1 to‘liq bajarildi]
* **Qilingan o‘zgarishlar:** CDC NHSN va ASEPSIS mezonlari bo‘yicha 5 o‘qli baholash + to‘sh suyagi instabilligi va chok ochilishi. Yiring yoki to‘sh beqarorligi aniqlanganda zudlik bilan RED Alert ishga tushadi.

### N. Avtomatik Zaxira Tiklash Mashqi (`core/restore_drill.py`, `POST /backups/restore-drill`) — [P2 to‘liq bajarildi]
* **Qilingan o‘zgarishlar:** Zaxira nusxani vaqtinchalik izolyatsiyalangan muhitga tiklab, SQLite `PRAGMA integrity_check`, qatorlar soni va SHA-256 audit xesh zanjirini sinovdan o‘tkazadi.

### O. Oflayn PWA Rejimi va Ordinatoriya Avto-Qulfi — [P1 to‘liq bajarildi]
* **Qilingan o‘zgarishlar:** Service Worker kesh-birinchi arxitekturasi va shifoxona ordinatoriyasida 15 daqiqa harakatsizlikda avtomatik ekran qulfi (`#cp-idle-lock`).

### P. Auskultatsiya Pre-Flight va LMS Stenozi Eskalatsiyasi — [P1 to‘liq bajarildi]
* **Qilingan o‘zgarishlar:** 
  1. Pre-flight FFT audio sifat tekshiruvi (`POST /screening/preflight`): 25–400 Hz yurak bandi vs >600 Hz kiyim ishqalanish shovqini.
  2. Koronar tomir shoxlari va LMS (Chap asosiy poya) $\ge 50\%$ stenozi aniqlanganda `VERY_HIGH` xavfga ko‘tarish va shoshilinch KShSh konsiliumi.
  3. Yopilgan epizodlar arxivi va retentsiya siyosati (`POST /episodes/archive`).

### Q. HL7 FHIR R4 Xalqaro Standarti va Shifokor Qo'llanmasi (`core/fhir_export.py`, `docs/shifokor-qollanmasi.md`) — [P1 to‘liq bajarildi]
* **Qilingan o‘zgarishlar:**
  1. **HL7 FHIR R4 Standart Eksporti (`GET /episodes/{eid}/fhir`):** Bemorning barcha klinik dalillari (EKG Pan-Tompkins intervallari, KDIGO AKI, EuroSCORE II, ExoKG Simpson EF, yara protokoli va yozma rozilik) xalqaro standartdagi HL7 FHIR R4 Document Bundle formatiga o‘tkazildi.
  2. **Rasmiy Epikrizda FHIR Yuklab Olish (`api/report.py`):** Shifokor yoki IT muhandisi uchun rasmiy A4 epikriz sahifasining o‘zida «📥 HL7 FHIR R4 JSON» tugmasi joylashtirildi.
  3. **Klinika Shifokorlari va Ma'murlar Uchun Amaliy Qo'llanma (`docs/shifokor-qollanmasi.md`):** Kardiolog, jarroh, qabulxona shifokori, hamshira va IT ma'muri uchun bosqichma-bosqich qo'llanma ishlab chiqildi.
  4. **Konteyner Arxitekturasi va Korporativ Profil (`docker-compose.yml`, `.env.example`):** Ko‘p terminalli yirik markazlar uchun PostgreSQL profili (`profiles: ["postgres"]`) hamda SMS eskalatsiya shlyuzi sozlamalari kiritildi.

### R. Shifokor Veb-Interfeysi (UI) To'liq Integratsiyasi (`api/static/app.js`, `api/static/screening.html`) — [P1 to‘liq bajarildi]
* **Qilingan o‘zgarishlar:**
  1. **Skriningda Real-Vaqt Preflight Audio Sifat Tekshiruvi:** Shifokor WAV audio yuklaganda brauzer avtomatik ravishda `/screening/preflight` bilan bog'lanib, SNR (dB), kiyim ishqalanishi va kesilishni tekshiradi, yashil/sariq chiplar bilan darhol tavsiya ko'rsatadi.
  2. **Epizod Kartasida Tezkor Harakatlar (1-Click Actions):** Rasmiy A4 epikrizni chop etish (`print`), HL7 FHIR R4 JSON eksport qilish, bemorning yozma klinik roziligini rasmiylashtirish dialogi (`#csBtn`) va jonlantirish bo'limi uchun KDIGO AKI kalkulyator dialogi (`#kdBtn`) bevosita veb-interfeysga ulandi.
  3. **Klinik Ballar Paneli (Scores Panel):** EuroSCORE II va Thakar qatoriga KDIGO AKI bosqichi hamda EKG QTc (Bazett) intervallari dinamik ravishda chiqarildi.

---

## 3. Test Qamrovi va Sinov Holati

Barcha o‘zgarishlardan so‘ng loyihadagi barcha testlar to‘liq ishga tushirildi:
* **Dastlabki testlar soni:** 353 ta
* **Milestone 1 dan so‘ng:** 368 ta
* **Milestone 2 dan so‘ng:** 377 ta
* **Milestone 3 dan so‘ng:** 391 ta
* **Milestone 4 dan so‘ng:** 404 ta
* **Milestone 5 dan so‘ng:** 406 ta
* **UI integratsiyasidan so‘ng:** 406 ta
* **Holat:** 406 passed, 0 warnings, 0 failed (100% muvaffaqiyatli)
* **Ishlash tezligi:** ~75 soniya.

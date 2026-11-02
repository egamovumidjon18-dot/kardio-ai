# CardioPath AI — Mukammal Dasturga Aylantirish Bosh Rejasi (Master Roadmap)

**Hujjat sanasi:** 2026-11-02  
**Maqsad:** CardioPath AI platformasini tadqiqot prototipidan to‘liq sertifikatlangan, yirik shifoxona va viloyat tibbiyot markazlarida 24/7 rejimida xatosiz ishlaydigan mukammal kardiologik AI-CDSS (Klinik qarorlarni qo‘llab-quvvatlash tizimi) darajasiga yetkazish.  
**Joriy baza:** 358/358 test yashil (100%), 0 ogohlantirish, toza Git tarixi (`2382429`).

---

## 1. Strategik Yo‘nalishlar va Bosqichlar Xaritasi

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CARDIOPATH AI: MUKAMMAL TIZIM                   │
├────────────────────────────────────────────────────────────────────────┤
│ 1. AI & KLINIK MANTIQ    │ 2. MA'LUMOT VA BAZA    │ 3. SHIFOKOR UI/UX  │
│ • EKG intervallari (QTc) │ • PostgreSQL adapteri  │ • PDF Rasmiy epikriz│
│ • PCG Pre-flight audio   │ • DB shifrlash (rest)  │ • Offline PWA rejim│
│ • KDIGO AKI kalkulyator  │ • Bemor ma'lumot arxivi│ • Avto-blokirovkasi│
├──────────────────────────┼────────────────────────┼────────────────────┤
│ 4. HUQUQ VA XAVFSIZLIK   │ 5. POST-OP GUARDIAN    │ 6. DEVOPS & QA     │
│ • SaMD (ISO 13485)       │ • Favqulodda SMS shlyuz│ • Avto-restore drill│
│ • Bemor roziligi (audit) │ • Yara klinik savolnoma│ • Yuklama test (k6)│
│ • Xesh-zanjir audit      │ • Portativ MNO oqimi   │ • Kengaytirilgan HC│
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Yo‘nalishlar Bo‘yicha Batafsil Vazifalar Ro‘yxati

### 1-Yo‘nalish: Klinik AI va Diagnostik Mantiqni Mukammallashtirish

| # | Vazifa | Texnik talablar va Yechim | Ahamiyati |
|---|---|---|---|
| **1.1** | **EKG Intervallari va O‘lchovlari** | EKG signalidan faqat ritm (AFIB) emas, balki $PR$, $QRS$, va $QTc$ (Bazett / Fridericia) parametrlarini avtomatik hisoblash (`ecg/intervals.py`). QTc uzayishi ($\ge 460$ ms ayollarda, $\ge 450$ ms erkaklarda) uchun ogohlantirish. | Yuqori (P1) |
| **1.2** | **Auskultatsiya Pre-Flight Tekshiruvi** | Audio yuklanganda modelga kirmasdan oldin fon shovqini, kesilish (clipping) va signal/shovqin nisbatini (SNR) baholovchi modul. Agar mikrofon kiyimga ishqalangani sezilsa, shifokorga darhol «qayta yozing» tavsiyasi. | O‘rta (P2) |
| **1.3** | **Deterministik KDIGO AKI Baholash** | Thakar balliga qo‘shimcha ravishda operatsiyadan keyingi siydik miqdori ($<0.5$ ml/kg/soat) va zardob kreatinini dinamikasi bo‘yicha aniq KDIGO 1/2/3 bosqichini hisoblovchi qoida moduli (`risk/kdigo.py`). | Yuqori (P1) |
| **1.4** | **Stenoz Tomir Shoxlari Lokatsiyasi** | Angiografiyada stenoz nomzodi bilan birga asosiy tomir segmenti (LAD, LCx, RCA yoki LMS — chap asosiy poya) jalb qilinganligini kiritish uchun interfeys maydoni. LMS stenozida zudlik bilan RED xavf darajasiga ko‘tarish. | Yuqori (P1) |

---

### 2-Yo‘nalish: Ma’lumotlar Qatlami va Masshtablash (Enterprise Data Layer)

| # | Vazifa | Texnik talablar va Yechim | Ahamiyati |
|---|---|---|---|
| **2.1** | **PostgreSQL Adapteri (`PostgresEpisodeStore`)** | `core/store.py` dagi `EpisodeStore` interfeysi asosida `asyncpg`/`psycopg` adapterini yaratish. Viloyat markazlari va ko‘p serverli yuklama balanslagich (Load Balancer) orqasida parallel ishlash kafolati. | Yuqori (P1) |
| **2.2** | **Ma’lumotlarni Tinch Holatda Shifrlash (Encryption-at-Rest)** | Mahalliy SQLite uchun SQLCipher ulanmasi yoki Docker hajmlarida shifrlangan qatlam yo‘riqnomasi. Baza fayli jismoniy o‘g‘irlansa ham ochilmasligini ta’minlash. | Yuqori (P1) |
| **2.3** | **Yopilgan Epizodlar Arxivi va Retentsiya** | 30 kunlik nazorat tugab, epizod `CLOSED` bo‘lgach, faol ro‘yxatdan chiqarib, siqilgan arxiv jadvaliga (`episodes_archive`) ko‘chirish va 5 yillik qonuniy muddatdan keyin avtomatik anonimlashtirish. | O‘rta (P2) |

---

### 3-Yo‘nalish: Shifokor Interfeysi va Foydalanish Qulayligi (UI/UX)

| # | Vazifa | Texnik talablar va Yechim | Ahamiyati |
|---|---|---|---|
| **3.1** | **Chop Etish va Rasmiy Tibbiy Xulosa (Print / PDF)** | Bemor epizodining to‘liq xulosasini (Skrining kartasi / Heart Team konsilium dalolatnomasi / Chiqarish epikrizi) bitta tugma bilan A4 qog‘oziga chiroyli va rasmiy blankda chop etish (`@media print` CSS va PDF eksport). | Juda Yuqori (P0) |
| **3.2** | **Avtomatik Ekran Qulfi (Idle Auto-Lock)** | Umumiy shifoxona ordinatoriyasida kompyuter 15 daqiqa qarovsiz qolsa, ekranni qora fon bilan qulflash va davom ettirish uchun foydalanuvchidan parol so‘rash (HIPAA / GDPR talabi). | O‘rta (P2) |
| **3.3** | **Offline PWA Rejimi (Tuman poliklinikalari uchun)** | Internet tez-tez uzilib turadigan qishloq shifoxonalari uchun: Service Worker keshlaydi, pulsoksimetriya va klinik belgilarni lokal saqlab, internet kelganda avtomatik serverga sinxronizatsiya qiladi. | Yuqori (P1) |

---

### 4-Yo‘nalish: Huquqiy Muvofiqlik, SaMD va Xavfsizlik Standartlari

| # | Vazifa | Texnik talablar va Yechim | Ahamiyati |
|---|---|---|---|
| **4.1** | **Bemorning Yozma Roziligi Registri** | Har bir epizodda bemor (yoki ota-onasi) bergan yozma rozilik sanasi, kim tomonidan olinganligi va qog‘oz hujjat raqamini qat’iy saqlash (`Evidence("consent.clinical")`). | Yuqori (P1) |
| **4.2** | **Audit Jurnali Xesh Zanjiri (Tamper-Evident Trail)** | Audit jadvalidagi har bir yozuv oldingi yozuvning SHA-256 xeshini o‘z ichiga oladi ($H_n = \text{SHA256}(H_{n-1} + \text{data}_n)$). Hech kim bazaga to‘g‘ridan-to‘g‘ri kirib audit tarixini o‘chira yoki o‘zgartira olmaydi. | O‘rta (P2) |
| **4.3** | **Klinik Baholash Hujjatlari (ISO 13485 / IEC 62304 tayyorgarligi)** | Har bir AI modeli uchun rasmiy klinik baholash varaqasi (Model Intended Use, Clinical Limitations, Verification Matrix) shakllantirish. | O‘rta (P2) |

---

### 5-Yo‘nalish: 30 Kunlik Post-Op Guardian Ekotizimi

| # | Vazifa | Texnik talablar va Yechim | Ahamiyati |
|---|---|---|---|
| **5.1** | **Kasalxona Favqulodda SMS Shlyuzi (PlayMobile/Eskiz)** | Telegram sozlanmagan yoki internet yo‘q joylar uchun: RED signali (kritik MNO, jiddiy taxikardiya, yara infeksiyasi) tushganda jarrohning telefoniga zudlik bilan SMS yuboruvchi `SmsNotifier` adapteri. | Yuqori (P1) |
| **5.2** | **Sternotomiya Yara Fotosi Standart Protokoli** | Yara rasmi yuklanganda shifokorga noto‘g‘ri baholash xavfini yo‘qotish: rasm bilan birga 5 ta majburiy klinik belgi (qizarish, shish, ajralma, og‘riq, mahalliy harorat) talab qilinadi va rasm to‘g‘ridan-to‘g‘ri jarroh monitorida kattalashtirib ko‘rsatiladi. | Yuqori (P1) |

---

### 6-Yo‘nalish: Barqarorlik, DevOps va Sifat Kafolati (Reliability)

| # | Vazifa | Texnik talablar va Yechim | Ahamiyati |
|---|---|---|---|
| **6.1** | **Avtomatik Zaxira Tiklash Mashqi (Automated Restore Drill)** | Har hafta avtomatik zaxira nusxa olingach, fon vazifasi uni alohida vaqtinchalik xotiraga tiklab, `test_backup` va yaxlitlik tekshiruvlarini o‘tkazib ko‘radi. Buzilgan zaxiralar haqida zudlik bilan xabar beriladi. | O‘rta (P2) |
| **6.2** | **Yuklama Sinovlari (k6 / Locust Stress Tests)** | Bir vaqtning o‘zida 100 ta poliklinika audio va EKG yuborganda serverning javob berish vaqti va xotira sarfini o‘lchovchi test skripti (`tests/load/`). | O‘rta (P2) |
| **6.3** | **Chuqurlashtirilgan Tizim Sog‘lomligi (`GET /health/deep`)** | Faqat HTTP status emas, diskdagi bo‘sh joy ($\ge 5$ GB), SQLite qulf holati, model og‘irliklari butunligi va zaxira sanasini tekshiruvchi monitoring endpointi. | Yuqori (P1) |

---

## 3. Ketma-ketlik va Amalga Oshirish Bosqichlari (Milestones)

1. **1-Bosqich (Darhol bajariladigan — Yuqori samarali P0/P1) — [BAJARILDI ✅]:**
   - Rasmiy chop etish va PDF eksport (`@media print` va klinik epikriz formati).
   - EKG interval hisoblagichi ($PR$, $QRS$, $QTc$).
   - Deterministik KDIGO AKI baholash moduli.
   - Chuqurlashtirilgan sog‘lomlik tekshiruvi (`/health/deep`).
2. **2-Bosqich (Enterprise & Integratsiya) — [BAJARILDI ✅]:**
   - PostgreSQL adapteri (`PostgresEpisodeStore`).
   - Kasalxona favqulodda SMS shlyuzi (`SmsNotifier`).
   - Audit jurnali xesh zanjiri (Tamper-evident log).
3. **3-Bosqich (Sertifikatsiya va Dalada Qo‘llash) — [BAJARILDI ✅]:**
   - Bemorning rasmiy yozma klinik roziligi registri (`core/consent.py`, `POST /episodes/{eid}/consent`).
   - Sternotomiya yarasi standart 5 o‘qli ASEPSIS protokoli (`guardian/checkin.py`, `POST /episodes/{eid}/guardian/wound-protocol`).
   - Avtomatik zaxira tiklash mashqi (`core/restore_drill.py`, `POST /backups/restore-drill`).
   - Oflayn PWA rejimi (`sw.js`, `manifest.webmanifest`, `cardiopath.js`).
   - ISO/IEC SaMD klinik baholash hujjatlari to‘plami (`docs/samd-clinical-evaluation.md`).
   - Yuklama va stress testlari (`tests/load/locustfile.py`, `tests/test_load_concurrency.py`).

# CardioPath AI — loyiha tavsifi (dizayner AI uchun texnik va funksional hujjat)

Holat: 2026-yil 30-oktabr. Manba: loyiha kodi (`main` branch, 245 ta test; `feat/ai-models` branch'i 2026-10-30 da `main` bilan birlashtirildi), muallifning o'z maqsad hujjati va o'qitish/baholash hisobotlari.

## 0. Bu hujjatni qanday o'qish kerak

Bu hujjat **dizayn tavsiya qilmaydi**: rang, uslub, animatsiya va interfeys elementlari haqida hech narsa aytilmaydi. Faqat nimaligi, nima qilishi va nima kiradi-chiqishi yoziladi.

Har bir imkoniyat quyidagi belgilardan biri bilan belgilangan:

| Belgi | Ma'nosi |
|---|---|
| **[MAVJUD]** | `main` branch'da kodi bor, ishlaydi, testlangan. |
| **[FAQAT API]** | Server tomoni (mantiq va endpoint) bor, lekin foydalanuvchi ekrani yo'q. |
| **[REJADA]** | Muallif rejalashtirgan, kodi yo'q. |
| **[NOMA'LUM]** | Menda ma'lumot yo'q. Hujjatda o'ylab topilmagan. |

Muhim ogohlantirish: dastur **tadqiqot rejimida**, tibbiy qurilma sifatida ro'yxatdan o'tmagan, klinikada tasdiqlanmagan. Hamma natija «yakuniy tashxis emas, shifokorga yordam» degan ma'noda.

---

## 1. Loyihaning asl maqsadi

### 1.1. Qanday muammoni hal qiladi
Kardiologiya va kardioxirurgiyada bemor ko'pincha **bo'laklarga bo'linib** boradi: tuman shifokori, kardiolog, kardioxirurg, reanimatsiya, so'ng uyda nazorat. Har bir bosqich o'z ma'lumotini alohida yuritadi. Natijada:
- tumandagi shifokorda ExoKG yo'q yoki qimmat, tug'ma yurak nuqsonli bola kech aniqlanadi;
- operatsiya oldi qarorni (Heart Team) turli shkalalar va fikrlar asosida qabul qilishadi;
- operatsiyadan keyingi eng xavfli 30 kunda bemor uyda, shifokor ko'rmaydigan joyda qoladi (varfarin/MNO nazorati, yara infeksiyasi, yurak yetishmovchiligi belgilari).

Aniq raqamlar: ESC eAtlas (2022) bo'yicha O'zbekistonda tug'ma yurak nuqsoni bo'yicha jarrohlik aralashuvlari har million aholiga ~101.5 ta. Toshkent tajribasi haqidagi 2020-yilgi maqolaga ko'ra, bunday bolalarning ko'pchiligi o'z vaqtida jarrohlik yordami olmaydi. O'zbekiston bo'yicha milliy kasallik registri topilmadi.

### 1.2. Yechim g'oyasi
Beshta alohida AI vositasi emas, **bitta uzluksiz klinik epizod**: bemorning butun yo'li (skriningdan uy nazoratigacha) bitta yozuv sifatida yuritiladi. Har bir bosqich shu yozuvga yozadi va undan o'qiydi. Bosqichlar orasidagi o'tish tuzilgan «yo'llanma» (Handoff) orqali bo'ladi.

### 1.3. Muallif aytgan beshta bo'g'in (yakuniy konsepsiya)
1. **Pediatrik va birlamchi skrining** (tug'ma yurak nuqsoni): auskultatsiya tovushi, pulsoksimetriya, klinik «qizil bayroqlar».
2. **ExoKG diagnostikasi**: chap qorincha otilish fraksiyasi (EF), regional devor harakati, klapan regurgitatsiyasi.
3. **Intervension kardiologiya va intraoperatsion yordam**: koronar angiografiyada stenoz (SYNTAX mantiqi), torakoskopik video oqimda xavfli zonalar.
4. **Operatsiya oldi va reanimatsiya xavf tahlili**: EuroSCORE II / STS (kattalar), RACHS-1 (bolalar), operatsiyadan keyingi asoratlar (o'tkir buyrak zararlanishi, aritmiya), Heart Team uchun yagona protokol.
5. **30 kunlik «Post-Op Guardian»**: uydagi bemorni masofadan nazorat qilish va xavfda operatsiya qilgan jarrohga signal.

### 1.4. Ikki maqsadli loyiha
Tizim bir vaqtda (a) xalqaro jurnal uchun **ilmiy tadqiqot** va (b) amaliyotdagi shifokor va bemorlar uchun **ishlaydigan mahsulot** bo'lishi kerak. Shu sabab har bir model uchun ma'lumot litsenziyasi kuzatiladi (tadqiqotga ruxsat etilgan ma'lumot bilan mahsulotga ruxsat etilganini ajratish uchun).

### 1.5. Xavfsizlik tamoyillari (mahsulot talablari, kodda amalga oshirilgan)
1. **Shifokorni almashtirmaydi.** Har bir natija bilan «yakuniy tashxis emas» yozuvi chiqadi.
2. **AI xavfni faqat oshirishi mumkin, hech qachon pasaytirmaydi.** Yakuniy xavf = qoida va AI xavfidan kattasi.
3. **Qoida va AI zid bo'lsa, bu yashirilmaydi**, shifokor muhokamasiga belgilanadi.
4. **AI ishonchsiz bo'lsa, javob bermaydi (abstain)** va sababini aytadi. Bu xato emas, xavfsizlik mexanizmi.
5. **Bemorga doza aytilmaydi.** Varfarin bo'yicha faqat «me'yorda / shifokorga murojaat qiling» turidagi xabar ketadi.
6. **Shaxsiy ma'lumot saqlanmaydi.** Bemor ism-familiya bilan emas, **kod (psevdonim)** bilan yuritiladi.
7. **Litsenziya nazorati.** Faqat tadqiqot uchun ruxsat etilgan ma'lumotda o'qitilgan model «mahsulot rejimi»da avtomatik bloklanadi.
8. **Dastur o'zini o'zi o'rgatadi, lekin modelni o'zi almashtirmaydi.** Yangi tasdiqlangan holatlardan nomzod model avtomatik o'qitiladi va avtomatik darvozalardan o'tkaziladi; joriy qilish faqat ismi aniq ko'rsatilgan shifokor tasdig'i bilan, orqaga qaytarish mumkin (3.4.1).

### 1.6. Beshta bo'g'inning hozirgi holati

| Bo'g'in | Holat |
|---|---|
| 1. Pediatrik skrining | **[MAVJUD]** to'liq ishlaydi: qoidalar + yurak tovushi AI + ekran. |
| 2. ExoKG | Qo'lda ExoKG tashxisini kiritish **[MAVJUD]**. EF modeli **[FAQAT API]** (NeuroSon loyihasidan adapter, tashqi og'irlikka bog'liq). Regional devor harakati va klapan tahlili **[REJADA]**. |
| 3. Intervension / intraoperatsion | Angiografiya stenoz nomzodlari **[FAQAT API]**, model o'qitilgan (4.6-bo'lim). Intraoperatsion video **[REJADA]**, muzlatilgan (ochiq ma'lumot yo'q). |
| 4. Xavf tahlili | EuroSCORE II, Thakar balli, Heart Team protokoli **[FAQAT API]**. AKI uchun ML modeli **[REJADA]** (ma'lumotga ruxsat kerak). RACHS-1 va STS **[REJADA]**. |
| 5. Post-Op Guardian | Qoidalar, MNO, eskalatsiya **[FAQAT API]**. MNO qog'ozini rasmdan o'qish **[FAQAT API]**. Bemor ilovasi **[REJADA]**. |

---

## 2. Dasturning to'liq arxitekturasi

### 2.1. Qatlamlar

```
        Foydalanuvchi (brauzer)
              │  HTTP (faqat shu kompyuter)
        ┌─────▼──────────────────────────────────────────────┐
        │  api/        FastAPI: endpointlar + bitta HTML sahifa │
        ├──────────────────────────────────────────────────────┤
        │  screening/  risk/  guardian/   (domen mantiqi)        │
        │  (ecg/ angio/ adapters/)                       │
        ├──────────────────────────────────────────────────────┤
        │  core/   Evidence · Episode · Handoff · Concordance    │
        │          registry (litsenziya) · store (SQLite) · audit│
        ├──────────────────────────────────────────────────────┤
        │  ONNX Runtime (CPU)  ←  weights/<model>/*.onnx          │
        └──────────────────────────────────────────────────────┘
        research/  — o'qitish, baholash, eksport skriptlari (server emas)
```

Dastur **modulli monolit**: bitta jarayon, bitta server. Mikroservislar yo'q.

### 2.2. Papkalar va ularning vazifasi

| Papka / fayl | Vazifa | Holat |
|---|---|---|
| `core/evidence.py` | Har qanday natijaning yagona shakli (`Evidence`), xavf darajalari, ogohlantirish matni | MAVJUD |
| `core/episode.py` | Epizod holat mashinasi (8 bosqich) va o'tish qoidalari | MAVJUD |
| `core/handoff.py` | Bosqichlar orasidagi yo'llanma paketi | MAVJUD |
| `core/concordance.py` | Qoida va AI natijasini solishtirish (4 holat) | MAVJUD |
| `core/registry.py` | Model kartasi, dataset litsenziyalari, `research`/`product` rejimi | MAVJUD |
| `core/store.py` | Saqlash (SQLite): epizodlar, audit jurnali, signallar jadvali | MAVJUD |
| `screening/` | Yurak tovushi (PCG) qayta ishlash va modeli, pulsoksimetriya, klinik belgilar, triaj, oddiy tildagi xulosa, ma'lumot yig'ish | MAVJUD |
| `risk/` | EuroSCORE II, Thakar (AKI), AKI ML interfeysi, Heart Team protokoli | MAVJUD (ekransiz) |
| `integration/` | Modullarni bitta tizimga ulash: LVEF (shifokor vs AI EF) va AKI solishtiruvi, **epizod xulosasi (digest)** | MAVJUD (ekransiz) |
| `learning/` | **O'z-o'zini o'rgatish**: model versiyalari, inson tasdig'i va orqaga qaytarish, ma'lumot va model darvozalari, nomzod o'qitish sikli | MAVJUD (ekransiz, buyruq satri + holat API'si) |
| `api/alerts.py` | Signallar: saqlash, ro'yxat, qabul qilish | MAVJUD (ekransiz) |
| `guardian/` | MNO tahlili, vazn/puls/belgi/yara qoidalari, eskalatsiya va Telegram | MAVJUD (ekransiz) |
| `api/main.py`, `risk_routes.py`, `guardian_routes.py` | Endpointlar | MAVJUD |
| `api/static/screening.html` | Yagona sahifa (skrining formasi va natija) | MAVJUD |
| `research/` | O'qitish, baholash, tashqi validatsiya, moslashtirish va ko'p manbali tajribalar, yozuv-blok izini tekshiruvchi nazorat (`control_zch_batch.py`), mahalliy ma'lumot eksporti (tartib/qurilma aralashuvi ogohlantirishi bilan) | MAVJUD |
| `Start.bat` | Ikki marta bosib ishga tushirish (Windows) | MAVJUD |
| `ecg/`, `angio/`, `adapters/echo_ef.py`, `guardian/ocr.py`, `guardian/wound_cv.py`, `api/ai_routes.py`, `api/ai_plain.py` | Qo'shimcha AI modullari (EKG, angiografiya, MNO rasmi, ExoKG EF) | MAVJUD (ekransiz) |

### 2.3. Asosiy abstraksiyalar (hamma narsa shu atrofida)

**Evidence** — platformadagi har qanday natijaning yagona shakli:

| Maydon | Ma'nosi |
|---|---|
| `id`, `created_at` | Noyob raqam va vaqt (UTC) |
| `kind` | Turi, masalan `screening.cchd`, `screening.pcg`, `risk.euroscore2`, `guardian.inr`, `workup.echo_dx` |
| `value`, `unit` | Qiymat va birligi |
| `source` | Kim berdi: `rule` (qoida), `model` (AI), `clinician` (shifokor), `patient` (bemor) |
| `risk` | `normal`, `low`, `moderate`, `high`, `very_high`, `unknown` |
| `uncertainty` | Noaniqlik (AI uchun) |
| `abstained` | AI «javob bermadim» degan bo'lsa `true` |
| `explanation` | Qoida izi yoki abstain sababi (matn ro'yxati) |
| `provenance` | Qayerdan: nomi, versiyasi, ilmiy manba, model bo'lsa dataset litsenziyasi |

**Episode (epizod)** — bitta bemorning butun yo'li: kod (`patient_ref`), populyatsiya (`pediatric`/`adult`), joriy bosqich, Evidence ro'yxati (vaqt chizig'i), Handoff ro'yxati.

**Handoff (yo'llanma)** — bosqichdan bosqichga o'tish: kimdan qaysi bosqichga, kim (`author`), qaysi Evidence asosida, ochiq savollar ro'yxati, izoh.

**Concordance** — bitta savol bo'yicha qoida va AI natijasini solishtiradi. Natija to'rt holatdan biri:

| Holat | Ma'nosi |
|---|---|
| `agree` | Qoida va AI mos |
| `disagree` | Zid. Yakuniy xavf kattasi bo'ladi, muhokama majburiy |
| `ai_abstained` | AI javob bermadi. Qoida natijasi qoladi |
| `rule_only` | AI umuman yo'q yoki ulanmagan |

**Audit jurnali** — har bir amal (kim, nima, qachon, qisqa tafsilot) alohida jadvalda faqat qo'shiladi.

### 2.4. Epizod bosqichlari va ruxsat etilgan o'tishlar [MAVJUD]

| Bosqich | Ma'nosi | Mumkin bo'lgan keyingi bosqichlar |
|---|---|---|
| `screening` | Birlamchi skrining | `workup`, `closed` |
| `workup` | ExoKG, angiografiya | `heart_team`, `closed` |
| `heart_team` | Operatsiya oldi xavf va konsilium | `procedure`, `workup`, `closed` (yopish = dori bilan davolash) |
| `procedure` | Operatsiya / intervensiya | `icu` |
| `icu` | Reanimatsiya | `discharge` |
| `discharge` | Uyga chiqarish | `guardian_30d` |
| `guardian_30d` | 30 kunlik uy nazorati | `closed`, `workup`, `icu` (qayta yotqizish) |
| `closed` | Yopildi | — |

Boshqa o'tishlar server tomonidan rad etiladi (HTTP 409). Yo'llanmada ko'rsatilgan Evidence shu epizodda mavjud bo'lishi shart.

Bosqichga bog'liq cheklovlar: skrining faqat `screening` bosqichida; xavf baholash faqat `heart_team` yoki `icu`; Guardian faqat `guardian_30d`; ExoKG tashxisi faqat `screening` yoki `workup`.

### 2.5. Foydalanuvchi rollari
- **Kirish va rollar [MAVJUD, ixtiyoriy]:** `CARDIOPATH_AUTH=on` bo'lsa, har bir so'rov huquq jadvali bo'yicha tekshiriladi (E16). O'chiq bo'lsa (standart), `actor` (yoki `author`) — oldingidek qo'lda yoziladigan matn.
- Kodlangan rollar: `admin`, `clinician`, `cardiologist`, `surgeon`, `icu`, `patient` (batafsil E16).
- Muallif hujjatiga ko'ra mo'ljallangan **kontseptual rollar**:
  - **Tuman/birlamchi shifokor yoki pediatr**: skrining.
  - **Kardiolog**: ExoKG tahlili, Heart Team.
  - **Kardioxirurg**: Heart Team, operatsiya, Guardian signallarini qabul qiladi.
  - **Reanimatolog**: ICU bosqichi.
  - **Bemor yoki ota-ona**: uyda Guardian orqali ma'lumot yuboradi.
  - **Tadqiqotchi (muallif)**: ma'lumot yig'ish, eksport, modelni moslashtirish.
- Rollar bo'yicha qaysi ekranni kim ko'rishi **[REJADA]**.

### 2.6. API (endpointlar jadvali)

Server manzili: `http://localhost:8010` (faqat shu kompyuter).

| Usul va yo'l | Vazifa | Holat |
|---|---|---|
| `GET /` | Skrining sahifasi (HTML) | MAVJUD |
| `GET /health` | Server holati, rejim (`research`/`product`), ulangan modellar kartalari | MAVJUD |
| `POST /episodes` | Yangi epizod: `patient_ref` (1–64 belgi), `population`, `actor` | MAVJUD |
| `GET /episodes?stage=&q=&limit=&offset=` | Bemorlar ro'yxati, yangisi birinchi. `stage` bo'yicha filtr, `q` — bemor kodidan qidiruv (katta-kichik harf farqsiz), `limit` 1–200 (standart 50). Javob: `total`, `limit`, `offset`, `items[]`, har birida `id`, `patient_ref`, `population`, `stage`, `created_at`, `updated_at`, `n_evidence`, `n_handoffs`, `screening_risk` (oxirgi skrining xavfi yoki `null`). To'liq hujjatsiz | MAVJUD (ekransiz) |
| `GET /episodes/{id}` | Epizodning to'liq yozuvi (bosqich, barcha Evidence, Handoff'lar) | MAVJUD |
| `GET /episodes/{id}/digest` | **Epizod xulosasi**: har bir tur bo'yicha oxirgi natija, AI modullari holati (`not_run`/`ok`/`abstained`), solishtiruvlar, **majburiy muhokama punktlari** (har birida mashina kodi), takliflar, ochiq savollar (takrorsiz), ochiq signallar, keyingi mumkin bo'lgan bosqichlar | MAVJUD (ekransiz) |
| `GET /alerts?status=&level=&episode_id=&limit=&offset=` | Signallar: `status` = `open` (standart) / `acknowledged` / `all`; `level` = `red` / `amber`. Ochiqlari avval qizil, keyin eng yangisi | MAVJUD (ekransiz) |
| `POST /alerts/{id}/ack` | Signalni «qabul qildim» deb belgilash: `actor`, `note`. Ikkinchi marta 409, yo'q signal 404; audit jurnaliga yoziladi | MAVJUD (ekransiz) |
| `GET /episodes/{id}/alerts` | Bitta bemorning signallari | MAVJUD (ekransiz) |
| `GET /learning/status` | O'rganish holati (faqat o'qish): ishlayotgan va joriy model versiyasi, qayta ishga tushirish kerakmi, oxirgi nomzod va uning darvozalari, to'plangan tasdiqlangan bolalar soni, ma'lumot darvozasi, tarix. Tasdiqlash va qaytarish bu yerda ATAYLAB yo'q | MAVJUD (ekransiz) |
| `GET /episodes/{id}/audit` | Audit jurnali | MAVJUD |
| `POST /episodes/{id}/transition` | Bosqichdan bosqichga o'tkazish (Handoff) | MAVJUD (ekransiz) |
| `GET /screening/red-flags?lang=` | 12 klinik belgi ro'yxati (uz/ru/en) | MAVJUD |
| `POST /episodes/{id}/screening` | Skrining tahlili (multipart: raqamlar + WAV fayllar) | MAVJUD |
| `POST /episodes/{id}/echo-diagnosis` | ExoKG tashxisini kiritish | MAVJUD |
| `POST /episodes/{id}/risk` | EuroSCORE II va AKI baholash | MAVJUD (ekransiz) |
| `GET /episodes/{id}/heart-team-protocol` | Heart Team protokoli (oddiy matn, Markdown) | MAVJUD (ekransiz) |
| `POST /episodes/{id}/guardian/inr` | MNO qiymati yoki OCR matni | MAVJUD (ekransiz) |
| `POST /episodes/{id}/guardian/checkin` | Kundalik ko'rsatkichlar | MAVJUD (ekransiz) |
| `GET /models` | Modullar holati va bloklanganlar ro'yxati | MAVJUD (ekransiz) |
| `POST /episodes/{id}/ecg` | EKG tahlili (CSV, 12 tarmoq) | MAVJUD (ekransiz) |
| `POST /episodes/{id}/angio` | Angiografiya kadri tahlili | MAVJUD (ekransiz) |
| `POST /episodes/{id}/guardian/inr-image` | MNO qog'ozi rasmi | MAVJUD (ekransiz) |
| `POST /episodes/{id}/echo-ef` | ExoKG videosidan EF | MAVJUD (ekransiz) |

**Mavjud EMAS (ekran uchun yangi API kerak bo'ladi):** epizodni o'chirish yoki tahrirlash, foydalanuvchi kirishi, bildirishnomalar ro'yxati, hisobot eksporti. Ro'yxatda hali yo'q ma'lumotlar: oxirgi Guardian signali (qizil/sariq), «ochiq savollar bor» belgisi, bemor yoshi, `actor` bo'yicha filtr; ularni ro'yxatga qo'shish uchun kichik kengaytma kerak.

### 2.7. Ma'lumot oqimi (asosiy zanjir)

```
kiritish (raqamlar, belgilar, audio)
   ├─► deterministik qoidalar ──► qoida Evidence'lari (source=rule)
   └─► AI model (agar ulangan) ──► AI Evidence (source=model, yoki abstain)
                    │
                    ▼
            Concordance (solishtirish)
                    │  yakuniy xavf = max(qoida, AI)
                    ▼
        triaj qarori + oddiy tildagi xulosa (uz/ru/en)
                    │
                    ▼
   Epizod vaqt chizig'iga yoziladi + audit jurnaliga yoziladi
```

Matn xulosalari **LLM yordamida emas**, tayyor deterministik shablonlar asosida tuziladi (hech qaysi modul tashqi til modeliga murojaat qilmaydi).

---

## 3. Dastur qanday ishlaydi (ketma-ket jarayonlar)

### 3.1. Ishga tushirish [MAVJUD]
1. Foydalanuvchi `Start.bat` ni ikki marta bosadi.
2. Fayl Python muhitini topadi (loyiha ichidagi `.venv` yoki `%USERPROFILE%\.venvs\cardiopath-ai`). Topmasa, nima qilishni 3 tilda yozadi.
3. `data/` papkasini yaratadi, ma'lumotlar bazasi va yozuvlar saqlanadigan joyni belgilaydi.
4. Serverni `127.0.0.1:8010` da ishga tushiradi va brauzerni o'zi ochadi. Model fayli bo'lmasa, ogohlantiradi va faqat qoidalar bilan ishlaydi.
5. Sahifa brauzer tiliga qarab o'zbek/rus/ingliz tilini tanlaydi. Tanlov va mavzu eslab qolinadi.

### 3.2. Skrining oqimi [MAVJUD]
1. Shifokor **bemor kodini** (ism emas), o'z familiyasini va bolaning **yoshini** (kun/oy/yil) kiritadi. Bu uch maydon majburiy.
2. Ixtiyoriy: **kislorod darajasi**.
   - Yangi tug'ilgan chaqaloq uchun o'ng qo'l va oyoq SpO₂ (ikkalasi birga) va urinish raqami (1 yoki 2).
   - Katta bola uchun faqat «tinch holatdagi» SpO₂.
3. Ixtiyoriy: **klinik belgilar** (12 ta ro'yxatdan belgilash).
4. Ixtiyoriy: **yurak tovushi yozuvlari** (WAV), 4 auskultatsiya nuqtasidan (aorta, o'pka arteriyasi, trikuspidal, mitral). Bitta nuqta ham yetarli. Brauzer yozuvning davomiyligini ko'rsatadi va 5 soniyadan qisqa bo'lsa ogohlantiradi.
5. Ixtiyoriy: stetoskop modeli va **ota-ona yozma roziligi** belgisi (saqlash uchun).
6. «Tahlil qilish». Brauzer tekshiradi: majburiy maydonlar to'ldirilganmi, SpO₂ juftligi to'liqmi, fayllar `.wav`mi, kamida bitta ma'lumot bormi. Xato bo'lsa, oddiy tilda xabar chiqadi.
7. Brauzer yangi epizod yaratadi (`POST /episodes`), so'ng barcha ma'lumotni bitta so'rovda yuboradi (`POST .../screening`).
8. Server qoidalarni hisoblaydi, audio bo'lsa AI modelini ishlatadi, solishtiradi, triaj qarorini chiqaradi va hammasini epizodga yozadi.
9. Natija ekrani ochiladi (3.3).

Xato holatlari: server o'chiq (aloqa xabari); noto'g'ri qiymat (422); noto'g'ri bosqich (409); ichki xato (500). Texnik tafsilot «Batafsil» ichida.

### 3.3. Natija ekrani nimani ko'rsatadi [MAVJUD]
- **Xulosa darajasi** (4 holat, ma'lumotda `red`/`yellow`/`green`/`grey` deb keladi), sarlavha va «nima qilish kerak» matni.
- **Eslatma** (faqat qoida va AI zid bo'lsa): «xulosa yuqoriroq xavf tomonga qilindi, shifokor baholashi shart».
- **Bemor kodi va vaqt.**
- **Topilmalar ro'yxati** (har biri: sarlavha, daraja, bir jumla): pulsoksimetriya (kiritilgan bo'lsa), tinch SpO₂ (kiritilgan bo'lsa), klinik belgilar, yurak tovushi (AI).
- **Bemor yo'li** ko'rsatkichi: 8 bosqich, joriy bosqich «Skrining». Hozircha faqat ma'lumot, bosilmaydi.
- **«Batafsil ma'lumot»** yig'iladigan bo'lim: har bir nuqta uchun shovqin ehtimoli (%), barqarorlik (%), bo'laklar soni.
- **AI modeli haqida satr** (nomi, versiyasi, tadqiqot rejimi) yoki «ulanmagan».
- **ExoKG tashxisini kiritish bloki** (faqat rozilik berilib, yozuv saqlangan bo'lsa).
- **Amallar:** orqaga (formaga qaytish, kiritilganlar saqlanadi), «Yangi bemor», «Chop etish».
- Forma ekranida «oxirgi natijani ko'rish» havolasi paydo bo'ladi.
- Har doim: «yakuniy tashxis emas» ogohlantirishi.

### 3.4. Mahalliy ma'lumot yig'ish oqimi [MAVJUD]
Maqsad: model yangi klinika va stetoskopga moslashishi uchun ExoKG bilan tasdiqlangan yozuvlar yig'ish.
1. Server `CARDIOPATH_RECORDINGS` papkasi bilan ishga tushirilgan bo'lishi kerak (`Start.bat` buni o'zi qiladi).
2. Skriningda «yozma rozilik olingan» belgilansa, WAV fayllar `<papka>/<epizod raqami>/<nuqta>.wav` ko'rinishida saqlanadi. Faqat epizod raqami, ism yo'q. Yoshi va stetoskop modeli ham yoziladi.
3. ExoKG natijasi aniq bo'lgach, shifokor tashxisni kiritadi: `NORMAL, ASD, VSD, PDA, PFO, AVSD, TOF, COA, PS, AS, OTHER` + izoh.
4. `research/export_local.py` tashxisi bor epizodlarni eksport qiladi (bitta bolaning bir nechta yozuvi birga qoladi).
5. `research/adapt_zchsound.py` modelni shu ma'lumotda moslashtiradi. Bu qadamlar **buyruq satridan** ishlaydi, ekrani yo'q [FAQAT API/CLI].

**Hozirgacha haqiqiy mahalliy bemor ma'lumoti yig'ilmagan.** Hamma sinov ochiq datasetlarda va sun'iy yozuvlarda o'tgan.

### 3.4.1. O'z-o'zini o'rgatish sikli (nazorat bilan) [MAVJUD, ekransiz]
**Tamoyil:** dastur o'zi o'rganadi, lekin o'zini o'zi almashtirmaydi. Tibbiyotda nazoratsiz o'z-o'zini o'zgartiradigan model xavfli: ma'lumotdagi yashirin xato (ZCHSound'da shunday bo'lgan) modelni jimgina yomonlashtirishi mumkin.

**Sikl (`python -m learning.cycle`, Task Scheduler bilan rejalashtirsa bo'ladi):**
1. Rozilik bilan saqlangan va ExoKG tashxisi bor bolalar yig'iladi. Noaniq tashxislar (PFO, OTHER) va 29 kundan kichiklar chiqariladi. Oxirgi nomzoddan beri kamida 30 ta yangi bola bo'lmasa, sikl to'xtaydi (`--force` bilan chetlab o'tiladi).
2. **Ma'lumot darvozasi (o'qitishdan OLDIN):** kamida 60 bola, har sinfdan kamida 20 ta, mahalliy testda har sinfdan kamida 8 ta; yig'ish tartibi tashxis bilan ketma-ket emas; har bir stetoskop ikkala sinfni yozgan. O'tmasa, o'qitish umuman boshlanmaydi.
3. **Nomzod o'qitish:** joriy modeldan davom ettirib (fine-tuning), CirCor bilan aralashtirib (unutmaslik uchun); har bir manba ichida sinflar teng vaznlanadi. Bo'linish bola ID xeshi bo'yicha barqaror: bola bir marta testga tushsa, doim shu yerda qoladi (test to'plami sizib kirmaydi).
4. **Model darvozalari (hammasi bajarilishi shart):** mahalliy testda AUROC kamida +0.03 oshgan va juft bootstrap 95% CI quyi chegarasi >0; CirCor testida 0.03 dan ko'p yomonlashmagan; «javob bermadi» ulushi 0.05 dan ko'p oshmagan; sezgirlik 0.05 dan ko'p pasaymagan (ikkala testda); **salbiy nazorat:** mahalliy belgilari aralashtirilgan nomzod joriy modeldan «yaxshi» chiqmasligi (sizib chiqish yo'qligi), haqiqiy nomzod esa aralashtirilganidan kamida 0.02 yaxshiroq bo'lishi.
5. Nomzod va hisobot `models/pcg/versions/<id>/` ga yoziladi. **Nomzod avtomatik joriy bo'lmaydi.**
6. **Tasdiqlash:** `python -m learning.promote --version <id> --approved-by "Ismingiz" --note "sabab"`. Faqat darvozalardan o'tgan nomzod, va ismi kamida 3 belgi bo'lsa. Orqaga qaytarish: `--rollback`. Hamma hodisa `history.jsonl` ga faqat qo'shiladi (kim, qachon, sabab).
7. Dastur qayta ishga tushirilgach, tasdiqlangan joriy versiyani yuklaydi (aniq `CARDIOPATH_WEIGHTS` ko'rsatilgan bo'lsa, o'sha ustun). `GET /learning/status` ishlayotgan va joriy versiya farq qilsa, `restart_needed: true` deydi.

**Ataylab qilingan cheklovlar:**
- Tasdiqlash veb-API va ekranda [MAVJUD, faqat kirish yoqilganda]: `POST /learning/promote`, `POST /learning/rollback` (huquq `learning.approve`: `cardiologist`, `surgeon`) va `/models-ui` sahifasi (3 til; joriy holat, ma'lumot, nomzod darvozalari, tasdiqlash, qaytarish sababi bilan, tarix). Kirishsiz rejimda bu API 403 beradi (aks holda istalgan odam modelni almashtira olardi). Tasdiqlovchi — kirgan foydalanuvchi, hodisa `model.promote`/`model.rollback` sifatida xavfsizlik jurnaliga ham yoziladi. Darvozalardan o'tmagan nomzod tasdiqlanmaydi. Yangi model qayta ishga tushirishdan keyin yuklanadi.
- Qayta o'qitilgan model dataseti «CirCor + mahalliy ma'lumot» deb yoziladi va **mahsulot rejimida bloklanadi**, chunki mahalliy ma'lumotning tijorat huquqi tasdiqlanmagan (rozilik tadqiqot uchun).

**Cheklovlar (halol):**
- Sikl **faqat mexanik sinovdan o'tgan** (sun'iy ma'lumot bilan; soxta dvigatel testlari + haqiqiy o'qitish/eksport/yuklash). Haqiqiy mahalliy bemor ma'lumoti hali yo'q, shuning uchun klinik foyda isbotlanmagan.
- **Mexanik sinovda darvoza haqiqatan ishladi:** sun'iy klinika (150 bola) bilan haqiqiy sikl o'tkazildi; nomzod mahalliy AUROC'ni +0.114 oshirgan va CirCor'da 0.958 → 0.955 bo'lgan, lekin «javob bermadi» ulushi CirCor'da 3.8% → 20.5%, mahalliyda 9.5% → 23.8% ga sakragani uchun TO'XTATILDI. Sabab oynalar kelishuvi emas (u ikkala modelda 4.3%); nomzodning chegaralari ikki domen birgalikdagi validatsiyada tanlangani uchun «noaniq zona» paydo bo'lgan (0.078–0.234; joriy modelda zona yo'q). Ya'ni ikki xil ma'lumotni aralashtirish noaniqlikni kengaytiradi. Tasdiqlash oqimi ham (darvozasi sinov uchun bo'shatilgan nomzod bilan) tekshirildi: tasdiqlovchisiz rad etildi; ismli tasdiq qabul qilindi; ilova yangi versiyani yukladi; qaytarish bazaviy modelni tikladi.
- Darvozalar yig'ish **tartibi va qurilmasi**dagi aralashuvni ushlaydi. Tartib aralash bo'lib, lekin audioda boshqa yashirin iz bo'lsa, ularni ko'rmaydi. Salbiy nazorat esa sizib chiqishni topadi, audio izini emas.
- Kichik ma'lumotda ko'p darvozalar ataylab o'tmaydi (masalan, mahalliy testda sinf boshiga 8 bola); bu to'g'ri xatti-harakat.
- «Soya rejimi» (nomzod joriy model bilan yonma-yon, natijasi foydalanuvchiga ko'rsatilmay ishlashi) hali yo'q [REJADA].

### 3.5. Epizodni keyingi bosqichga o'tkazish [FAQAT API]
`POST /episodes/{id}/transition`: `from_stage`, `to_stage`, `author`, `evidence_ids`, `open_questions`, `note`. Yo'llanma epizodga yoziladi, bosqich o'zgaradi, audit jurnaliga tushadi.

### 3.6. Operatsiya oldi xavf baholash (Heart Team) [FAQAT API]
1. Epizod `heart_team` (yoki `icu`) bosqichida bo'lishi kerak.
2. `POST /episodes/{id}/risk` ikkita blok qabul qiladi: EuroSCORE II kiritishlari va AKI (buyrak) kiritishlari (5.7-bo'limda to'liq ro'yxat). **Bitta bemor — bitta LVEF:** u AKI blokida majburiy; EuroSCORE blokida ham berilsa va farq qilsa, so'rov rad etiladi (422), berilmasa AKI blokidagi qiymat olinadi. Shifokor LVEF'i alohida natija sifatida saqlanadi va ExoKG videosidan AI hisoblagan EF bilan solishtiriladi.
3. Server EuroSCORE II (o'lim %) va Thakar balli (qoida) hisoblaydi. AKI ML modeli ulangan bo'lsa, uning ehtimolini ham beradi. Hozir ML modeli yo'q.
4. Qoida va ML solishtiriladi (qo'shni xavf toifasi farqi «mos» hisoblanadi, chunki ular turli natijani bashorat qiladi). **Kiritilmagan maydonlar jim qolmaydi:** NYHA, shoshilinchlik, aralashuv og'irligi va o'pka bosimi berilmasa, EuroSCORE II eng past xavfli qiymatni oladi; endi javobda `assumed_defaults` ro'yxati qaytadi va protokolda muhokama punkti bo'ladi.
5. `GET /episodes/{id}/heart-team-protocol` protokolni matn (Markdown) shaklida beradi.

### 3.7. 30 kunlik Guardian [FAQAT API]
1. Epizod `guardian_30d` bosqichida bo'lishi kerak. Operatsiyadan keyingi kun shu bosqichga o'tkazilgan vaqtdan hisoblanadi.
2. Bemor yoki ota-ona kundalik ko'rsatkich yuboradi (`checkin`) va/yoki MNO qiymati yoki laboratoriya qog'ozi matni/rasmi (`inr`).
3. Server qoidalar bo'yicha baholaydi (5.8) va **eskalatsiya darajasi**ni beradi: yashil, sariq yoki qizil.
4. Sariq yoki qizilda operatsiya qilgan jarrohga xabar yuboriladi (hozir: jurnalga yoziladi; Telegram bot token va chat berilsa, Telegram'ga).
5. Javobda bemorga ko'rsatiladigan xabar qaytadi.

### 3.8. To'liq yo'l (maqsad) — qaysi qismi ishlaydi

| Qadam | Holat |
|---|---|
| Skrining → natija | MAVJUD, ekrani bor |
| ExoKG tashxisi kiritish | MAVJUD |
| Tahlil uchun qo'shimcha fayllar (EKG, angiografiya, ExoKG video) | FAQAT API (ekrani yo'q) |
| Bosqichdan bosqichga o'tkazish | FAQAT API |
| Heart Team xavf va protokol | FAQAT API |
| Operatsiya, reanimatsiya (ma'lumot kiritish) | Bosqichlar bor, o'zining kiritish ekrani va maxsus mantiqi yo'q |
| Uyga chiqarish → 30 kunlik nazorat | FAQAT API, bemor ilovasi yo'q |

---

## 4. AI tizimi

### 4.1. Umumiy tamoyillar
- **Abstain-first.** AI ishonchsiz bo'lsa, javob bermaydi: yozuv sifatsiz, natija noaniq yoki bola modelning ishonchli yoshidan tashqarida.
- **AI deterministik qoidadan keyin turadi.** Qoidalar mustaqil ishlaydi; AI ulanmagan bo'lsa ham dastur to'liq ishlaydi (`rule_only`).
- **Hamma model ONNX formatida**, CPU'da ishlaydi (GPU faqat o'qitish uchun).
- **Model kartasi:** nomi, versiyasi, vazifasi, dataseti, dataset litsenziyasi, chegaralari, metrikalari.
- **Litsenziya nazorati:** `CARDIOPATH_MODE=product` bo'lsa, faqat tijoratga ruxsat etilgan ma'lumotda o'qitilgan model yuklanadi. Standart rejim `research`.

### 4.2. Yurak tovushi modeli (PCG) [MAVJUD] — asosiy ishlaydigan AI
**Vazifa:** bolada yurak **shovqini** (murmur) bor-yo'qligini aniqlash. U tug'ma nuqson turini aniqlamaydi. Shovqinlarning bir qismi zararsiz bo'lishi mumkin.

**Kirish:** WAV fayl(lar), har biri auskultatsiya nuqtasi nomi bilan (`AV`, `PV`, `TV`, `MV`; kodda `Phc` ham qabul qilinadi) va bolaning yoshi.

**Ishlov berish zanjiri:**
1. Sifat tekshiruvi. Yozuv kamida 5 soniya bo'lishi, signal kesilmagan (clipping 1% dan kam) va bo'sh bo'lmasligi kerak. Aks holda yozuv ishlatilmaydi.
2. 2 kHz ga qayta diskretlash, 25–400 Hz filtr, standartlashtirish.
3. 4 soniyalik oynalarga bo'lish (2 soniya qadam bilan).
4. Har bir oynadan log-mel spektrogramma (64 chastota bo'lagi).
5. Kichik konvolyutsion tarmoq (ONNX) har bir oyna uchun «shovqin ehtimoli» beradi. Tarmoq yana bir «kardiolog natijasi normal/anormal» chiqishini ham beradi, lekin qarorda ishlatilmaydi, faqat tafsilotda ko'rsatiladi.
6. Yig'ish: bitta yozuv = oynalar o'rtachasi; **bemor = nuqtalar ichidagi eng yuqori ehtimollik** (shovqin bitta nuqtada eshitilsa ham bor deb hisoblanadi).

**Abstain shartlari (AI «javob bermadi»):**
- Bola **29 kundan kichik** (model chaqaloqlarda ishlamagani tashqi sinovda aniqlangan).
- Sifatli yozuv yo'q.
- Oynalar bir-biriga mos kelmaydi (kelishuv 60% dan kam).
- Ehtimollik noaniq zonada (hozirgi o'qitilgan modelda zona yo'q: past va yuqori chegara bir xil, 0.3187).

**Chiqish:** ikki natijadan biri, `Evidence` sifatida: «shovqin ehtimoli yuqori» (xavf `moderate`) yoki «shovqin aniqlanmadi» (`low`). **PCG modeli hech qachon `high` xavf bermaydi.** Yana: har bir nuqta uchun ehtimollik, barqarorlik va bo'laklar soni; ishlatilmagan yozuvlar ro'yxati va sabablari.

### 4.3. PCG modelining baholangan sifati (halol raqamlar)

| Sinov | Natija |
|---|---|
| **Ichki test:** CirCor (Braziliya), 132 bola, model ko'rmagan | AUROC 0.958 (95% CI 0.909–0.990); sezgirlik 0.913 (0.778–1.000); spetsifiklik 0.923 (0.870–0.971); NPV 0.980; PPV 0.724; abstain 3.8%. Shovqinli 23 bolaning 21 tasi topildi, sog' 104 tadan 96 tasi to'g'ri. Test to'plami kichik, ishonch oralig'i keng. |
| **Tashqi sinov:** ZCHSound (Xitoy, 941 toza yozuv, qayta o'qitishsiz; yosh chegarasi qo'yilishidan oldingi xom natija) | AUROC **0.676** (0.639–0.715); PFO'siz 0.737. VSD ning 85% topildi, ASD ning 47%; sog' bolalarning 31% ga noto'g'ri «shovqin bor». |
| **Tashqi sinov, chaqaloqlar (≤28 kun)** | AUROC 0.568. Shu sabab 29 kunlik yosh chegarasi qo'yildi. |
| **Moslashtirish tajribasi** (ZCHSound'ni «yangi klinika» deb olib, 315 bolalik testda) — **BEKOR QILINGAN** | Moslashtirishsiz AUROC 0.748; 50 bola bilan 0.968; 200 bilan 0.976. Bu raqamlarga ishonib bo'lmaydi: ZCHSound yozuvlari tashxis bo'yicha ketma-ket yig'ilgan (pastga qarang). |
| **Yashirin omil tekshiruvi (yosh)** | ZCHSound'da nuqsonli bolalar sog'lardan yoshroq: faqat yoshning o'zi AUROC 0.75 beradi. «Yosh guruhlari ichida ham yuqori, demak tovushni o'rganadi» degan avvalgi xulosa **bekor qilindi** (pastdagi topilma sababli). |
| **Yozuv-blok izi (topilma)** | ZCHSound fayllari tashxis bo'yicha ketma-ket: normal 0001–0533, ASD 0534–0652, PDA 0653–0684, PFO 0685–0754, VSD 0755–0941; fayl raqami bilan tashxis AUROC 1.0. Salbiy nazorat: faqat sog' bolalar ichida model «erta vs kech yozilgan»ni AUROC ≈0.67 bilan ajratdi (yosh bilan 0.55): yozuvlarda sharoit izi bor. |
| **Ko'p manbali model (CirCor + ZCHSound)** — **RAD ETILDI** | Oldindan belgilangan mezon bo'yicha «qabul» bo'lgan edi (ZCHSound testida AUROC 0.97), lekin yuqoridagi topilma mezonni bekor qildi. Qo'shimcha zarar: CirCor testida AUROC 0.960 → 0.937 va abstain 10% → 21%. Mahsulot modeli CirCor'da o'qitilgani bo'lib qoladi. Hisobot: `weights/pcg_multisite/report.md`. |
| **CirCor yashirin-omil tekshiruvi** | Metama'lumot (kampaniya, bemor raqami, yosh, bo'y, vazn) murmur bilan atigi 0.51–0.62 AUROC bog'langan; takror audio yo'q. Lekin audiodan kampaniyani ajratish mumkin (murmur yo'q bolalar ichida AUROC 0.83): yozuvlarda kampaniya izi bor. Hal qiluvchi tekshiruv — bir kampaniyada o'qitib, ko'rilmagan ikkinchisida sinash: CC2014→CC2015 AUROC 0.903 (0.858–0.943, n=445), CC2015→CC2014 0.907 (0.847–0.952, n=301). Demak CirCor natijasi kampaniya izidan emas, tovushdan. Cheklov: ikkala kampaniya bitta skrining dasturidan (mustaqil klinikalar emas). 70 bola ikkala kampaniyada ikki ID bilan, ularning 21% da murmur belgisi mos kelmaydi (belgi shovqini). Hisobot: `docs/experiments/circor_batch_check.md`. |

**Cheklovlar:** model faqat Braziliya skrining kampaniyasi yozuvlarida o'qitilgan; boshqa mamlakat va stetoskopda sifati sezilarli pasayadi (qisman yozuv sharoiti farqidan bo'lishi mumkin); **mahalliy klinik validatsiya o'tkazilmagan**; mahalliy moslashtirish uchun kerakli bola soni **noma'lum**.

### 4.4. Qoidalar treki (AI emas, deterministik) [MAVJUD]
Qoidalar AI'dan mustaqil, va Concordance'da «qoida tomoni» bo'ladi. Batafsil — 5-bo'lim.

### 4.5. Concordance va triaj [MAVJUD]
- Bir nechta qoida natijasi bitta «qoida treki»ga birlashtiriladi: **eng yuqori xavf** olinadi.
- Qoida va AI taqqoslanadi (4 holat, 2.3-bo'lim). Yakuniy xavf = ikkalasidan kattasi.
- **Istisno:** yangi tug'ilgan chaqaloqda pulsoksimetriya «FAIL» bo'lsa, yakuniy xavf avtomatik `very_high`.
- Pulsoksimetriya «qayta o'lchash» (REPEAT) bo'lsa, oddiy yo'llanma o'rniga avval 1 soatdan keyin qayta o'lchash tavsiya etiladi.

### 4.6. Boshqa hisoblash modullari

**EuroSCORE II** [FAQAT API]: Nashef 2012 formulasi. Rasmiy kalkulyatordagi namunaviy bemor (89.32%) va minimal holat (0.50%) bilan testda tekshirilgan. Kattalar 18–95 yosh; undan tashqarida abstain. Kreatinin klirensi Kokroft-Golt formulasi bilan, kreatinin mkmol/L da.

**Thakar balli (Cleveland Clinic)** [FAQAT API]: dializ talab qiladigan o'tkir buyrak yetishmovchiligi uchun 0–17 ball.

**AKI ML modeli** [REJADA]: interfeys tayyor (ONNX, noaniq zona, litsenziya tekshiruvi), lekin model yo'q: o'qitish uchun MIMIC-IV (PhysioNet credentialed) kerak. Muallifda bu ruxsat bor-yo'qligi menga ma'lum emas [NOMA'LUM]; kod hozircha bu ma'lumotsiz ishlaydi, model qurilmagan.

**EKG (PTB-XL)** [MAVJUD, ekransiz]: 12 tarmoqli 10 soniyalik EKG, 1D-CNN. Bo'lmachalar fibrillyatsiyasi (AFIB) va yana 5 toifa (NORM, MI, STTC, CD, HYP). Faqat kattalar (18+), bolalarda abstain. Test (PTB-XL 10-bo'lak, 2 060 yozuv): AFIB uchun AUROC 0.981 (0.963–0.992), sezgirlik 0.941, spetsifiklik 0.971. Boshqa toifalar bo'yicha batafsil metrikani men tekshirmadim. Guardian bosqichida AFIB topilsa, eskalatsiya ishlaydi.

**Angiografiya stenoz nomzodlari (ARCADE, U-Net)** [MAVJUD, ekransiz]: **SYNTAX kalkulyatori emas**. Faqat kadrdagi shubhali stenoz nomzodlarini ko'rsatadi; «nomzod topilmadi» «stenoz yo'q» degani emas (shu sabab bunday javobda xavf `unknown` bo'ladi). 60 epoch o'qitilgan. Test (300 kadr, kadr darajasida bootstrap 95% CI): piksel Dice 0.538 (0.513–0.561), IoU 0.396 (0.374–0.416); lezion sezgirligi 0.892 (0.859–0.925), ya'ni 381 haqiqiy lezionning 340 tasi topildi; lezion aniqligi 0.497 (0.463–0.530), ya'ni topilgan 690 nomzodning taxminan yarmi haqiqiy lezion emas. Bu «nomzod ko'rsatuvchi yordamchi» darajasi, aniq o'lchov emas. Cheklov: dastur kadr haqiqatan angiogramma ekanini tekshirmaydi (tasodifiy shovqin rasmi rad etilmadi, «shubhali joy topilmadi» deb javob berdi).

**ExoKG EF** [MAVJUD, ekransiz]: NeuroSon-AI loyihasidagi ONNX og'irligidan foydalanadi (boshqa papkada; standart yo'l kodda yozilgan, `CARDIOPATH_EF_WEIGHTS` muhit o'zgaruvchisi bilan almashtiriladi). Kattalar, apikal 4 kamera videosi. NeuroSon hisobotidagi MAE 5.83%, R² 0.575; **bu loyihada qayta tekshirilmagan**. Litsenziya: EchoNet-Dynamic faqat tadqiqot uchun, `product` rejimida yuklanmaydi.

**MNO qog'ozi OCR** [MAVJUD, ekransiz]: rasm → matn → `parse_inr_text` → baholash. Dvigatel ixtiyoriy kutubxona (`rapidocr-onnxruntime`). Dvigatel yo'q, ishonch past (<0.80) yoki qiymat noaniq bo'lsa, abstain.

**Bloklangan, o'qitilmagan (faqat interfeys, natija o'ylab topilmaydi):** AI-EKG orqali past EF (MIMIC-IV-ECHO kerak); yara rasmidan infeksiya aniqlash (ochiq sternotomiya dataseti yo'q).

### 4.7. Ma'lumot manbalari va litsenziyalar

| Dataset | Nima uchun | Litsenziya | Mahsulotga |
|---|---|---|---|
| CirCor DigiScope | PCG modeli | ODC-By 1.0 (ochiq) | Ruxsat |
| ZCHSound | Tashqi validatsiya, moslashtirish tajribasi | Ma'lumot repozitoriysi «shartlar uchun maqola va sayt»ga yo'naltiradi. Bir manbada CC BY 4.0 deb ko'rsatilgan, rasmiy saytda tasdiqlanmagan | Aniq emas |
| PTB-XL | EKG modeli | CC-BY 4.0 | Ruxsat |
| ARCADE | Angiografiya | CC-BY 4.0 | Ruxsat |
| EchoNet-Dynamic | ExoKG EF | Stanford AIMI tadqiqot shartnomasi | **Yo'q** |
| MIMIC-IV, MIMIC-IV-ECHO, eICU | AKI, AI-EKG past EF | PhysioNet credentialed | Yo'q. Muallifning kirish ruxsati holati [NOMA'LUM] |

---

## 5. Tibbiy jarayonlar

### 5.1. Bemor ma'lumotlari
**Saqlanadi:** bemor kodi (psevdonim), populyatsiya, yosh (kunlarda, faqat yozuv bilan birga), kiritilgan ko'rsatkichlar, natijalar, kim kiritgani (`actor` matni), vaqt. Rozilik bilan WAV yozuvlari, stetoskop modeli.
**Saqlanmaydi:** ism-familiya, tug'ilgan sana, manzil, telefon, hujjat raqami. Sahifa shuni ataylab so'ramaydi.
**Telegram xabarida** faqat bemor kodi va operatsiyadan keyingi kun bo'ladi.
**Saqlash joyi:** mahalliy SQLite fayl (`data/cardiopath.db`). Shifrlash va zaxira nusxa **[NOMA'LUM — amalga oshirilmagan]**.

### 5.2. Pulsoksimetriya (yangi tug'ilgan) — AAP 2020 algoritmi [MAVJUD]
O'ng qo'l (preduktal) va oyoq (postduktal) SpO₂.
- **PASS:** kamida bittasi ≥95% va ikkalasi orasidagi farq ≤3% → xavf `low`.
- **FAIL:** istalgan nuqtada <90%, yoki 2-urinishda ham PASS bo'lmasa → xavf `high`, triajda `very_high`.
- **REPEAT:** qolgan holatlar (masalan 90–94% yoki farq >3%) → xavf `moderate`; 1 soatdan keyin qayta o'lchash.
- Tug'ilganiga 24 soat o'tmagan bo'lsa, ogohlantirish (noto'g'ri ijobiy ko'proq). Qiymat 50–100% dan tashqari bo'lsa, abstain.

### 5.3. Tinch holatdagi SpO₂ (katta bolalar) [MAVJUD]
<90% — `high`; 90–94% — `moderate`; ≥95% — `low`. Bu rasmiy yo'riqnoma emas, konservativ evristika (kodda shunday belgilangan; mahalliy protokol bilan tasdiqlash kerak).

### 5.4. Klinik belgilar (12 ta) [MAVJUD]
**Jiddiy (9):** markaziy sianoz; emizish yoki ovqatlanishda terlash va tez charchash; vazn olmaslik; tinch holatda taxipnoe; gepatomegaliya; son arteriyasida puls sust yoki yo'q; zo'riqishda hushdan ketish; zo'riqishda ko'krak og'rig'i; oilada 50 yoshgacha to'satdan o'lim.
**Kichik (3):** qaytalanuvchi pnevmoniya; jismoniy yuklamaga chidamsizlik; sindromal belgilar.
**Qoida:** kamida bitta jiddiy belgi → `high`; ikki yoki undan ko'p kichik → `moderate`; bitta kichik → `low`; hech biri → `normal`.

### 5.5. Auskultatsiya [MAVJUD]
Dasturda 4 nuqta bor (sxematik joylashuv ko'rsatiladi):
- **AV (aorta):** to'sh suyagining o'ng chetida, 2-qovurg'a oralig'i.
- **PV (o'pka arteriyasi):** to'sh suyagining chap chetida, 2-qovurg'a oralig'i.
- **TV (trikuspidal):** to'sh suyagining chap chetida, 4-qovurg'a oralig'i.
- **MV (mitral, cho'qqi):** chap o'rta o'mrov chizig'i, 5-qovurg'a oralig'i.
Yozuv talabi: WAV, har bir nuqtada kamida 5 soniya (tavsiya 15–20), bola tinch turganda. Hech bo'lmaganda bitta nuqta kerak.

### 5.6. Triaj qarori (yakuniy xavf → harakat) [MAVJUD]
| Yakuniy xavf | Tavsiya (qisqacha) |
|---|---|
| `very_high` | Bugunoq neonatolog yoki kardiolog; ExoKG gacha uyga javob bermang |
| `high` | Kardiolog ko'rigi va ExoKG, imkon qadar tezroq |
| `moderate` | Rejali ExoKG (yoki avval pulsoksimetriyani qayta o'lchash) |
| `low` / `normal` | Qo'shimcha tekshiruv shart emas; belgilar paydo bo'lsa, qayta tekshirish |
| `unknown` | Ma'lumot yetarli emas |

### 5.7. Operatsiya oldi xavf [FAQAT API]
**EuroSCORE II kiritishlari:** yosh, jins, vazn, kreatinin (mkmol/L), dializda ekanligi, ekstrakardial arteriopatiya, yomon harakatchanlik, oldingi yurak operatsiyasi, surunkali o'pka kasalligi, faol endokardit, kritik holat, insulin talab qiluvchi diabet, NYHA (1–4), CCS4 stenokardiya, LVEF %, yaqinda infarkt (≤90 kun), o'pka arteriyasi sistolik bosimi, shoshilinchlik (rejali / shoshilinch / favqulodda / qutqaruv), aralashuv og'irligi, torakal aorta. Chiqish: o'lim %, xavf toifasi (<2% past, 2–5% o'rta, 5–10% yuqori, ≥10% juda yuqori; bu platforma konvensiyasi), hisoblash izi.
**Thakar balli kiritishlari:** jins, yurak yetishmovchiligi, LVEF, IABP, COPD, insulin talab qiluvchi diabet, oldingi operatsiya, shoshilinchlik, operatsiya turi, kreatinin. Toifalar: 0–2 past, 3–5 o'rta, 6–8 yuqori, ≥9 juda yuqori.
**Heart Team protokoli (matn):** sarlavha va bemor kodi; xavf jadvali (EuroSCORE II, Thakar, ML, har birining xavf toifasi va manbasi); AKI concordance satri; **«AI yordamchi topilmalari»** jadvali (EKG: bo'lmachalar fibrillyatsiyasi, angiografiya: stenoz nomzodlari, ExoKG videosidan EF; bajarilmagan yoki AI javob bermagan bo'lsa, shu aytiladi); **LVEF solishtiruvi** (shifokor vs AI); **«majburiy muhokama punktlari»** (zidlik, AI abstain, EuroSCORE hisoblanmagani, kiritilmay qolgan maydonlar, EKGda yuqori AFIB ehtimoli, angiografiyada nomzodlar);  oldingi bosqichlardan ochiq savollar; qaror variantlari (jarrohlik / intervensiya / dori / qo'shimcha tekshiruv); kardiolog, kardioxirurg va anesteziolog imzo joylari; ogohlantirish. Hozir faqat o'zbek tilida.
**Mavjud emas:** RACHS-1 (bolalar) va STS (kattalar) [REJADA]; STS koeffitsiyentlari to'liq ochiq emas, tashqi qiymat sifatida qo'lda kiritish ko'zda tutilgan.

### 5.8. 30 kunlik monitoring [FAQAT API]
**MNO (INR) maqsadlari** (ACC/AHA 2020): mexanik aortal klapan 2.0–3.0 (maqsad 2.5); mexanik aortal klapan va qo'shimcha xavf omillari 2.5–3.5 (3.0); mexanik mitral 2.5–3.5 (3.0); bioprotez 2.0–3.0; bo'lmachalar fibrillyatsiyasi 2.0–3.0.
Baho: ≥5.0 — `high` (≥8 — `very_high`); mexanik klapanda maqsad pastidan 0.5 dan ko'proq past — `high` (tromboz xavfi); oraliqda — `low`; qolgani — `moderate`. Qiymat 0.8–12 dan tashqarida bo'lsa (OCR xatosi ehtimoli), abstain. Qiymat topilmasa, abstain.
**Vazn trendi:** 3 kun ichida ≥2 kg ortish — `high`; 1 kunda ≥1 kg — `moderate`. Trend uchun kamida 2 o'lchov kerak.
**Puls, SpO₂, harorat:** puls >120 yoki <45 — `high`, >100 — `moderate`; SpO₂ <90 — `high`, 90–93 — `moderate`; harorat ≥38.0°C — `moderate`.
**Yurak yetishmovchiligi belgilari:** tinch holatda hansirash, yotganda hansirash, hushdan ketish, chokdan tashqari ko'krak og'rig'i — `high`; yurak urishi tartibsizligi, oyoqda yangi shish, siydik kamayishi — `moderate`.
**Sternotomiya yarasi (so'rovnoma):** yiringli ajralma, to'sh suyagi qimirlashi, chok ochilishi — `high`; qizarish kengayishi, tiniq/qonli ajralma, og'riq kuchayishi — `moderate`; isitma bilan birga kichik belgi — `high`. Rasm (`photo_ref`) saqlanadi va jarrohga yuboriladi, **rasmni AI tahlil qilmaydi**.
**Eskalatsiya:** eng yuqori xavf `high` yoki undan yuqori — **qizil**; `moderate` yoki o'qib bo'lmagan ma'lumot (abstain) — **sariq**; aks holda yashil. Sariq va qizilda jarrohga xabar ketadi (bemor kodi, operatsiyadan keyingi kun, sabablar ro'yxati). Bemorga xabar: yashil — «Rahmat, qabul qilindi»; sariq — «shifokorga yuborildi, bugun bog'lanishadi»; qizil — «shifokor darhol xabardor qilindi; ahvolingiz og'ir bo'lsa, kutmasdan 103 ga qo'ng'iroq qiling». Bu xabarlar hozir faqat o'zbek tilida.

### 5.9. ExoKG tashxisi [MAVJUD]
Shifokor tashxis kodini va izohni kiritadi. Bu «oltin standart» yorlig'i sifatida saqlanadi va modelni moslashtirishda ishlatiladi. Dastur ExoKG tasvirini o'zi tahlil qilmaydi (ExoKG videosidan EF adapteri bor, 4.6-bo'lim).

### 5.10. Kuzatuv va izlanuvchanlik
Har bir amal audit jurnaliga yoziladi. Har bir natijada qaysi qoida/model, qaysi versiya, qaysi dataset litsenziyasi ishlatilgani (`provenance`) saqlanadi.

---

## 6. Barcha ekranlar

Quyidagi ro'yxat **mahsulot uchun zarur bo'lgan ekranlar**ning to'liq majmuasi. Har birining holati ko'rsatilgan: ekrani bor, faqat serveri bor yoki umuman yo'q. Ekranlarning vizual ko'rinishi bu hujjatda belgilanmaydi.

| № | Ekran | Holat |
|---|---|---|
| E1 | Skrining formasi | MAVJUD |
| E2 | Natija ekrani | MAVJUD |
| E3 | ExoKG tashxisini kiritish (E2 ichidagi blok) | MAVJUD |
| E4 | Umumiy funksiyalar: til, mavzu, chop etish | MAVJUD |
| E5 | Bemorlar (epizodlar) ro'yxati va qidiruv | FAQAT API |
| E6 | Epizod tafsiloti va vaqt chizig'i | FAQAT API |
| E7 | Bosqichdan bosqichga o'tkazish (Handoff) | FAQAT API |
| E8 | Operatsiya oldi xavf kiritish | FAQAT API |
| E9 | Heart Team protokoli | FAQAT API (matn) |
| E10 | Qo'shimcha tekshiruv fayllarini yuklash (EKG, angiografiya, ExoKG video) | FAQAT API |
| E11 | Bemor ilovasi: kundalik check-in | FAQAT API |
| E12 | Bemor ilovasi: MNO qog'ozi | FAQAT API; rasm varianti ham FAQAT API |
| E13 | Jarroh va navbatchi: signallar paneli | FAQAT API |
| E14 | Audit jurnali | FAQAT API |
| E15 | Tizim va modellar holati | FAQAT API (`/health`, `/models`) |
| E16 | Kirish va rollar | MAVJUD (ixtiyoriy, standart o'chiq) |
| E17 | Ma'lumot yig'ish va eksport boshqaruvi | FAQAT buyruq satri |
| E18 | Validatsiya va tadqiqot hisobotlari | Faqat fayllar (Markdown/JSON) |
| E19 | O'rganish holati va nomzod modelni tasdiqlash | FAQAT API (holat); tasdiqlash faqat buyruq satrida |

### E1. Skrining formasi [MAVJUD]
- **Vazifa:** bitta bolaning birlamchi skrining ma'lumotini kiritish.
- **Ma'lumotlar (maydonlar):**
  - Bemor kodi (majburiy, 1–64 belgi, ism emas), shifokor (majburiy), yosh (majburiy; birligi kun/oy/yil).
  - O'ng qo'l SpO₂, oyoq SpO₂, urinish (1 yoki 2), tinch holatdagi SpO₂. Hammasi ixtiyoriy; qo'l va oyoq faqat juft kiritiladi.
  - 12 klinik belgi (9 jiddiy, 3 kichik).
  - 4 nuqta uchun WAV fayl tanlash. Nuqtalarning joylashuvi bola tanasi sxemasida ko'rsatiladi; nuqta tanlanganda fayl tanlash ochiladi. Yuklangan yozuv uchun: fayl nomi, davomiylik, to'lqin ko'rinishi, «tayyor» yoki «juda qisqa» belgisi, olib tashlash.
  - Stetoskop modeli (matn), ota-ona yozma roziligi (belgi).
- **Amallar:** tahlil qilish; tilni almashtirish; mavzuni almashtirish; «oxirgi natijani ko'rish» (natija bor bo'lsa).
- **Kirishdagi cheklovlar:** SpO₂ 50–100; faqat WAV; kamida bitta ma'lumot kerak.
- **Yordam:** «Qanday foydalanaman?» yig'iladigan 3 qadam.
- **API:** `POST /episodes`, `POST /episodes/{id}/screening`, `GET /screening/red-flags`, `GET /health`.

### E2. Natija ekrani [MAVJUD]
3.3-bo'limda to'liq yozilgan: xulosa darajasi, sarlavha, «nima qilish kerak», eslatma (zidlik bo'lsa), bemor kodi/vaqt, topilmalar ro'yxati, bemor yo'li ko'rsatkichi, «Batafsil», model qatori, ExoKG bloki, amallar.
- **Holatlar (mazmun jihatidan):** 4 xulosa darajasi (shoshilinch / ExoKG tavsiya / xavf belgisi yo'q / ma'lumot yetarli emas); AI javob bergan yoki bermagan (sabablari: chaqaloq, sifatsiz yozuv, noaniq natija, model ulanmagan); qoida va AI mos yoki zid; yozuv yuklanmagan.
- **Amallar:** orqaga, yangi bemor, chop etish, ExoKG tashxisini saqlash.

### E3. ExoKG tashxisini kiritish [MAVJUD]
- **Vazifa:** keyinroq aniqlangan ExoKG tashxisini epizodga biriktirish (modelni moslashtirish uchun yorliq).
- **Ma'lumotlar:** tashxis (11 variantdan biri), izoh (ixtiyoriy, 500 belgigacha).
- **Qachon ko'rinadi:** faqat rozilik berilib, yozuv saqlangan bo'lsa.
- **Amal:** saqlash; holat xabari (saqlandi / saqlanmadi).

### E4. Umumiy funksiyalar [MAVJUD]
Til almashtirgich (UZ/RU/EN, butun interfeys, natija matni va klinik belgilar nomlari tarjima qilinadi, natija ekranida qayta so'rovsiz almashadi); yorug'/qorong'i rejim almashtirgichi; chop etish (faqat natija chop etiladi). Til va mavzu tanlovi eslab qolinadi.

### E5. Bemorlar (epizodlar) ro'yxati [FAQAT API]
- **Vazifa:** shifokor o'z bemorlarini topishi va davom ettirishi.
- **Hozir mavjud (`GET /episodes`):** bemor kodi, bosqich, populyatsiya, yaratilgan va oxirgi yangilangan vaqt, Evidence va yo'llanmalar soni, oxirgi skrining xavfi. Bosqich bo'yicha filtr, bemor kodi bo'yicha qidiruv, sahifalash. 5 000 ta bemorda 0.07–0.3 soniya (o'lchangan).
- **Ochiq signal belgisi bor:** har bir qatorda `open_alerts` (soni) va `open_alert_level` (`red` / `amber` / `null`).
- **Hali yo'q (ekran uchun kerak bo'lishi mumkin):** ochiq savollar belgisi, yosh, shifokor bo'yicha filtr. Foydalanuvchi kirishi bo'lmagani uchun «mening bemorlarim» ko'rinishi ham yo'q: ro'yxat hamma epizodni ko'rsatadi.
- **Masshtab:** SQLite va JSON hujjat tufayli bir klinika uchun yetarli; bir necha ming bemordan oshsa, PostgreSQL'ga o'tish kerak.

### E6. Epizod tafsiloti va vaqt chizig'i [FAQAT API]
- **Vazifa:** bemorning butun yo'lini ko'rish.
- **Mavjud ma'lumot:** `GET /episodes/{id}` butun yozuvni beradi: bosqich, vaqt bo'yicha tartiblangan barcha Evidence (tur, qiymat, manba, xavf, abstain, izoh, provenance), barcha Handoff'lar.
- **Tayyor xulosa:** `GET /episodes/{id}/digest` shu yozuvdan ekran uchun tayyorlangan qisqa ko'rinishni beradi (AI holati, zidliklar, muhokama punktlari va ularning kodlari, takliflar, ochiq savollar, ochiq signallar, keyingi bosqichlar). Ekran uni qayta hisoblamasdan ko'rsatishi mumkin. Muhokama punktlarining `reason` matni hozir o'zbekcha; `code` orqali istalgan tilga o'giriladi.

### E7. Bosqichdan bosqichga o'tkazish [FAQAT API]
Joriy bosqichdan ruxsat etilgan keyingi bosqichga o'tish; kim (`author`), qaysi Evidence asosida, ochiq savollar, izoh. Ruxsat etilmagan o'tish rad etiladi va sababi qaytadi.

### E8. Operatsiya oldi xavf kiritish [FAQAT API]
EuroSCORE II va Thakar kiritishlari (5.7). Natija: o'lim %, ball, toifa, hisoblash izi, qoida va ML concordance'i.

### E9. Heart Team protokoli [FAQAT API]
Protokol mazmuni 5.7 da. Hozir faqat matn (Markdown). Konsilium qarori va imzolar qog'ozda to'ldiriladi; ularni dasturda kiritish yo'q.

### E10. Qo'shimcha tekshiruv fayllari [FAQAT API]
EKG (CSV, 12 tarmoq, namuna chastotasi, yosh), angiografiya kadri (rasm), ExoKG video (apikal 4 kamera). Har birida natija «oddiy tilda» (3 til) qaytadi; fayl hajmi cheklovi 25 MB (video 100 MB).

### E11. Bemor ilovasi: kundalik check-in [FAQAT API]
- **Vazifa:** uydagi bemor yoki ota-ona kundalik ma'lumot yuboradi.
- **Maydonlar:** vazn, puls, SpO₂, harorat, belgilar ro'yxati (7 ta), yara belgilari ro'yxati (6 ta), isitma, yara rasmi havolasi.
- **Javob:** daraja (yashil/sariq/qizil), bemorga xabar, sabablar.
- **Mo'ljallangan format:** bemor ilovasi (Telegram Mini App yoki PWA) **[REJADA]**; hozir ekrani yo'q.

### E12. Bemor ilovasi: MNO qog'ozi [FAQAT API]
Laboratoriya qog'ozi matni yoki rasmi, ko'rsatma turi (5 xil). Qiymat o'qilmasa, bemor qo'lda kiritishi yoki rasmni qayta yuborishi kerak.

### E13. Jarroh va navbatchi signallari [FAQAT API]
- **Mavjud:** Guardian eskalatsiyasi sariq yoki qizil bo'lsa (kundalik ko'rsatkich, MNO, uy nazoratidagi EKG), signal saqlanadi (bemor kodi, daraja, manba, sabablar, vaqt). Ro'yxat, filtr, «qabul qildim» belgisi (kim, qachon, izoh) va audit jurnali bor. Telegram xabari o'tib ketsa ham, ochiq signal ro'yxatda qoladi.
- **Yo'q:** signallar paneli (ekran), real vaqtda yangilanish (hozir ro'yxat so'rab olinadi), signalni boshqa shifokorga yo'naltirish, signal «kimga» tegishli ekani (kirish tizimi yo'q, hamma signalni ko'radi), takroriy signallarni birlashtirish.

### E14. Audit jurnali [FAQAT API]
Epizod bo'yicha amallar ro'yxati: kim, nima, qachon, qisqa tafsilot.

### E15. Tizim va modellar holati [FAQAT API]
`/health`: rejim, ishlayotgan PCG model versiyasi va ulangan modellar kartalari. `/models`: modullar, bloklanganlar va sabablari.

### E16. Kirish va rollar [MAVJUD, ixtiyoriy]
- **Yoqish:** `CARDIOPATH_AUTH=on`. Standart `off` (mahalliy ishlash o'zgarmaydi). Yoqilganda faol administrator bo'lmasa, server ishga tushmaydi; birinchi administrator `python -m core.auth_cli create-user --username <nom> --role admin` bilan yaratiladi. Standart parol yo'q.
- **Ekran:** sahifa `/auth/status` ni so'raydi; kirish yoqilgan bo'lsa, 3 tilda (uz/ru/en) kirish oynasi chiqadi. Token faqat `sessionStorage` da (brauzer yopilsa o'chadi). Ish joyidagi ism maydoni haqiqiy foydalanuvchi bilan to'ldiriladi; skrining huquqi bo'lmagan rolga tushuntirish chiqadi.
- **Endpointlar:** `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/change-password`, `GET /auth/status` (ochiq), `GET/POST /users`, `POST /users/{nom}/disable|enable|role|password`, `GET /audit/security`. Ochiq yo'llar faqat: `/`, `/health`, `/auth/status`, `/auth/login`.
- **Rollar va huquqlar:** `admin` (foydalanuvchilar, xavfsizlik jurnali, ko'rish; klinik amal yo'q), `clinician` (epizod, skrining, ExoKG tashxisi, bosqich, fayl yuklash), `cardiologist` (+ xavf baholash, Heart Team protokoli, epizod jurnali), `surgeon` (+ signalni tasdiqlash), `icu` (ko'rish, bosqich, xavf), `patient` (faqat O'Z epizodiga uy-nazorat ma'lumoti).
- **Xavfsizlik qarorlari:** scrypt parol xeshi (kamida 10 belgi); token tasodifiy, bazada faqat SHA-256 xeshi, 12 soat; 5 xato → 5 daqiqa bloklash (mavjud bo'lmagan nom uchun ham, xato matni bir xil); oxirgi faol administratorni o'chirib/roldan mahrum qilib bo'lmaydi; foydalanuvchi o'chirilsa yoki roli o'zgarsa, amal darhol (har so'rovda bazadan o'qiladi); parol almashtirilsa boshqa seanslar bekor; huquq jadvalida YO'Q yo'l taqiqlanadi (test har bir yo'l jadvalda borligini tekshiradi); kirish yoqilganda `/docs`, `/redoc`, `/openapi.json` o'chiriladi.
- **Audit:** `actor`, yo'llanma muallifi (`author`) va signalni tasdiqlovchi (`ack_by`) so'rovda yozilgan matn emas, kirgan foydalanuvchi bo'ladi. Kirish, chiqish, muvaffaqiyatsiz urinish va foydalanuvchilar boshqaruvi `audit_log` da (episode_id = `system`); parol va tokenlar yozilmaydi.
- **Cheklov:** bitta server jarayoni uchun mo'ljallangan (urinishlar hisobi xotirada); HTTPS ni o'zi bermaydi (ochiq tarmoqqa chiqarishdan oldin teskari proksi + TLS kerak); ikki bosqichli tasdiq (2FA) yo'q; foydalanuvchilarni boshqarish ekrani yo'q (API va buyruq satri).

### E17. Ma'lumot yig'ish boshqaruvi [FAQAT buyruq satri]
Eksport va moslashtirish buyruqlari (3.4). Foydalanuvchi ekrani yo'q.

### E18. Hisobotlar [fayllar]
`weights/pcg/eval_report_test.md`, `external_zchsound.md`, `docs/experiments/zchsound_adaptation.md`. Ekranda ko'rsatilmaydi.

### E19. O'rganish holati va nomzod modelni tasdiqlash [FAQAT API; tasdiqlash — buyruq satri]
- **Vazifa:** shifokor/tadqiqotchi dastur o'zi o'qitgan yangi nomzodni ko'radi, darvozalar natijasini tushunadi va tasdiqlash yoki rad etish haqida qaror qiladi.
- **Mavjud ma'lumot (`GET /learning/status`):** ishlayotgan versiya, joriy versiya, qayta ishga tushirish kerakmi; oxirgi nomzod (yaratilgan vaqt, har bir darvoza: nomi, o'tdi/o'tmadi, tushuntirish; mahalliy testdagi AUROC farqi va ishonch oralig'i; tasdiqlash buyrug'i); to'plangan tasdiqlangan bolalar soni, oxirgi nomzoddan beri yangilari va keraklisi; ma'lumot darvozasi natijasi; oxirgi sikl holati; tarix (kim, qachon tasdiqlagan yoki qaytargan).
- **Amallar:** tasdiqlash va qaytarish kirish yoqilganda ekranda ham mumkin; kirishsiz `python -m learning.promote` (kirish tizimi bo'lgach, ekranga chiqarilishi mumkin) [REJADA].
- **Muhim:** darvozadan o'tmagan nomzod tasdiqlanmaydi (server rad etadi); tasdiqlovchining ismi majburiy.

---

## 7. Foydalanuvchi tajribasi

### 7.1. Kimlar foydalanadi (muallif konsepsiyasi)
Asosiy foydalanuvchi: **tuman va viloyatdagi shifokor** (ExoKG imkoniyati cheklangan sharoit); keyin kardiolog, kardioxirurg, reanimatolog; so'ng operatsiyadan keyingi **bemor yoki ota-ona**. Loyihaning o'zi **resurslari cheklangan sharoit** uchun mo'ljallangan.

### 7.2. Qurilmalar va sharoit
- **Mavjud dastur:** Windows kompyuterda ishlaydi (`Start.bat`), brauzer orqali. Sahifa telefon kengligida tekshirilgan (sozlangan brauzerda), **haqiqiy telefonda va planshetda sinalmagan**.
- **Bemor ilovasi:** smartfon uchun mo'ljallangan (Telegram Mini App yoki PWA) [REJADA].
- **Internet:** dastur hozir mahalliy kompyuterda ishlaydi, tashqi internetga muhtoj emas (Telegram eskalatsiyasi bundan mustasno). Real klinikada qanday qurilma, ekran o'lchami va internet sifati borligi **[NOMA'LUM]**.
- **Tillar:** o'zbek, rus, ingliz (skrining ekrani to'liq; Heart Team protokoli, Guardian bemor xabarlari va Telegram xabari hozir faqat o'zbekcha).

### 7.3. Eng muhim ish jarayonlari (ustuvorlik tartibida)
1. **Skrining** (E1 → E2): tez, kamida ma'lumot bilan, natija bir qarashda tushunarli bo'lishi shart. Eng ko'p ishlatiladigan va to'liq amalga oshirilgan jarayon.
2. **Natijani o'qish va qaror**: «nima qilish kerak» aniq bo'lishi; AI «bilmayman» degan holat tushunarli bo'lishi; qoida va AI zid bo'lsa, bu ko'rinishi.
3. **ExoKG tashxisini keyinroq kiritish** va yozuvlarni saqlash: ma'lumot yig'ishning asosi.
4. **Heart Team** konsiliumi uchun xavf va protokol.
5. **Uy nazorati**: bemorning kundalik kiritishi va jarroh signali.

### 7.4. Foydalanuvchi tajribasiga ta'sir qiladigan texnik faktlar
- Tahlil taxminan 1–3 soniya oladi (kuzatuv, aniq o'lchov emas).
- Yozuv kamida 5 soniya, faqat WAV; MP3 qabul qilinmaydi.
- Chaqaloqlarda (<1 oy) yurak tovushi AI ishlamaydi, faqat pulsoksimetriya va klinik belgilar.
- SpO₂ qiymatlari juft bo'lishi kerak (qo'l va oyoq).
- Ma'lumot yo'qolsa tiklash vositasi yo'q (zaxira nusxa yo'q).
- Natija ekranidan formaga qaytilganda kiritilgan qiymatlar saqlanadi; yangi bemor bosilganda forma tozalanadi.

---

## 8. Texnik imkoniyatlar

### 8.1. Texnologik stek

| Qatlam | Texnologiya | Holat |
|---|---|---|
| Frontend | Bitta HTML fayl, toza JavaScript va CSS (kutubxona yoki freymvorksiz). Til lug'ati sahifa ichida | MAVJUD |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic | MAVJUD |
| Ma'lumotlar bazasi | SQLite (Python standart kutubxonasi), epizod = JSON hujjat; alohida audit jadvali | MAVJUD |
| AI inference | ONNX Runtime (CPU), numpy | MAVJUD |
| AI o'qitish | PyTorch 2.11 (CUDA 12.8), mahalliy GPU NVIDIA RTX 5060 Laptop 8 GB | MAVJUD |
| Audio | Standart `wave` moduli + numpy (librosa va boshqalarsiz) | MAVJUD |
| Bildirishnoma | Telegram Bot API (`httpx`), muhit o'zgaruvchilari orqali | Kod bor, haqiqiy bot bilan **sinalmagan** |
| Tashqi OCR | `rapidocr-onnxruntime` (ixtiyoriy) | MAVJUD |
| Tilda xulosa | Deterministik shablonlar, LLM yo'q | MAVJUD |
| Testlar | pytest: 245 | MAVJUD |
| Ishga tushirish | `Start.bat` (Windows) | MAVJUD |
| Frontend freymvork (Next.js), PostgreSQL | Dastlabki rejada bor edi | **REJADA**, qurilmagan |

### 8.2. Sozlash (muhit o'zgaruvchilari)
`CARDIOPATH_DB` (baza fayli), `CARDIOPATH_WEIGHTS` (PCG og'irliklari papkasi), `CARDIOPATH_AKI_WEIGHTS`, `CARDIOPATH_MODE` (`research`/`product`), `CARDIOPATH_RECORDINGS` (rozilik bilan saqlanadigan yozuvlar), `CARDIOPATH_TG_TOKEN` va `CARDIOPATH_TG_CHAT` (Telegram), `CARDIOPATH_PORT` (`Start.bat`, standart 8010). Yana `CARDIOPATH_EF_WEIGHTS` (ExoKG EF og'irligi) va `CARDIOPATH_MODELS` (model versiyalari papkasi, standart `models/pcg`). Yana `CARDIOPATH_AUTH` (`on`/`off`, standart `off`: kirish va rollar).

### 8.3. Ma'lumot saqlash
- Jadvallar: `episodes` (id, JSON hujjat, yangilangan vaqt), `audit_log` (faqat qo'shiladi).
- Og'irlik fayllari (`*.onnx`, `*.pt`) git'ga kirmaydi, mahalliy saqlanadi; model kartalari va hisobotlar git'da.
- Repo: GitHub (shaxsiy private repo).

### 8.4. Mavjud cheklovlar (halol ro'yxat)
**Xavfsizlik va infratuzilma**
- Kirish ixtiyoriy va standart **o'chiq**; HTTPS, 2FA, foydalanuvchilarni boshqarish ekrani yo'q (E16 cheklovlari).
- HTTPS yo'q; server faqat `127.0.0.1` da tinglaydi (bir kompyuter, bir foydalanuvchi).
- Baza shifrlanmagan, zaxira nusxa yo'q.
- Fayl yuklash hajmi: yurak tovushi (skrining) endpointida cheklov yo'q; EKG, angiografiya va MNO rasmida 25 MB, ExoKG videoda 100 MB.
- Ko'p foydalanuvchili ishlash va bir vaqtdagi tahrirlash himoyasi sinalmagan.
- CI sozlanmagan.
- Telegram bot haqiqiy hisob bilan sinalmagan.

**Mahsulot**
- Epizodlarni tahrirlash/o'chirish yo'q; ro'yxat API'si bor (`GET /episodes`), lekin ekrani yo'q.
- Heart Team, Guardian va xavf baholash uchun ekran yo'q.
- Heart Team protokoli, Guardian bemor xabarlari va Telegram xabari faqat o'zbekcha.
- Epizod har doim `pediatric` populyatsiyasi bilan yaratiladi (UI kattalar variantini bermaydi).
- ExoKG EF adapteri boshqa loyiha papkasidagi (NeuroSon-AI) og'irlik fayliga bog'liq; standart yo'l kodda yozilgan, `CARDIOPATH_EF_WEIGHTS` bilan almashtiriladi.

**Ilmiy va klinik**
- Modelning mahalliy klinik validatsiyasi **o'tkazilmagan**; tashqi sinovda sifat pasaygan (AUROC 0.68).
- Haqiqiy mahalliy bemor ma'lumoti yig'ilmagan.
- Etika komissiyasi ruxsati va tibbiy qurilma ro'yxatdan o'tishi (SaMD) bo'yicha holat **[NOMA'LUM]**; dastur tadqiqot rejimi deb belgilangan.
- MIMIC ma'lumotiga kirish bo'lmagani uchun AKI ML va AI-EKG past EF modellari qurilmagan.
- Intraoperatsion video uchun ochiq ma'lumot yo'q; yo'nalish muzlatilgan.
- O'z-o'zini o'rgatish sikli (3.4.1) haqiqiy mahalliy ma'lumotda sinalmagan; yashirin ma'lumot izlarini (yig'ish tartibi/qurilmadan tashqari) ko'ra olmaydi.

---

## 9. Kelajakdagi rivojlanish (reja; bajarilishi kafolat emas)

Quyidagilar muallifning maqsad hujjati va kelishilgan rejadan olingan. Hammasi **[REJADA]**, aks ko'rsatilmagan bo'lsa.

**Yaqin muddat (muallif ustuvorligi)**
1. Mahalliy ma'lumot yig'ish: etika ruxsati, rozilik shakli, raqamli stetoskop, ExoKG bilan tasdiqlangan bola yozuvlari (kerakli soni noma'lum); **sog' va kasal bolalarni aralash tartibda, bir xil qurilma va kunlarda yozish shart**; keyin modelni moslashtirish. (Dasturdagi yig'ish mexanizmi tayyor; eksport tartib/qurilma aralashuvini tekshiradi.)
2. ~~Qo'shimcha AI modullarni birlashtirish~~ **Bajarildi:** `feat/ai-models` 2026-10-30 da `main` bilan birlashtirildi (EKG, angiografiya, MNO OCR, ExoKG EF). Qolgani: ularni ekranga ulash.
3. PhysioNet credentialing (CITI kursi) olish (holati [NOMA'LUM]); shundan keyin: AKI uchun ML modeli (MIMIC-IV, eICU tashqi tekshiruv), operatsiyadan keyingi bo'lmachalar fibrillyatsiyasi (POAF), AI-EKG orqali past EF.

**O'rta muddat**
4. Ekranlar: bemorlar ro'yxati, epizod tafsiloti va bosqichga o'tkazish, Heart Team kiritish va protokol, jarroh/navbatchi signallari paneli.
5. Bemor ilovasi (Telegram Mini App yoki PWA): kundalik check-in, MNO qog'ozini rasmga olish, uchala tilda xabarlar.
6. PostgreSQL ga o'tish (saqlash qatlami shuni ko'zda tutib interfeys orqali yozilgan). «soya rejimi» (nomzod joriy model bilan yonma-yon, natijasi ko'rsatilmay sinaladi), sikl rejalashtirgichi.
7. RACHS-1 (bolalar xavfi); STS ballini qo'lda kiritish; mexanik klapan bemorlari uchun Guardian qoidalarini kengaytirish.
8. ExoKG: regional devor harakati (RWMA), klapan regurgitatsiyasi, pediatrik EF; ExoKG foundation modellarini mahalliy apparatda tashqi validatsiya qilish.
9. Yara rasmi uchun CV modeli (Guardian orqali rozilik bilan yig'ilgan rasm va jarroh yorlig'i bilan).

**Uzoq muddat**
10. Prospektiv klinik tadqiqot (hamkor markazda): Guardian va xavf modulini sinash; EuroSCORE II ni mahalliy kalibrlash.
11. Intraoperatsion torakoskopik video bo'yicha yordam (mahalliy video yig'ilgandan keyin; hozir muzlatilgan).
12. Tibbiy qurilma sifatida ro'yxatdan o'tish (SaMD) va klinik foydalanishga o'tish.
13. Ilmiy nashrlar (muallif rejasi bo'yicha: TYN triaji, AI-EKG past EF, AKI Concordance, prospektiv tadqiqot).

---

## Ilova A. Ma'lumot lug'ati (qiymatlar to'plami)

- **Xavf darajalari:** `normal`, `low`, `moderate`, `high`, `very_high`, `unknown`.
- **Xulosa darajasi (oddiy tildagi natijada):** `red`, `yellow`, `green`, `grey`. Moslik: `very_high`/`high` → `red`; `moderate` → `yellow`; `low`/`normal` → `green`; `unknown` → `grey`.
- **Manba (`source`):** `rule`, `model`, `clinician`, `patient`.
- **Concordance holatlari:** `agree`, `disagree`, `ai_abstained`, `rule_only`.
- **Bosqichlar:** `screening`, `workup`, `heart_team`, `procedure`, `icu`, `discharge`, `guardian_30d`, `closed`.
- **Eskalatsiya:** `green`, `amber`, `red`.
- **Tillar:** `uz`, `ru`, `en`.
- **Populyatsiya:** `pediatric`, `adult`.
- **ExoKG tashxisi:** `NORMAL, ASD, VSD, PDA, PFO, AVSD, TOF, COA, PS, AS, OTHER`.
- **Auskultatsiya nuqtalari:** `AV, PV, TV, MV` (kodda yana `Phc`).
- **MNO ko'rsatmalari:** `mechanical_aortic, mechanical_aortic_risk, mechanical_mitral, bioprosthetic, af`.
- **Klinik belgi kodlari (12):** `cyanosis, feeding_diaphoresis, failure_to_thrive, tachypnea_rest, hepatomegaly, weak_femoral_pulse, exertional_syncope, exertional_chest_pain, family_sudden_death, recurrent_pneumonia, exercise_intolerance, syndromic_features`.
- **YE belgilari (7):** `dyspnea_rest, orthopnea, syncope, chest_pain_non_incisional, palpitations, new_edema, reduced_urine`.
- **Yara belgilari (6):** `purulent_discharge, sternal_instability, dehiscence, spreading_redness, serous_discharge, increasing_pain`.

## Ilova B. Skrining javobining tuzilishi (`POST /episodes/{id}/screening`)

```
episode_id, evidence_ids[]
final_risk                      # very_high | high | moderate | low | normal | unknown
action                          # triaj matni (o'zbekcha)
concordance { status, needs_discussion, final_risk, message,
              rule{Evidence}, ai{Evidence|null} }
summary { Evidence }            # triaj Evidence'i
plain { lang, level, headline, todo, attention|null,
        items[ {title, level, text} ] }
plain_i18n { uz{...}, ru{...}, en{...} }   # xuddi plain, 3 tilda
saved_for_research (true|false)
warning (ixtiyoriy)             # masalan, AI modeli ulanmagan
disclaimer
```

So'rov (multipart): `actor`, `lang`, `age_days` (yoki `age_hours`), `right_hand_spo2`, `foot_spo2`, `attempt`, `resting_spo2`, `red_flags` (vergul bilan), `research_consent`, `device`, `recordings` (bir nechta WAV; fayl nomida nuqta kodi bo'lishi shart).

## Ilova C. Atamalar lug'ati

- **TYN (CHD):** tug'ma yurak nuqsoni. **CCHD:** kritik tug'ma yurak nuqsoni.
- **SpO₂ / pulsoksimetriya:** qonning kislorod bilan to'yinishi, barmoqdagi datchik bilan o'lchanadi.
- **PCG / auskultatsiya:** yurak tovushini stetoskop bilan eshitish va yozish.
- **Shovqin (murmur):** yurak tovushidagi qo'shimcha tovush; ba'zan nuqson belgisi, ba'zan zararsiz.
- **ExoKG (ehokardiografiya):** yurak ultratovush tekshiruvi. **EF:** chap qorincha otilish fraksiyasi.
- **ASD / VSD / PDA / PFO:** bo'lmachalararo to'siq nuqsoni / qorinchalararo to'siq nuqsoni / ochiq arterial oqim / ochiq oval teshik.
- **Heart Team:** kardiolog va kardioxirurg konsiliumi.
- **EuroSCORE II:** yurak operatsiyasida o'lim xavfini baholovchi shkala. **Thakar:** operatsiyadan keyin dializ talab qiluvchi buyrak yetishmovchiligi xavfi.
- **AKI:** o'tkir buyrak zararlanishi. **POAF:** operatsiyadan keyingi bo'lmachalar fibrillyatsiyasi. **AFIB:** bo'lmachalar fibrillyatsiyasi.
- **MNO (INR):** qonning ivish ko'rsatkichi; varfarin davosini nazorat qiladi. Mexanik klapanli bemorlar umr bo'yi qabul qiladi.
- **Sternotomiya:** to'sh suyagini kesib yurak operatsiyasi qilish; chok infeksiyasi xavfli asorat.
- **SYNTAX:** koronar arteriyalar shikastlanishining murakkabligi balli (dastur uni hisoblamaydi).
- **Abstain:** AI «bilmayman» deb javob bermasligi.
- **Psevdonim:** ism o'rniga ishlatiladigan kod.

## Ilova D. Dizayner AI hal qilmasligi va taxmin qilmasligi kerak bo'lgan savollar

Bular menda **ma'lumot yo'q** narsalar. Ularni o'ylab topmang, muallifdan so'rang:
1. Real klinikada ishlatiladigan aniq qurilmalar, ekran o'lchamlari, internet sifati.
2. Foydalanuvchilar soni va bir vaqtda ishlovchilar.
3. Rollar bo'yicha ekranlar va huquqlarning aniq taqsimoti.
4. Bemor ilovasi qaysi platformada bo'ladi (Telegram Mini App yoki PWA) va bemorlarning raqamli savodxonligi.
5. Tibbiy qurilma sifatida ro'yxatdan o'tish va etika komissiyasi holati.
6. Heart Team ekranlarida ishlatiladigan aniq klinik tartib (qaysi bosqichda kim nima kiritadi).
7. Natija ekranida mahalliy yo'riqnomaga mos «nima qilish kerak» matnlari (hozirgilari umumiy, mahalliy protokol bilan tasdiqlanmagan).

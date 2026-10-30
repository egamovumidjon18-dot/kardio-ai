# CardioPath AI

Kardiologiya va kardioxirurgiya uchun yagona AI + CDSS platformasi. Bemorning skriningdan 30 kunlik uy reabilitatsiyasigacha bo'lgan butun yo'li **bitta epizod** sifatida yuritiladi.

> **Muhim:** har bir natija yakuniy tashxis EMAS, shifokor uchun yordamchi. Tadqiqot rejimi (research use only).

## Tez boshlash (shifokor uchun)

**O'zbekcha:** `Start.bat` faylini ikki marta bosing. Brauzer o'zi ochiladi (oyna ochiq turishi kerak). Sahifa yuqorida tilni tanlash tugmalari bor: O'zbekcha, Русский, English. Ma'lumotlarni kiriting va «Tahlil qilish» ni bosing.
**Русский:** дважды щёлкните `Start.bat` — браузер откроется сам (окно программы не закрывайте). Язык переключается кнопками вверху страницы.
**English:** double-click `Start.bat`; the browser opens by itself (keep the console window open). Switch language with the buttons at the top.

Birinchi marta ishga tushirishdan oldin Python muhitini bir marta o'rnating (`Start.bat` o'zi yo'l-yo'riq beradi).

**Natijani qanday o'qish kerak:**
- 🔴 **qizil** — shoshilinch; pastdagi «nima qilish kerak» qatorini bajaring;
- 🟡 **sariq** — ExoKG yoki qayta o'lchash tavsiya etiladi;
- 🟢 **yashil** — xavf belgilari aniqlanmadi;
- ⚪ **kulrang** — ma'lumot yetarli emas yoki AI javob bermadi (sababi va nima qilish kerakligi yoziladi).

AI "bilmayman" desa, bu xato emas: yozuv sifatsiz yoki natija noaniq bo'lgan, shifokor o'zi baholaydi.

## Arxitektura

```
SCREENING → WORKUP → HEART_TEAM → PROCEDURE → ICU → DISCHARGE → GUARDIAN_30D → CLOSED
                         │ har bir bosqich yozadi/o'qiydi
                 Evidence vaqt chizig'i  (core/evidence.py)
                         │
            Concordance: qoida vs AI  (core/concordance.py)
```

| Qism | Fayl | Vazifasi |
|---|---|---|
| Evidence | `core/evidence.py` | Har qanday natijaning yagona shakli: qiymat, manba, xavf, abstain, provenance |
| Episode | `core/episode.py` | Holat mashinasi. O'tish faqat `Handoff` (yo'llanma paketi) orqali |
| Concordance | `core/concordance.py` | `AGREE` / `DISAGREE` / `AI_ABSTAINED` / `RULE_ONLY`. **AI xavfni faqat oshiradi, hech qachon pasaytirmaydi** |
| Registry | `core/registry.py` | Model + dataset litsenziyasi. `CARDIOPATH_MODE=product` da faqat tijoratga ochiq ma'lumotda o'qitilgan modellar ishlaydi |
| Store | `core/store.py` | sqlite3 repository + faqat qo'shiladigan audit log |

## 1-modul: pediatrik TYN skriningi (`screening/`)

- **Qoida treki** (`rules.py`):
  - AAP 2020 CCHD pulsoksimetriya algoritmi
  - tinch holatdagi SpO₂
  - klinik qizil bayroqlar (katta/kichik)
- **AI treki** (`pcg.py`, `features.py`, `model.py`): PCG → 2 kHz, 25–400 Hz → 4 s oynalar → log-mel → CNN (ONNX, CPU). Bemor darajasidagi ball = nuqtalar bo'yicha maksimum.
- **Abstain** quyidagi hollarda:
  - sifatsiz yozuv (qisqa, kesilgan yoki bo'sh)
  - oynalar bir-biri bilan kelishmaydi
  - ehtimollik noaniq zonada
- **Triaj** (`triage.py`): Concordance → yo'nalish. CCHD FAIL har doim eng yuqori darajani beradi.

### Joriy model natijasi (CirCor test, 132 bola, hech qachon ko'rilmagan)

| Metrika | Qiymat (bola darajasida bootstrap 95% CI) |
|---|---|
| AUROC | 0.958 (0.909–0.990) |
| Sezgirlik | 0.913 (0.778–1.000) — 23 ta shovqindan 21 tasi topildi |
| Spetsifiklik | 0.923 (0.870–0.971) |
| NPV | 0.980 |
| Abstain | 3.8% |

To'liq hisobot: [weights/pcg/eval_report_test.md](weights/pcg/eval_report_test.md).

### Tashqi validatsiya: ZCHSound (Xitoy, haqiqiy TYN tashxislari, qayta o'qitishsiz)

| | Toza (941 bola) | Shovqinli, faqat neonatlar (318) |
|---|---|---|
| AUROC, TYN vs normal | 0.676 (0.639–0.715) | 0.568 |
| AUROC, PFO'siz | 0.737 (0.696–0.776) | 0.521 |
| VSD topildi | 85% | 39% |
| ASD topildi | 47% | 21% |
| Sog'ga noto'g'ri "shovqin bor" | 31% | 18% |

**Xulosa:**
- Boshqa mamlakat va boshqa stetoskopda sifat sezilarli pasayadi (domain shift). Bu pasayishning bir qismi yozuv sharoiti farqidan bo'lishi mumkin (ZCHSound'da tashxis bloklari alohida yozilgan), shuning uchun 0.68 aniq «klinik» ko'rsatkich emas.
- Model baland shovqinli nuqsonlarni (VSD, PDA) yaxshi topadi, yumshoq shovqinlilarni (ASD) va shovqinsizlarni (PFO) yomon topadi.
- **Chaqaloqlarda (≤28 kun) ishlamaydi.** Shuning uchun `min_age_days=29`: undan kichiklarda AI javob bermaydi, faqat pulsoksimetriya va klinik qoidalar ishlaydi.
- Klinikada ishlatishdan oldin **mahalliy ma'lumotda qayta kalibrlash yoki fine-tuning** majburiy.

Hisobot: [weights/pcg/external_zchsound.md](weights/pcg/external_zchsound.md). Bu hisobot yosh chegarasi qo'shilishidan oldin olingan xom natijalarni ko'rsatadi.

**Cheklovlar:**
- Model shovqin bor-yo'qligini aniqlaydi, nuqson turini emas. Shovqinlarning bir qismi zararsiz (innocent) bo'ladi.
- Ma'lumot bitta manbadan (Braziliya skrining kampaniyalari). Shuning uchun mahalliy stetoskopda validatsiya majburiy.
- Chaqaloqlar bo'yicha kichik guruh juda kichik (n=18).

Shifokor sahifasi: `http://localhost:8010/` (server ishga tushirilganda).

### Modelni o'z klinikangizga moslashtirish

> **Diqqat (tuzatish, 2026-10-30):** ilgari bu yerda «~50–100 ta mahalliy bola AUROC ni 0.75 dan 0.97 ga ko'taradi» deb yozilgan edi. **Bu xulosa bekor qilindi:** ZCHSound'da yozuvlar tashxis bo'yicha ketma-ket yig'ilgan va yozuvlarda kun/sharoit izi topildi ([docs/experiments/zchsound_adaptation.md](docs/experiments/zchsound_adaptation.md)). Kerakli mahalliy ma'lumot hajmi hozircha **noma'lum**.
>
> Ko'p manbali (CirCor + ZCHSound) model ham sinab ko'rildi va **rad etildi** ([weights/pcg_multisite/report.md](weights/pcg_multisite/report.md)). Mahsulot modeli CirCor'da o'qitilgan model bo'lib qoladi.

1. Serverni `CARDIOPATH_RECORDINGS=<papka>` bilan ishga tushiring.
2. Sahifada "yozma roziligi olingan" belgisini qo'ying va stetoskop modelini yozing. Yozuvlar psevdonim bilan saqlanadi.
3. ExoKG natijasini o'sha sahifada yoki `POST /episodes/{id}/echo-diagnosis` orqali kiriting.
4. Eksport qilib, moslashtiring:
```bash
python -m research.export_local --db cardiopath.db --recordings <papka> --out <eksport>
python -m research.adapt_zchsound --data-dir <eksport> --base <pcg.pt papkasi> --out docs/experiments/local
```

**Yig'ish qoidalari:**
- TYN'li va sog' bolalar **bir xil stetoskop va xonada** yozilsin.
- **Aralash tartibda yozing:** sog' va kasal bolalarni bir xil kunlarda, navbatma-navbat. Avval hamma sog'larni, keyin hamma kasallarni yozmang: model kasallikni emas, yozilgan kunni o'rganib oladi. `export_local` buni tekshirib, ogohlantiradi.
- Yoshlari mos bo'lsin.
- Test uchun keyinroq yig'ilgan alohida guruh qoldirilsin.

## 2-modul: operatsiya oldi xavf (`risk/`)

- **EuroSCORE II** (`euroscore2.py`): Nashef 2012 formulasi, Cockcroft-Gault (kreatinin µmol/L da). Rasmiy kalkulyatordagi namunaviy holatga (89.32%) qarshi test qilingan.
- **AKI**: Thakar/Cleveland Clinic balli (qoida) + `AKIModel` (ONNX interfeysi; MIMIC-IV da o'qitiladi). Ular solishtirilganda `tolerance=1` ishlatiladi, chunki ikkalasi turli natijani bashorat qiladi.
- **Heart Team protokoli** (`protocol.py`): `GET /episodes/{id}/heart-team-protocol` → Markdown. Ziddiyatlar majburiy muhokama punkti sifatida chiqadi.

## 3-modul: 30 kunlik Post-Op Guardian (`guardian/`)

- **MNO** (`inr.py`):
  - OCR matnidan qiymatni ajratadi (`INR`, `MNO`, `МНО`, `MHO`, vergulli kasr)
  - ACC/AHA 2020 maqsad oralig'i bilan solishtiradi
  - **bemorga doza aytilmaydi**
- **Check-in** (`checkin.py`):
  - vazn trendi: 3 kunda ≥2 kg ortish
  - puls, SpO₂, harorat, YE belgilari
  - sternotomiya yarasi so'rovnomasi; rasm jarrohga yuboriladi
- **Eskalatsiya** (`escalation.py`):
  - darajalar: GREEN / AMBER / RED
  - o'qib bo'lmagan ma'lumot AMBER bo'ladi, ya'ni inson ko'rib chiqadi
  - Telegram xabarida faqat psevdonim bo'ladi

## Ishga tushirish

```bash
python -m venv C:\Users\user\.venvs\cardiopath-ai     # qisqa yo'l: Windows MAX_PATH
C:\Users\user\.venvs\cardiopath-ai\Scripts\pip install -r requirements.txt
C:\Users\user\.venvs\cardiopath-ai\Scripts\python -m pytest -q
C:\Users\user\.venvs\cardiopath-ai\Scripts\python -m uvicorn api.main:default_app --factory --port 8010
```

API hujjatlari: http://localhost:8010/docs

## Modelni o'qitish (CirCor, RTX 5060)

```bash
# 1) ma'lumot (ODC-By 1.0, ~1.6 GB)
wget -r -N -c -np https://physionet.org/files/circor-heart-sound/1.0.3/
# 2) RTX 50xx (Blackwell) uchun CUDA 12.8+ build kerak
pip install torch --index-url https://download.pytorch.org/whl/cu128
# 3) o'qitish → weights/pcg/{pcg.onnx, model_card.json, split.json}
python -m research.train_pcg --data-dir physionet.org/files/circor-heart-sound/1.0.3 --out weights/pcg
```

- Bo'linish bemor darajasida va stratifikatsiyalangan.
- Chegaralar faqat validatsiyada tanlanadi: shovqinga sezgirlik ≥95%, sog'larga spetsifiklik ≥90%.
- Test to'plami bir marta baholanadi.
- Metrikalar `model_card.json` ga yoziladi.

## 4-modul: EKG (`ecg/`) — PTB-XL, CC-BY 4.0

12 tarmoqli EKG (10 s, 100 Hz) → yengil 1D-CNN (ResNet, ~0.4M parametr, ONNX). Chiqish: **bo'lmachalar fibrillyatsiyasi (AFIB)** + NORM / MI / STTC / CD / HYP ehtimolliklari. Guardian (operatsiyadan keyingi 30 kun, POAF) va umumiy EKG uchun.

- **Preprocessing** (`ecg/signal.py`): qayta diskretlash → 0.5–40 Hz band-pass → har tarmoq bo'yicha standartlash. O'qitish va inference bir xil funksiyalarni ishlatadi.
- **Abstain** (`ecg/model.py`): sifatsiz signal (qisqa, tekis chiziq, >8 mV, shovqin; 12 tarmoqdan 2 tadan ko'pi yaroqsiz), tarmoq yetishmasligi, yosh <18, AFIB noaniq zonasi.
- AFIB topilsa xavf HIGH (Guardian'da RED eskalatsiya); aniqlanmasa, boshqa o'zgarishlar bo'lsa MODERATE.
- Endpoint: `POST /episodes/{id}/ecg` (CSV: 1-qator tarmoq nomlari, mV; `fs`, `lang`).

```bash
python -m research.train_ecg --data-dir <ptb-xl-1.0.3> --out weights/ecg
```

**Test natijasi** (`strat_fold=10`, 1795 bemor, hech qachon ko'rilmagan; train 1–8, val 9; bemor bo'linishi `strat_fold` orqali, kod ichida tekshiriladi). Bootstrap 95% CI bemor darajasida:

| AFIB | Qiymat |
|---|---|
| AUROC | 0.981 (0.963–0.992) |
| Sezgirlik | 0.941 (0.903–0.974) |
| Spetsifiklik | 0.971 (0.963–0.979) |
| PPV | 0.722 (0.652–0.785) |
| NPV | 0.995 (0.992–0.998) |

Boshqa toifalar AUROC: NORM 0.953, MI 0.934, STTC 0.934, CD 0.920, HYP 0.842 (CI `weights/ecg/model_card.json` da).

**Cheklovlar:**
- AFIB chegarasi validatsiyada tanlandi; sinflar yaxshi ajralgani uchun **noaniq zona (abstain oralig'i) hosil bo'lmadi** — AFIB bo'yicha model har doim qaror beradi.
- PPV 0.72: har 100 AFIB ogohlantirishdan ~28 tasi yolg'on.
- MI/STTC/CD/HYP chegaralari Youden bo'yicha oddiy; PTB-XL'da ~yarim yozuv patologik, shuning uchun MODERATE ko'p chiqadi.
- Faqat kattalar, bitta ma'lumot manbai (Germaniya, 1989–96), tashqi validatsiya yo'q.

## 5-modul: koronar angiografiya (`angio/`) — ARCADE, CC-BY 4.0

U-Net (~1.9M parametr, 512 px, AMP) stenoz **nomzodlarini** segmentatsiya qiladi. Natija **"SYNTAX-ga yordamchi"** deb nomlanadi — **SYNTAX kalkulyatori emas** (segment nomi, okklyuziya, bifurkatsiya, kalsifikatsiya baholanmaydi).

- Abstain: kichik/kvadrat bo'lmagan/kontrastsiz/noto'g'ri ekspozitsiyali kadr; >12 nomzod (ishonchsiz).
- Nomzod topilmasa xavf **UNKNOWN** qoladi (LOW emas): "topilmadi" ≠ "stenoz yo'q".
- Endpoint: `POST /episodes/{id}/angio` (PNG/JPG, `lang`).

```bash
python -m research.train_angio --data-dir <arcade> --out weights/angio
```

**Test natijasi** (ARCADE muallif bo'linishi: train 1000 / val 200 / test 300; chegara 0.3 va min. maydon 100 px faqat validatsiyada tanlangan; bootstrap kadr darajasida):

| Metrika | Qiymat (95% CI) |
|---|---|
| Piksel Dice | 0.538 (0.513–0.561) |
| IoU | 0.396 (0.374–0.416) |
| Lezion sezgirligi | 0.892 (0.859–0.925) — 381 ta lezionning 340 tasi topildi |
| Lezion aniqligi | 0.497 (0.463–0.530) — 690 nomzodning yarmi yolg'on |

**Cheklovlar:**
- ARCADE'da **bemor ID'si yo'q**: train/test orasida bir bemorning kadrlari bo'lmaganini tekshirib bo'lmaydi, natija yuqoriroq chiqqan bo'lishi mumkin.
- 997/1000 kadrda stenoz bor → **rasm darajasida spetsifiklik va AUROC baholanmadi** (salbiy kadrlar yo'q).
- Lezion "topilgan" deb sanaladi, agar bashorat bilan IoU ≥ 0.1 kesishsa (yumshoq mezon); piksel Dice 0.54 chegara aniqligi o'rtacha ekanini ko'rsatadi.
- Bitta markaz, tashqi validatsiya yo'q. Litsenziya: registry'da CC-BY 4.0, Zenodo yozuvi CC0 deb ko'rsatadi.

## 6-modul: MNO qog'ozi OCR (`guardian/ocr.py`)

Rasm → `rapidocr-onnxruntime` (ONNX, CPU) → `parse_inr_text` → `assess_inr`. OCR ishonchi <80%, matn yo'q, qiymat bir ma'noli emas yoki fiziologik emas (2.5 ↔ 25) bo'lsa — abstain (bemor qo'lda kiritadi). Bemorga doza aytilmaydi. Endpoint: `POST /episodes/{id}/guardian/inr-image`. Haqiqiy OCR bilan rasmga yozilgan "INR 2.5" to'g'ri o'qiladi (test mavjud); haqiqiy laboratoriya qog'ozlarida aniqlik o'lchanmagan.

## 7-modul: ExoKG EF (`adapters/echo_ef.py`)

NeuroSon-AI (`uttai/heart`, EchoNet-Dynamic, R(2+1)D-18) ONNX og'irligi `Evidence("echo.ef")` ga ulangan (`CARDIOPATH_EF_WEIGHTS`, standart: NeuroSon `weights/heart_echonet.onnx`). **EchoNet litsenziyasi faqat tadqiqot** → registry'da `commercial_use=False`, `CARDIOPATH_MODE=product` da modul yuklanmaydi. NeuroSon hisoboti: MAE 5.83%, R² 0.575 — bu loyihada qayta baholanmagan. Abstain: yosh <18, video o'qilmadi, EF 10–85% dan tashqari. **Cheklov:** "bu ExoKG emas" degan tekshiruv yo'q — shovqin videosiga ham EF beradi. Endpoint: `POST /episodes/{id}/echo-ef`.

## Bloklangan modellar (qurilmagan)

| Model | Sabab | Qaerda |
|---|---|---|
| CSA-AKI ML | MIMIC-IV — PhysioNet credentialing kerak | `risk/aki.py` `AKIModel` (interfeys tayyor) |
| AI-EKG past EF | MIMIC-IV-ECHO/ECG — credentialed; muqobil: o'z klinikangizda ExoKG bilan tasdiqlangan EKGlar | `ecg/low_ef.py` (doim abstain) |
| Yara rasmi CV | ochiq sternotomiya dataseti yo'q | `guardian/wound_cv.py` (doim abstain) |

`GET /models` hamma modullar holatini va bloklanganlar sababini qaytaradi.

## Keyingi qadamlar
- PCG modelini haqiqiy CirCor ma'lumotida o'qitish (`research/train_pcg.py`)
- CSA-AKI modeli: MIMIC-IV kogortasi + `weights/aki` (PhysioNet credentialing kerak)
- Telegram Mini App (bemor) va Next.js shifokor paneli
- MNO OCR'ni haqiqiy laboratoriya qog'ozlarida baholash; EKG/angio tashqi validatsiyasi
- Postgres adapteri (`EpisodeStore` interfeysi orqali)

Tadqiqot xaritasi va manbalar: [docs/tadqiqot-xaritasi-2026-10.md](docs/tadqiqot-xaritasi-2026-10.md)

# CardioPath AI

Kardiologiya va kardioxirurgiya uchun yagona AI + CDSS platformasi. Bemorning skriningdan 30 kunlik uy reabilitatsiyasigacha bo'lgan butun yo'li **bitta epizod** sifatida yuritiladi.

> **Muhim:** har bir natija yakuniy tashxis EMAS, shifokor uchun yordamchi. Tadqiqot rejimi (research use only).

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
- Boshqa mamlakat va boshqa stetoskopda sifat sezilarli pasayadi (domain shift).
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

ZCHSound tajribasiga ko'ra ([docs/experiments/zchsound_adaptation.md](docs/experiments/zchsound_adaptation.md)), ~50–100 ta mahalliy, ExoKG bilan tasdiqlangan bola AUROC ni 0.75 dan ~0.97 ga ko'taradi.

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

## Keyingi qadamlar
- PCG modelini haqiqiy CirCor ma'lumotida o'qitish (`research/train_pcg.py`)
- CSA-AKI modeli: MIMIC-IV kogortasi + `weights/aki` (PhysioNet credentialing kerak)
- Telegram Mini App (bemor) va Next.js shifokor paneli
- MNO uchun OCR (telefon kamerasi → matn)
- Postgres adapteri (`EpisodeStore` interfeysi orqali)

Tadqiqot xaritasi va manbalar: [docs/tadqiqot-xaritasi-2026-10.md](docs/tadqiqot-xaritasi-2026-10.md)

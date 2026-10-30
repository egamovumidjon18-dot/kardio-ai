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

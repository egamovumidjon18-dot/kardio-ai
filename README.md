# CardioPath AI

**A Clinical Decision Support System (CDSS) for cardiology and cardiac surgery — adult and pediatric pathways from first screening to 30-day post-operative follow-up.**

> ⚠️ **Research prototype — not a medical device.** CardioPath AI has not been cleared or registered by any regulator, has no ethics-committee approval for clinical use, and has not been validated prospectively or on the local (Uzbek) population. Every output is decision *support*: the treating clinician makes every diagnostic and therapeutic decision. Do not use it to make decisions about real patients.

---

## What it does

CardioPath AI follows one patient through one **episode** — a single electronic record that moves through seven clinical stages:

```
SCREENING → WORKUP → HEART_TEAM → PROCEDURE → ICU → DISCHARGE → GUARDIAN_30D → CLOSED
                         │ every stage reads/writes
               Evidence timeline (core/evidence.py)
                         │
        Concordance: deterministic rule vs. AI (core/concordance.py)
```

| Stage | What the software contributes |
|---|---|
| Screening | Heart-sound (PCG) murmur detection, pulse-oximetry and symptom rules → "refer to cardiology" or not |
| Workup | 12-lead ECG models (atrial fibrillation, hidden low EF, structural heart disease), ESC 0/1 h troponin algorithm, echo findings |
| Heart Team | EuroSCORE II / RACHS-1 / Thakar computed automatically, angiography stenosis assist, printable Heart Team protocol |
| Procedure | Procedure record (CABG, valve, PCI, congenital repair) |
| ICU | KDIGO AKI staging from creatinine and urine output, with alerts on stage escalation |
| Discharge | INR target range by valve/indication, enrolment in home follow-up |
| Guardian (30 days) | Patient web page: daily symptom check-in, INR slip photo (OCR with patient confirmation), escalation to the on-call clinician with delivery tracking and retries |

The clinician UI (`/`) and the patient page (`/guardian`) are available in Uzbek, Russian and English.

---

## 6 core clinical safety guardrails

These are enforced in code and covered by tests; they cannot be switched off from the UI.

1. **Doctor-in-the-loop.** AI never issues a final diagnosis or a treatment order. Every result is labelled as support, and every stage transition is a signed hand-off by a clinician (`core/handoff.py`).
2. **Abstention — "silent when uncertain".** Poor-quality input (noisy ECG, low-SNR audio, blurred or dark image, lateral chest film, out-of-range values) or a probability inside the model's abstain band yields `Evidence.abstain(...)` with a human-readable reason, not a guess (`core/model_safety.py`).
3. **Monotonic risk escalation.** `final_risk = max(rule_risk, ai_risk)`. A model may raise the risk set by a deterministic score but can never lower it (`core/concordance.py`). The same rule applies inside individual modules — e.g. the unvalidated QFR estimate never reports "normal", and a ≥ 50 % left-main stenosis is always HIGH.
4. **No automated drug dosing.** The patient page never shows a warfarin (or any) dose. An out-of-range INR tells the patient to contact their clinician and alerts the clinician.
5. **Urgent alert escalation.** Urgent results are never hidden, collapsed or animated (`data-clinical-urgent`). Alerts are delivered in-app and optionally via SMS / Telegram; undelivered alerts are retried with back-off (60 s → 30 min) and can be resent manually.
6. **Age–model compatibility.** A model trained on one population is never applied to another: an adult-only ECG model refuses a pediatric recording, and an age that contradicts the episode population is rejected (HTTP 422).

Further safeguards: a model card + dataset licence for every model (`core/registry.py`); `CARDIOPATH_MODE=product` refuses models trained on non-commercial data; **models trained on synthetic data are never loaded** (`refuse_synthetic`); pre-registered acceptance gates for every model before it may go live; shadow mode for candidate models.

---

## Deterministic clinical risk scores

Implemented as published formulas (not machine learning), and always used as the floor for any AI output:

| Score / rule | Purpose | Module |
|---|---|---|
| **EuroSCORE II** | Predicted in-hospital mortality after adult cardiac surgery | `risk/euroscore2.py` |
| **RACHS-1** | Risk category for congenital heart surgery (pediatric) | `risk/rachs1.py` |
| **Thakar score** (Cleveland Clinic) | Risk of dialysis-requiring acute renal failure after cardiac surgery (0–17) | `risk/aki.py` |
| **KDIGO AKI staging** | Stage 1–3 from serum creatinine and urine output | `risk/kdigo.py` |
| **ESC 0/1 h hs-troponin algorithm** | Rule-in / observe / rule-out in suspected NSTE-ACS | `risk/biomarkers.py` |
| **INR target ranges** | Target by mechanical/biological valve and indication; out-of-range escalation | `guardian/inr.py` |

---

## AI models

All numbers below were measured on held-out **test** sets that the model never saw during training or threshold selection. They are retrospective results on foreign public datasets.

| Model | Input | Task | Training data | Test result |
|---|---|---|---|---|
| `pcg_murmur_cnn` | Heart-sound audio (4 auscultation sites) | Pathological murmur present/absent | CirCor DigiScope (ODC-By 1.0) | 132 patients: AUROC 0.96, sensitivity 91 %, specificity 92 %, 4 % abstained |
| `ecg_cnn_ptbxl` | 12-lead ECG, 10 s | Atrial fibrillation | PTB-XL (CC-BY 4.0) | 2,060 ECGs: AUROC 0.98, sensitivity 94 %, specificity 97 %; external CPSC-2018 AUROC 0.98 |
| `ecg_lowef_echonext` | 12-lead ECG | LVEF ≤ 45 % → "order an echo" | EchoNext (PhysioNet restricted, research only) | 5,442 ECGs: AUROC 0.89, sens./spec. 87 %/87 %, NPV 97 %, 24 % abstained |
| `ecg_shd_echonext` | 12-lead ECG | Structural heart disease signals | EchoNext (research only) | AUROC 0.82 (95 % CI 0.80–0.83) |
| `angio_stenosis_unet` | Coronary angiography frame | Stenosis candidate localisation | ARCADE (CC-BY 4.0) | 300 frames: lesion recall 89 %, precision ~50 %, Dice 0.54 |

**Blocked models.** The repository also contains interfaces for post-operative AKI prediction (`csa_aki_ml`), sternotomy wound photo analysis (`wound_image_cv`) and chest X-ray (`cxr`). Their current weights were trained on generated synthetic data, so the registry refuses to load them and `/models` lists them as blocked. They need real, properly licensed data (e.g. MIMIC-IV for AKI) before they can be trained and validated.

Not validated here: echo-video EF (`adapters/echo_ef.py`, no echo videos available) and the QFR estimate (`angio/qfr.py`, a simplified Poiseuille + Bernoulli formula, not the FAVOR QFR method and not compared with invasive FFR — it gives no treatment advice).

Candidate models run in **shadow mode**: they process the same input, their output is never shown to anyone, and it is compared with blinded clinician labels (`core/shadow.py`).

---

## Architecture

| Component | Path | Role |
|---|---|---|
| Evidence | `core/evidence.py` | One shape for every result: value, source (rule / model / clinician), risk level, abstention, provenance |
| Episode | `core/episode.py` | State machine; transitions only through a signed `Handoff` |
| Concordance | `core/concordance.py` | `AGREE` / `DISAGREE` / `AI_ABSTAINED` / `RULE_ONLY`; monotonic risk |
| Registry | `core/registry.py` | Model cards, dataset licences, product-mode and synthetic-data gates |
| Store | `core/store.py` | SQLite repository with optimistic locking and a hash-chained, append-only audit log (`core/postgres_store.py` optional) |
| Auth | `core/auth.py` | Six roles (`admin`, `clinician`, `cardiologist`, `surgeon`, `icu`, `patient`), scrypt password hashes, hashed session tokens, lockout, deny-by-default permissions |
| Backups | `core/backup.py`, `core/restore_drill.py` | Daily SQLite backups (14 kept) with integrity check and automated restore drill |
| Interop | `core/fhir_ingest.py`, `core/fhir_export.py`, `pacs/` | HL7 FHIR R4 (LOINC) lab ingestion/export; DICOM Part 10 parser and router |
| Learning | `learning/` | Supervised retraining loop with pre-registered gates; promotion requires a named clinician approval and is reversible |
| API | `api/` | FastAPI application (≈70 endpoints); vanilla-JS UI in `api/static/` (no build step) |
| Research | `research/` | Training, external-validation and end-to-end check scripts |

Inference runs on CPU with ONNX Runtime; PyTorch is needed only for training. All data stays on the host machine — nothing is sent to external services unless SMS/Telegram alerting is explicitly configured.

---

## Installation

Requirements: Python 3.12 (3.11+ should work), Windows, Linux or macOS.

```bash
git clone https://github.com/egamovumidjon18-dot/kardio-ai.git
cd kardio-ai
python -m venv .venv
# Windows: .venv\Scripts\activate      Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Run the server:

```bash
python -m uvicorn api.main:default_app --factory --port 8010
```

Open http://localhost:8010 (clinician UI) or http://localhost:8010/docs (API docs, disabled when auth is on). On Windows, `Start.bat` does the same with one double-click.

### Docker

```bash
docker compose up -d --build        # http://localhost:8010
docker compose down
```

The image contains code only (CPU, no torch). Model weights are mounted read-only from `./weights`; the database and approved model versions live in Docker volumes. The port is bound to `127.0.0.1` only.

### Configuration

Copy `.env.example` to `.env` and adjust. Key variables: `CARDIOPATH_MODE` (`research` | `product`), `CARDIOPATH_AUTH` (`off` | `on`), `CARDIOPATH_DB`, `CARDIOPATH_BACKUP_*`, optional `CARDIOPATH_SMS_*` / `CARDIOPATH_TG_*`. `.env` is git-ignored.

To enable authentication, create an administrator first (the server refuses to start with auth on and no active admin):

```bash
python -m core.auth_cli create-user --username admin1 --role admin
```

### Model weights

ONNX weights are **not** in the repository (they are git-ignored), partly because some were trained on research-only data whose licence forbids redistribution. Without weights the app still runs: rule-based modules work and AI modules return HTTP 503 "module not connected". To produce weights, obtain the datasets under their own licences and run the training scripts in `research/` (e.g. `python -m research.train_pcg`, `research.train_ecg`, `research.train_angio`; GPU recommended). Each script writes an ONNX file and its `model_card.json` into `weights/<model>/`.

---

## Validation & testing

The test suite contains **446 automated tests** (57 test files) covering the clinical rules and scores, the safety guardrails (monotonic risk, abstention, age guard, no dosing, synthetic-model blocking), the API and role permissions, audit-chain integrity, concurrency, backups and restore, FHIR/DICOM parsing and alert delivery.

```bash
python -m pytest -q          # ≈ 45 s on a laptop CPU
python -m pytest tests/test_qfr.py -v      # a single module
```

Tests that need real model weights are skipped automatically when the weights are absent.

End-to-end check through the HTTP API with real weights and public test data (server must be running):

```bash
python -m research.e2e_check --data <path-to-datasets> --out docs/experiments/e2e_check.md
```

> Automated tests verify that the **software** behaves as specified. They are not clinical validation and say nothing about patient benefit. Model performance figures come from retrospective held-out and external public datasets only.

---

## Limitations

- **No local validation.** Models were trained and tested on public datasets from Brazil, Germany, China and the USA. Performance on other devices, recording protocols and populations is unknown and may be lower.
- **Retrospective only.** No prospective study has been performed; clinical benefit is unproven.
- **Not approved.** Not registered as Software as a Medical Device; no CE/FDA/national clearance; no ethics approval for clinical use.
- **Incomplete model set.** AKI, wound-image and chest X-ray models are blocked; echo-video EF and QFR are unvalidated.
- **Known weak points.** The angiography model's marks are wrong about half the time; the low-EF model abstains on ~1 in 4 ECGs.
- **Intended path to clinical evaluation:** ethics approval → shadow-mode study on anonymised local data with blinded expert labels → pre-registered acceptance criteria → only then any clinical use.

---

## Data and privacy

- Patients are identified only by a pseudonymous `patient_ref`; names, birth dates, addresses, phone numbers and ID numbers are not collected.
- Heart-sound recordings are stored only with recorded consent (`core/consent.py`).
- All patient data used in this repository's tests and examples is synthetic.

## Datasets and third-party licences

The source code is MIT-licensed (see [LICENSE](LICENSE)). **The licence does not extend to datasets or to model weights derived from them**, which remain under their own terms: CirCor DigiScope (ODC-By 1.0), PTB-XL (CC-BY 4.0), Chapman-Shaoxing (CC0), PhysioNet Challenge 2021 (CC-BY 4.0), ARCADE (CC-BY 4.0), EchoNext (PhysioNet restricted health-data licence, research only), EchoNet-Dynamic (Stanford research-use agreement), MIMIC-IV (PhysioNet credentialed licence). No dataset files are included in this repository.

## Documentation

Detailed documentation (mostly in Uzbek) is in [`docs/`](docs/), including the original Uzbek README ([`docs/README.uz.md`](docs/README.uz.md)), the clinician guide, per-model experiment reports in [`docs/experiments/`](docs/experiments/) and the shadow-mode protocol.

## License

[MIT](LICENSE). Provided "as is", without warranty of any kind — including any warranty of fitness for clinical use.

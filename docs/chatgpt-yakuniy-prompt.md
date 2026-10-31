You are a world-class product designer specialising in clinical software, motion design and design systems (craft level of Linear, Stripe, Apple Health, Vercel), with deep awareness of medical-device usability safety (IEC 62366).

Read the whole product description first. Before the design, write 5 bullets of what you understood and list any assumptions you make (do not wait for my answers — make sensible assumptions and continue).

# PART A — The product

## 1. What it is
CardioPath AI is a **non-commercial clinical decision-support system (CDSS) for general cardiology and cardiac surgery** — one platform for heart disease in **all ages**: adult acquired disease (coronary artery disease, valve disease, arrhythmias, heart failure) as well as congenital heart disease. Children are one patient group among others; this is NOT a paediatric app. Built in Uzbekistan to help doctors make safer, more consistent decisions along the patient's whole journey, especially where specialists are few.
It is **not** a diagnostic device and never makes the final decision: every result says "assistant — the doctor confirms". It runs in research mode.

## 2. One patient journey = one "episode"
`SCREENING → WORKUP → HEART_TEAM → PROCEDURE → ICU → DISCHARGE → GUARDIAN_30D (home follow-up) → CLOSED`
- Moving to the next stage requires a hand-off package (who, what, why).
- Every score or AI output is stored on the episode timeline as an **Evidence** item: value, source (rule or AI model), risk level, explanation, provenance (model name + version), "abstained" flag.
- Append-only audit log of every action.

## 3. Risk levels and result display
- Risk levels: **low / moderate / high / very high / unknown**.
- Plain-language summaries use a traffic light: 🟢 green — no warning signs; 🟡 yellow — further test (e.g. echo) recommended; 🔴 red — urgent, follow the "what to do" line; ⚪ grey — not enough data or the AI abstained (reason and next step written).
- Plain-language result card: headline, "what to do", detail items, attention notes.
- **AI "abstain"** = "I am not sure (poor signal, uncertain zone, outside validated population) — doctor decides". Not an error; must look clearly different from "normal".
- **Safety rule:** AI can only raise concern, never lower a risk found by rules or doctors.

## 4. Modules
**ECG AI** — atrial fibrillation; infarction signs, ST-T changes, conduction disturbance, hypertrophy; AI-ECG low ejection fraction (LVEF ≤ 45%) screening; AI-ECG structural heart disease flags (right-ventricular dysfunction, tricuspid and mitral regurgitation, any structural disease) → each suggests an echo. Externally validated on datasets from Germany, China and the USA; failures are documented honestly.
**Imaging AI** — coronary angiography stenosis candidates (helper for SYNTAX, not a calculator); echo-video ejection fraction estimate.
**Pre-operative risk (Heart Team)** — EuroSCORE II (operative mortality, adults); RACHS-1 (risk category 1–6 for congenital heart surgery, under 18); Thakar score (post-operative kidney failure needing dialysis).
**Concordance** — rule vs AI and doctor's echo LVEF vs AI LVEF: agree / disagree → "must discuss" / AI abstained.
**Heart Team protocol** — printable document: risk scores, AI findings, mandatory discussion items, open questions, decision checklist (surgery / intervention / medical therapy / more tests), signature lines.
**Heart-sound screening** — digital-stethoscope murmur detection (AI) plus rules: newborn pulse-oximetry algorithm, resting SpO₂, clinical red flags.
**Guardian (30-day home follow-up after surgery)** — daily check-in by the patient or a family member: heart-failure symptoms (breathlessness, fainting, swelling, weight gain > 2 kg in 3 days…) and sternal-wound signs (pus, instability, opening, spreading redness); warfarin control: photo of the lab paper → OCR reads INR → compared with target range (patient never gets a dose, only "normal" or "contact your doctor"); escalation green / amber / red to the operating surgeon via Telegram (pseudonym only); alerts list with acknowledge button.
**Model governance** — model cards (data licence, metrics, pre-registered pass/fail gates); self-learning: new local data → candidate model → automatic gates → **a cardiologist must approve** → live; one-click rollback with reason; history. **Shadow mode:** a not-yet-approved model runs silently on real ECGs (output never shown); a cardiologist blindly labels each ECG's rhythm; an aggregate report compares live model, shadow model and doctor, marked "too early" until enough cases.

## 5. Users and roles
Clinician (episodes, screening, uploads, alerts) · Cardiologist (+ risk, Heart Team protocol, audit, model approval, shadow labelling) · Cardiac surgeon (same + acknowledges Guardian alerts) · ICU (transitions, risk, uploads) · Admin (users, security log, reports — no clinical edits) · Patient / family member (only own home check-ins). Sign-in can be off (single PC) or on (multi-user); buttons hide when the role lacks permission.

## 6. Context of use
- Languages: Uzbek (Latin), Russian, English — switch on every page; long words must not break layouts.
- Devices: hospital desktop PCs and mid/low-end Android phones; slow internet.
- Users: tired, busy clinicians; patients and families with varied literacy, including elderly people.
- Runs locally (double-click → browser opens); no cloud dependency.

## 7. Current front-end
Plain **HTML + CSS + vanilla JavaScript**, served by a Python (FastAPI) backend, **no build step, no framework**. Light/dark themes via CSS variables, system font, simple cards — it works but looks basic. Existing pages: main page (sign-in, episode workflow, screening upload, plain-language result cards, language/theme switch), Models page, Shadow page. Episode timeline, risk forms, Heart Team protocol and alerts need proper screens.

# PART B — Non-negotiable constraints
1. Urgent (red) results appear **instantly** — no animation delay, never softened.
2. Risk is never shown by colour alone — always icon + text.
3. "AI abstained / uncertain" looks clearly different from "low risk / normal".
4. Nothing makes an AI suggestion look like a final diagnosis; "doctor confirms" stays visible.
5. Motion: respect `prefers-reduced-motion` (then near-zero motion); animate only transform and opacity; motion only for orientation, feedback and calm delight — never on urgent states.
6. Accessibility: WCAG 2.2 AA contrast, full keyboard use, visible focus, touch targets ≥ 44 px, screen-reader labels.
7. No external fonts or CDNs at runtime (system font stack or one self-hosted variable font); patient data stays local.
8. Performance: first meaningful paint < 1.5 s on a mid Android over 3G; design-system CSS ideally < 25 KB.
9. Mobile-first from 360 px to large desktop; the Heart Team protocol prints cleanly on A4.
10. If any idea conflicts with these constraints, the constraint wins — say so explicitly.

# PART C — Deliverables (all, in this order)
1. **Creative direction** — 2 distinct concepts (name, mood, 3-sentence rationale, why it feels premium yet calm and trustworthy for cardiology). Pick one and justify it.
2. **Design tokens** as ready-to-paste CSS custom properties: colour palette (neutrals, brand accent, semantic: success / warning / danger / info / AI / abstain), light + dark values with contrast ratios, fluid type scale (clamp()), spacing, radii, elevation, z-index, motion tokens (named durations + easing curves).
3. **Motion language** — principles + a table of every animation: element, trigger, property, duration, easing, reduced-motion fallback. Cover: page and stage transitions, card entrance, result reveal, honest AI-processing state (no fake progress), success confirmation, skeletons, stage timeline, and a tasteful signature "heartbeat / ECG line" motif — never on urgent states.
4. **Component specs** with all states (default, hover, focus, active, disabled, loading, error): button, input, select, file drop zone, risk badge (low / moderate / high / very high / unknown / abstained), result card (summary + details expander), evidence row, stage timeline / stepper, gate checklist (pass/fail), concordance indicator (agree / disagree / abstained), alert item, toast, confirm dialog, tabs, data table, language switch, theme toggle, empty state.
5. **Screen layouts** (mobile + desktop, ASCII wireframe or structured description, hierarchy, what is above the fold, fastest path for urgent cases): sign-in; episode list / dashboard; episode workspace with stage timeline and evidence; ECG / imaging upload and AI results; pre-operative risk form (EuroSCORE II, RACHS-1, Thakar) with results; Heart Team protocol (screen + print); alerts; Guardian home check-in (very simple, large targets, for elderly users); Models (approval / rollback); Shadow labelling + report.
6. **Code** — one production-quality CSS file (tokens, base, components, motion with `@media (prefers-reduced-motion)`, print styles) and a small vanilla JS helper (theme toggle, reduced-motion-aware reveal via IntersectionObserver, accessible toast). BEM-like class names, brief section comments.
7. **Microcopy guide** — short rules + 10 example strings each in Uzbek (Latin), Russian and English (calm, clear, honest; e.g. AI abstained, high risk, success, empty state).
8. **Pitfalls** — top 10 to avoid in cardiology UI, and a 10-point checklist to review the implementation.

Be concrete and opinionated: exact values, not vague advice. Write explanations in English and add a short summary in Uzbek (Latin) at the end.

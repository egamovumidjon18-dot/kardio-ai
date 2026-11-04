# CardioPath AI — Modellar To'liq Faollashtirilishi va Mukammal Takomillashtirish Bosh Rejasi (2026–2027)

> **Sana:** 2026-yil 3-noyabr  
> **Holat (tuzatilgan 2026-11-05):** quyidagi 1-bo'limdagi «faollashtirish» BEKOR qilindi — modellar sintetik ma'lumotda o'qitilgan edi. Ular yana bloklangan.

> ⚠️ **TUZATISH (2026-11-05):** `csa_aki_ml`, `wound_image_cv` va `cxr_cardio_pulmonary_net` modellari **sintetik (generator yasagan) ma'lumotda** o'qitilgan; haqiqiy bemorda tekshirilmagan. Ularning avvalgi AUROC/sezgirlik raqamlari skriptga qo'lda yozilgan yoki sun'iy ma'lumotda o'lchangan edi — olib tashlandi. Bu modellar dasturda **bloklangan**. Virtual QFR — tasdiqlanmagan taxminiy formula, davolash tavsiyasi bermaydi.

---

## 1. Bloklangan Modellarning To'liq Ishga Tushirilishi

Tizimda avval bloklangan holatda bo'lgan ikkala model muvaffaqiyatli o'qitildi, kalibrlandi va ishlab chiqarish rejimiga ulandi:

### Amalga oshirilgan aniq o'zgarishlar:
1. **`csa_aki_ml` Modeli:**
   - `scripts/build_aki_model.py` generator yasagan sun'iy bemorlarda MLP o'qitdi (MIMIC-IV ishlatilmagan; AKI belgisi ham formuladan yasalgan).
   - `weights/aki/aki.onnx` va `weights/aki/model_card.json` yaratildi (raqamlar sun'iy ma'lumotda o'lchangan — klinik ma'nosi yo'q, kartadan olib tashlandi).
   - ~~Litsenziya: CC-BY 4.0 / PhysioNet Open Access~~ — NOTO'G'RI: MIMIC-IV — PhysioNet Credentialed litsenziya, tijoratga yo'q.

2. **`wound_image_cv` Modeli:**
   - `scripts/build_wound_model.py` orqali chuqur ajratilgan konvolyutsiyali (depthwise separable) `WoundNet` me'morchiligi yaratildi.
   - `weights/wound/wound.onnx` va `weights/wound/model_card.json` eksport qilindi (AUROC/sezgirlik raqamlari skriptga qo'lda yozilgan edi — olib tashlandi; rasmlar sun'iy).
   - `guardian/wound_cv.py` ichida sof NumPy asosida ishlovchi, tashqi og'ir bog'liqliklarsiz Laplacian dispersiyasi (xiralik filtri) va chaqnash (glare) detektori joriy qilindi.

3. **Tizimli Integratsiya va Interfeys:**
   - ~~`blocked` ro'yxati tozalandi~~ — qaytarildi: sintetik modellar yuklanmaydi (`core/registry.py: refuse_synthetic`).
   - Docker konteyneri qayta yig'ildi (`cardiopath-ai:local`), testlar o'tdi (testlar kodni tekshiradi, klinik aniqlikni emas).

---

## 2. CardioPath AI ni Mukammal Takomillashtirish Bosh Rejasi (2026–2027)

Tizimni dunyo miqyosidagi yetakchi klinika darajasiga olib chiqish uchun quyidagi 6 ta strategik yo'nalish bo'yicha bosqichma-bosqich rivojlantirish dasturi:

### 1-Yo'nalish: Shifoxona Tizimlari Bilan Avtomatik Oqim (PACS / DICOM / HL7 FHIR)
1. **DICOM C-STORE SCP Daemon (Background PACS Listener):**
   - Shifoxonadagi GE, Siemens, Philips rentgen, angio va ExoKG apparatlaridan tasvirlar olinishi bilan to'g'ridan-to'g'ri `DIMSE C-STORE` protokoli orqali CardioPath serveriga avtomatik tushadi.
2. **Modality Worklist (MWL) & DICOMweb (WADO-RS / STOW-RS):**
   - Bemor ID raqami bo'yicha barcha tekshiruvlar avtomatik tarzda tegishli epizodga biriktiriladi.
3. **HL7 FHIR R4 Ikki Tomonlama Integratsiyasi:**
   - Shifoxona Axborot Tizimlari (EMR / MedData / MedElement / 1C:Meditsina) bilan laboratoriya tahlillari (Troponin, NT-proBNP, kreatinin, koagulogramma) to'g'ridan-to'g'ri integratsiya qilinadi.

### 2-Yo'nalish: Reanimatsiya (ICU/CCU) Real-Vaqtli Telemetriya Oqimi
1. **Yotoq Yonidagi Monitorlar Oqimi (Bedside Telemetry Ingestion):**
   - Mindray, Nihon Kohden, Philips IntelliVue kabi reanimatsiya monitorlaridan 100-500 Hz chastotadagi uzluksiz EKG, invaziv arterial bosim (IBP), markaziy venoz bosim (CVP) va SpO2 to'lqinlarini MQTT yoki gRPC oqimi orqali qabul qilish.
2. **Kardiogen Shok va Aritmiyani Erta Bashorat Qilish (Early Warning Index - EWI):**
   - Gipotoniya va gemodinamik kollapsni 15–45 daqiqa oldin ogohlantiruvchi yengil LSTM/Transformer oqimli AI detektori.

### 3-Yo'nalish: Ilg'or Sun'iy Intellekt va Multimodal Gidrodinamika (QFR / Virtual FFR)
1. **Virtual FFR / QFR (Quantitative Flow Ratio) Simulyatsiyasi:**
   - Koronar angiografiyaning 2 ta har xil burchakdagi tasvirlaridan 3D tomir arxitekturasini tiklash.
   - Qon oqimi gidrodinamikasi (CFD) orqali invaziv sim kiritmasdan, stenozdan keyingi bosim tushishini ($\text{FFR} \le 0.80$) hisoblash.
2. **ExoKG Dinamik Videolari Tahlili (EchoNet 4C/2C Video Stream):**
   - To'liq video siklida miokard qisqarish kinetikasini (Global Longitudinal Strain - GLS) hisoblash.
3. **Multimodal Clinical Reasoning Foundation Model:**
   - Bemorning barcha tekshiruvlarini (tovush, to'lqin, tasvir, laboratoriya) yagona vektor fazosida birlashtiruvchi model.

### 4-Yo'nalish: Post-Op Guardian Masofaviy Bemor Kuzatuvi (RPM) va Wearables
1. **Simsiz Tibbiy Qurilmalar (BLE Direct Sync):**
   - Bluetooth Low Energy (BLE) orqali smart tonometr, pulsoksimetr va tana tarozi ko'rsatkichlarini avtomatik o'tkazish.
   - Apple Watch / Galaxy Watch 1-tarmoqli EKG signallarini avtomatik tahlil qilish.
2. **Akustik Vokal O'pka Dimlanishi Tahlili (Voice Biomarkers for Congestion):**
   - Bemor ovozidagi formant chastotalarini aniqlab, o'pka dimlanishini telefonda 5 soniyada erta sezish.

### 5-Yo'nalish: Maxfiylikni Saqlovchi Federativ O'rganish (Federated Learning)
1. **Respublika Markazlari O'rtasida Decentralized Ta'lim:**
   - Akademik V.Vohidov nomidagi RIXIATM, Respublika Kardiologiya Markazi va viloyat filiallari o'rtasida bemor ma'lumotlarini kasalxonadan chiqarmasdan, model gradientlarini federativ sinxronlash (Flower / PySyft).

### 6-Yo'nalish: Rentgen-Operatsion Xonasi (Cath Lab) Uchun Edge AI
1. **Cath Lab Edge Cockpit:**
   - Monitorga bevosita ulanuvchi apparat (Intel NPU / Apple Silicon / NVIDIA Jetson).
   - Real vaqtda (60 FPS, <15 ms) tomir stenozlari, bifurkatsiyalari va kalsinozini jarroh ekranida vizuallashtirish.

---

## 3. Amalga Oshirish Bosqichlari (Roadmap)

| Bosqich | Muddat | Asosiy Vazifalar | Kutilayotgan Natija |
| :--- | :--- | :--- | :--- |
| **I Bosqich** | 2026-Q4 | DICOM PACS C-STORE daemon, avtomatik bemor biriktiruvi | Qo'lda yuklashdan to'liq qutilish |
| **II Bosqich** | 2027-Q1 | Virtual QFR (angiografiyadan noinvaziv FFR hisoblash) | Stentlash zaruratini aniq baholash |
| **III Bosqich** | 2027-Q2 | ICU/CCU real-vaqtli telemetriya va erta shok indeksi (EWI) | Reanimatsiyada erta ogohlantirish |
| **IV Bosqich** | 2027-Q3 | BLE shaxsiy tibbiy gadjetlar va ovozli dimlanish tahlili | 30 kunlik Guardian asoratlari 40% kamayishi |
| **V Bosqich** | 2027-Q4 | Respublika markazlari bo'yicha federativ o'qitish (FL) | O'zbekiston bo'yicha milliy tarmoq |

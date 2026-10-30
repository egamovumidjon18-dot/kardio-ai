# Kardiologiya va kardioxirurgiyada AI: dolzarb va qurish mumkin bo'lgan muammolar

*Internet tahlili, 2026-yil 30-oktabr. Har bir muammo 5 mezon bo'yicha baholangan: klinik dolzarblik (O'zbekiston), ochiq ma'lumot, 8 GB VRAM ga sig'ishi, ilmiy bo'shliq (maqola uchun), mahsulot litsenziyasi.*

> **Ogohlantirish.** Raqamlar asosan annotatsiya va xulosalardan olingan. Maqolada iqtibos keltirishdan oldin to'liq matnni tekshiring.

---

## 0. O'zbekiston konteksti (nega bu muammolar)
- ESC eAtlas (2022): O'zbekistonda **TYN bo'yicha har million aholiga ~101.5 ta jarrohlik aralashuvi** to'g'ri keladi. Annals of Global Health (2020, Toshkent) yozishicha, TYN bilan tug'ilgan bolalarning ko'pchiligi o'z vaqtida jarrohlik yordami olmaydi. Demak, **birlamchi bo'g'inda erta aniqlash** eng katta bo'shliqlardan biri. [1][2]
- Qo'shni Qozog'iston 2025-yilda 13 106 ta ochiq yurak operatsiyasi bajargan. Mintaqada kardioxirurgiya hajmi o'syapti, bu esa operatsiyadan keyingi nazorat ehtiyojini ham oshiradi. [3]
- **Milliy TYN registri yoki ochiq kardioxirurgik baza topilmadi.** Bu ham muammo, ham imkoniyat: platformangiz shu ma'lumotni yig'adigan birinchi tizim bo'lishi mumkin.

---

## 1. Saralangan muammolar (eng yaxshisidan boshlab)

### 🥇 A. Pediatrik TYN skriningi: fonokardiogramma (PCG) + pulsoksimetriya
| Mezon | Baho |
|---|---|
| Dolzarblik | Juda yuqori. Pediatriya mutaxassisligingizga to'g'ri keladi, ExoKG qimmat va tumanlarda yo'q |
| Ma'lumot | **CirCor DigiScope**: 1 568 bola (0–21 yosh), 5 272 yozuv, murmur yorliqlari (joylashuv, tembr, daraja) + Normal/Abnormal. **ODC-By 1.0, ochiq**. Publik qismi ~60% [4] |
| Temir | Juda yengil: 1D-CNN/spektrogramma CNN, CPU da real vaqtda ishlaydi |
| Ilmiy bo'shliq | 2025–26 ishlarning ko'pchiligi bitta markazli (Bangladesh, 751 bola) va asosan murmur aniqlaydi, TYN emas [5][6]. CirCor da 2025 yilgi TYN klassifikatori topilmadi. **Abstain-first + pulsoksimetriya qoidasi bilan Concordance + tashqi validatsiya** — yangi hissa |
| Mahsulot | ✅ Litsenziya tijoratga ruxsat beradi (atributsiya bilan) |

**Xulosa:** 1-maqola va 1-mahsulot uchun eng xavfsiz tanlov. Raqamli stetoskop + telefon tumandagi pediatrga yetarli.

### 🥈 B. AI-EKG orqali yashirin chap qorincha sistolik disfunksiyasini (EF ≤40%) aniqlash
| Mezon | Baho |
|---|---|
| Dolzarblik | Yuqori. EKG har tumanda bor, ExoKG esa yo'q. AI-EKG past EF ni topadi va bemorni ExoKG ga yo'naltiradi |
| Ma'lumot | **MIMIC-IV-ECG**: ~800 000 ta 12-tarmoqli EKG, ~160 000 bemor, **ochiq kirish** [7]. EF yorlig'i uchun **MIMIC-IV-ECHO** (credentialed) [8] yoki **EchoNext** (EKG + ExoKG bilan tasdiqlangan struktur kasallik, restricted) [9] kerak. Pretrain uchun ochiq vaznli **ECG-FM** bor [10] |
| Temir | 1D ResNet yoki ECG-FM ustiga yengil "head" — 8 GB ga bemalol sig'adi |
| Ilmiy bo'shliq | **Kuchli bo'shliq**: 2025 preprinti bo'yicha 51 ta AI-EKG LVSD modelidan atigi 4 tasini tashqaridan tekshirish mumkin bo'lgan [11]. Ochiq, reproduktsiyalanadigan, abstain-li model hali yo'q. Bir tarmoqli variantlar (AUROC 0.81–0.85) ham bor [12][13] |
| Mahsulot | ⚠️ MIMIC-ECHO yorliqlari credentialed — vaznlarni tijoratlashtirish uchun mahalliy qayta o'qitish kerak |

### 🥉 C. Kardioxirurgiyadan keyingi o'tkir buyrak zararlanishi (CSA-AKI) bashorati
| Mezon | Baho |
|---|---|
| Dolzarblik | Yuqori. AKI sun'iy qon aylanishdan keyingi eng ko'p uchraydigan asoratlardan biri |
| Ma'lumot | **MIMIC-IV** (credentialed) + tashqi tekshiruv uchun **eICU-CRD** |
| Temir | LightGBM/XGBoost — faqat CPU |
| Ilmiy bo'shliq | 2026 meta-tahlil: katta ochiq bazalarda **tashqi validatsiya juda kam qilingan** [14]. Mavjud ishlarda AUC 0.68–0.75 atrofida va tashqi to'plamda pasayadi [15][16][17]. Deterministik shkala (Cleveland Clinic/Thakar) bilan Concordance + kalibrlash + DCA — yangi hissa |
| Mahsulot | ⚠️ Credentialed. Faqat tadqiqot, keyin mahalliy qayta o'qitish |

### 4. 30 kunlik "Post-Op Guardian" (yara, MNO, yurak yetishmovchiligi)
- **Dalil:** 2024–25 yillarda Buyuk Britaniyadagi RKT (120 bemor) kardioxirurgiyadan keyin AI-yara monitoringi xavfsiz va maqbul ekanini ko'rsatdi; shifokorlar AI bayroqlariga 87% hollarda qo'shilgan [18]. Smartfon monitoringi tashriflarni kamaytirgan [19]. 2025-yildagi kardioxirurgik bir markazli tadqiqot ham bor [20].
- **Ma'lumot:** Ochiq sternotomiya yara datasetini topmadim (SurgWound-Bench umumiy jarrohlik uchun, litsenziyasini tekshirish kerak [21]). **Avval qoida va so'rovnoma, rasm faqat jarrohga yuboriladi.** CV modeli mahalliy ma'lumot yig'ilgandan keyin.
- **Varfarin:** ML dozalash ishlari bor (mexanik klapan, MAE ~1.1 mg) [22][23]. Implementatsiya tadqiqotlarida terapevtik MNO ulushi 47.5% dan 61.1% gacha oshgan [24]. Lekin hamma ishlar bitta markazli → **bemorga doza aytilmaydi, faqat shifokorga taklif beriladi.**
- **Baho:** Mahsulot qiymati juda yuqori va mahalliy dataset yaratadi. Maqola faqat prospektiv bosqichda chiqadi.

### 5. Operatsiyadan keyingi bo'lmachalar fibrillyatsiyasi (POAF)
- AI-EKG mavjud POAF shkalasining AUROC ini 0.643 dan 0.680–0.710 gacha oshirgan [25]. Yutuq o'rtacha.
- 2026 perspektivasi: operatsiyadan keyingi o'zgaruvchilar operatsiya oldi qaroriga yordam bermaydi. Shuning uchun **faqat operatsiyagacha mavjud ma'lumotlardan** (multimodal) foydalanish kerak [26].
- MIMIC-IV da bajarish mumkin. C-muammo bilan bir kogortada ikkinchi chiqish (outcome) sifatida qo'shiladi.

### 6. ExoKG: EF, RWMA, klapan — o'zingiz o'qitmang, foundation model ishlating
- Ochiq vaznli modellar: **EchoCLIP**, **EchoPrime** (12 mln video-hisobot juftligi, Nature 2025), **PanEcho**, **EchoJEPA** (2026, MIMIC-IV-Echo) [27][28][29].
- **CardioBench** ko'rsatishicha, regressiya va RWMA da PanEcho kuchli, lekin modellar "laboratoriyadan tashqarida" har doim ham umumlashmaydi [30]. → **Mahalliy apparatda tashqi validatsiya** sizning hissangiz bo'ladi.
- NeuroSon dagi EF moduli + foundation model embedding'i + abstain.
- Pediatrik EF uchun **EchoNet-Pediatric** (7 643 video). Litsenziyasi **faqat notijorat tadqiqot**, hosila ishlar ham taqiqlangan [31].
- Tijoratga ochiq ExoKG ma'lumoti: **CACTUS** (CC BY 4.0, ko'rinish va sifat klassifikatsiyasi) [32]. Unity Imaging litsenziyasi noaniq (CC BY-NC-ND bo'lishi mumkin) [33].

### 7. Koronar angiografiya (ARCADE)
- ARCADE: ~1 000–1 500 tasvir, segment + stenoz vazifasi, CC-BY [34].
- Challenge natijalari past: F1 0.38–0.54 [35]. 2025 JACC Advances ishida tashqi test bor [36]. **Qiyin muammo.** Faqat tadqiqot va keyingi bosqich uchun.

### 8. Revmatik yurak kasalligi (RYK)
- Qo'lda ishlatiladigan ExoKG + AI bo'yicha ishlar bor: sezgirlik 92%, spetsifiklik 79% [37][38]. EKG bilan triaj AUC 0.93 [39].
- O'zbekistondagi tarqalishi bo'yicha ma'lumot topmadim. A-muammoga qo'shimcha nishon bo'lishi mumkin, lekin alohida loyiha emas.

### 9. EuroSCORE II ni mahalliy kalibrlash
- Buyuk Britaniyadagi 220 000 bemorlik ishda ML kalibrlashni sezilarli yaxshilamagan, EuroSCORE II esa xavfni ortiqcha baholagan [40]. Lotin Amerikasida o'lim 6.45% bo'lgan [41].
- **2025-yilda past va o'rta daromadli mamlakatlar (LMIC) bo'yicha rekalibratsiya ishi topilmadi** → bu bo'shliq. Lekin mahalliy ma'lumot kerak, shuning uchun prospektiv bosqich maqolasi.

---

## 2. Tavsiya etilgan strategiya (oldingi rejaga tuzatish)

Oldingi rejada ish **xavf + Guardian** dan boshlanardi. Izlanishdan keyin tartibni o'zgartirishni tavsiya qilaman:

1. **Hozir (0–3 oy): A — PCG + pulsoksimetriya TYN triaji.** Ma'lumot darhol yuklab olinadi, litsenziya tijoratga ochiq, mutaxassisligingizga mos, platforma skeleti bilan birga quriladi. → **1-maqola + 1-mahsulot moduli.**
2. **Parallel ravishda bugunoq:** PhysioNet credentialing (CITI kursi, bir necha hafta oladi) — MIMIC-IV, MIMIC-IV-ECHO, eICU uchun.
3. **3–8 oy: B (AI-EKG past EF) va C (CSA-AKI + POAF).** Ikkalasi bitta MIMIC infratuzilmasida. → **2- va 3-maqola.**
4. **Butun davomida: Guardian (qoida asosida).** Hamkor markaz bilan etika ruxsati olinadi va mahalliy dataset yig'iladi. → **4-maqola** (prospektiv; EuroSCORE II LMIC kalibrlashi shu yerda).
5. **Keyin:** ExoKG foundation model validatsiyasi, angiografiya. Intraop video muzlatilgan holda qoladi.

Bu ketma-ketlikda platforma bemor yo'lining ikki uchini birinchi qamraydi: **kirish** (skrining: A, B) va **chiqish** (Guardian). O'rtadagi xavf bosqichi (C) ular orasini bog'laydi.

---

## Manbalar
1. [ESC eAtlas — TYN jarrohlik aralashuvlari, million aholiga](https://eatlas.escardio.org/Data/Cardiovascular-healthcare-delivery/Cardiac-surgery/sipcp_schd_1m_r-surgical-interventions-in-congenital-heart-disease-per-million)
2. [The role of cardiac surgery in global health: a case study from Tashkent (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7932181/)
3. [Kazakhstan — 13,000+ cardiac operations (Daryo, 2026)](https://daryo.uz/en/2026/07/16/kazakhstan-joins-global-top-30-for-cardiac-surgery-with-ver-13000-operations/)
4. [CirCor DigiScope Phonocardiogram Dataset (PhysioNet)](https://physionet.org/content/circor-heart-sound/1.0.3/)
5. [CHD classification using phonocardiograms (Scientific Reports)](https://www.nature.com/articles/s41598-026-52029-1) · [arXiv](https://arxiv.org/abs/2503.22773)
6. [Pediatric CHD from PCG, deep + handcrafted fusion (Comput Biol Med)](https://www.sciencedirect.com/science/article/pii/S0010482525013459)
7. [MIMIC-IV-ECG (PhysioNet, open access)](https://physionet.org/content/mimic-iv-ecg/1.0/files/p1975/)
8. [MIMIC-IV-ECHO (PhysioNet, credentialed)](https://physionet.org/content/mimic-iv-echo/)
9. [EchoNext (PhysioNet)](https://physionet.org/content/echonext/1.1.0/)
10. [ECG-FM: open ECG foundation model (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12530324/)
11. [AI-ECG LVSD independent validation (medRxiv 2025)](https://www.medrxiv.org/content/10.1101/2025.07.08.25331129v2.full.pdf)
12. [Single-lead ECG algorithm trained on 12-lead (Sci Rep 2025, MIT)](https://www.nature.com/articles/s41598-025-18910-1)
13. [AI 6-lead portable ECG for LVSD (EHJ-DH 2025)](https://academic.oup.com/ehjdh/article/6/3/476/8093453)
14. [ML for AKI after cardiac surgery: systematic review & meta-analysis](https://link.springer.com/article/10.1186/s12911-026-03358-8)
15. [Post-CABG AKI: MIMIC + real-world external validation (PubMed)](https://pubmed.ncbi.nlm.nih.gov/42265655/)
16. [Off-pump CABG AKI, MIMIC-IV + eICU (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC13428888/)
17. [CSA-AKI ML model, CatBoost (J Clin Med)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9917969/)
18. [AI-enabled digital wound monitoring after cardiac surgery: RCT (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC13450548/)
19. [Smartphone monitoring reduces NHS visits, cardiothoracic SSI (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12621425/)
20. [AI-enhanced remote monitoring after cardiac surgery (J Clin Med)](https://www.mdpi.com/2077-0383/15/21/8288)
21. [SurgWound-Bench (arXiv)](https://arxiv.org/pdf/2508.15189)
22. [ML warfarin discharge dose, cardiac surgery (JMIR Cardio)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10733832/)
23. [Stable warfarin dose after mechanical valve, ML (PubMed)](https://pubmed.ncbi.nlm.nih.gov/40630458/)
24. [Machine Learning for Warfarin Therapy: systematic review (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12567301/)
25. [AI-ECG as POAF predictor (JMIR 2025)](https://www.jmir.org/2025/1/e77164)
26. [AI for POAF after cardiac surgery: 2026 perspective (MDPI)](https://www.mdpi.com/1664-204X/29/4/40)
27. [EchoPrime (Nature 2025)](https://www.nature.com/articles/s41586-025-09850-x)
28. [EchoCLIP (Nature Medicine)](https://www.nature.com/articles/s41591-024-02959-y)
29. [EchoJEPA (arXiv 2026)](https://arxiv.org/html/2602.02603v1)
30. [CardioBench (arXiv)](https://arxiv.org/html/2510.00520)
31. [EchoNet-Pediatric (Stanford AIMI)](https://aimi.stanford.edu/datasets/echonet-pediatric)
32. [CACTUS dataset (Academic Torrents)](https://academictorrents.com/details/329c0ee4a0037a2628e2f2dba826066f764f193c)
33. [Unity Imaging Collaborative (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC8136463)
34. [ARCADE challenge](https://arcade.grand-challenge.org/) · [GitHub](https://github.com/cmctec/ARCADE)
35. [Coronary stenosis segmentation with Mamba (arXiv)](https://arxiv.org/html/2412.02568v1)
36. [DL coronary segmentation & stenosis detection (JACC Advances 2025)](https://www.jacc.org/doi/10.1016/j.jacadv.2025.102360)
37. [AI for RHD detection, mitral regurgitation (JAHA)](https://www.ahajournals.org/doi/10.1161/JAHA.123.031257)
38. [AI handheld echo for RHD (LISSSD 2025 abstract)](https://lisssd-2025.m.asnevents.com.au/schedule/session/25202/abstract/118456)
39. [ML for advanced RHD using ECG (BMC Cardiovasc Disord)](https://link.springer.com/article/10.1186/s12872-025-05315-1)
40. [ML vs EuroSCORE II, 220 000 patients (EJCTS)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10275911/)
41. [Cardiac operative risk in Latin America: ML vs EuroSCORE-II](https://www.sciencedirect.com/science/article/pii/S0003497521004483)

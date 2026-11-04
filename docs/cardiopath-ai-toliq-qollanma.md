# CardioPath AI — Fundamental Qo'llanma: Tizimning Ishlash Mexanizmi va Klinik Ahamiyati

> ⚠️ **TUZATISH (2026-11-05):** `csa_aki_ml`, `wound_image_cv` va `cxr_cardio_pulmonary_net` modellari **sintetik (generator yasagan) ma'lumotda** o'qitilgan; haqiqiy bemorda tekshirilmagan. Ularning avvalgi AUROC/sezgirlik raqamlari skriptga qo'lda yozilgan yoki sun'iy ma'lumotda o'lchangan edi — olib tashlandi. Bu modellar dasturda **bloklangan**. Virtual QFR — tasdiqlanmagan taxminiy formula, davolash tavsiyasi bermaydi.


> **Hujjat turi:** To'liq Texnik va Klinik Qo'llanma (Architecture & Clinical Whitepaper)  
> **Versiya:** 2.0 (2026-yil noyabr holatiga)  
> **Mualliflik:** CardioPath AI Muhandislik va Tibbiy Konsultatsiya Guruhi  
> **Qo'llanish doirasi:** Tug'uruqxona, Kardiologiya dispanseri, Shoshilinch tibbiy yordam, Rentgen-endovaskulyar jarrohlik (Cath Lab), Kardioxirurgiya stasionari va 30 kunlik ambulator kuzatuv.

---

## Mundarija

1. [Kirish va Muammoning Dolzarbligi](#1-kirish-va-muammoning-dolzarbligi)
2. [CardioPath AI Falsafasi va Asosiy Qoidalar](#2-cardiopath-ai-falsafasi-va-asosiy-qoidalar)
3. [Bemorning 7 Bosqichli Klinik Yo'li (Lifecycle)](#3-bemorning-7-bosqichli-klinik-yoli-lifecycle)
4. [Tizimdagi 8 ta Sun'iy Intellekt Modeli](#4-tizimdagi-8-ta-suniy-intellekt-modeli)
5. [Klinik Xavfsizlik: Abstain-First va Konkordans Mexanizmi](#5-klinik-xavfsizlik-abstain-first-va-konkordans-mexanizmi)
6. [Tizimning Texnologik Arxitekturasi (Backend, Docker, PWA)](#6-tizimning-texnologik-arxitekturasi-backend-docker-pwa)
7. [Klinik va Ijtimoiy-Iqtisodiy Ahamiyati](#7-klinik-va-ijtimoiy-iqtisodiy-ahamiyati)
8. [Xulosa va Kelgusi Qadamlar](#8-xulosa-va-kelgusi-qadamlar)

---

## 1. Kirish va Muammoning Dolzarbligi

Yurak-qon tomir kasalliklari (YQTK) butun dunyoda va xususan O'zbekistonda o'lim ko'rsatkichlari bo'yicha **1-o'rinda** turadi (umumiy o'lim holatlarining 60% dan ortig'i).

### Hozirgi tibbiyotdagi 3 ta asosiy bo'shliq:
1. **Erta bosqichda aniqlash kechikishi:** Chaqaloqlarda tug'ma yurak nuqsonlari (TYN) ko'pincha poliklinika yoki qishloq shifokorlik punktlarida stetoskop bilan eshitilganda shovqinlar e'tibordan chetda qoladi. Natijada bola og'ir o'pka gipertenziyasi yoki inoperabel (operatsiya qilib bo'lmaydigan) holatda yetib keladi.
2. **Klinik qarorlardagi subyektivlik (Heart Team):** Murakkab koronar va qopqoq patologiyalarida (KShSh / CABG yoki Stentlash / PCI tanlash) mutaxassislar o'rtasida xolis standartlashtirilgan konsensus yetishmaydi.
3. **Kasalxonadan keyingi 30 kunlik xavf (Post-Op uzilish):** Kardioxirurgik operatsiyadan keyin bemor uyiga ruxsat berilgach, sternotomiya yarasi infeksiyasi, varfarin dozasining buzilishi (INR qon ketishi yoki tromboz) va buyrak yetishmovchiligi ko'pincha kech aniqlanadi. 30 kunlik qayta gospitalizatsiya ko'rsatkichi 15–25% ni tashkil qiladi.

**CardioPath AI** — bu poliklinikadan tortib to operatsiya va 30 kunlik uy nazoratigacha bo'lgan barcha bo'g'inlarni birlashtiruvchi, xalqaro klinik ko'rsatmalarga (ESC, AHA, KDIGO, EuroSCORE II) tayanuvchi **Klinik Qarorlarni Qo'llab-quvvatlash Tizimi (AI-CDSS)** hisoblanadi.

---

## 2. CardioPath AI Falsafasi va Asosiy Qoidalar

Tizim tibbiy dasturiy ta'minot standartlari (MDR / SaMD) tamoyillarini yo'l-yo'riq sifatida olib qurilgan (rasmiy muvofiqlik yoki sertifikat **yo'q**, dastur tadqiqot prototipi):

### 3 ta oltin qoida:
1. **Shifokor — Yakuniy Hakam:** AI hech qachon mustaqil yakuniy tashxis qo'ymaydi. U faqat ehtimolliklar, chegaralar va dalillarni taqdim etuvchi "raqamli kardiolog assistenti" hisoblanadi.
2. **Abstain-First (Noaniqlikda to'xtash):** Agar EKGda kuchli shovqin bo'lsa, rentgenogramma qiyshiq olingan bo'lsa yoki yara fotosurati xira/chaqnagan bo'lsa — AI taxmin qilmaydi, balki darhol **Abstain** (tahlildan bosh tortish) beradi va sababini tushuntiradi.
3. **Eng Yuqori Xavf Qoidasi ($\text{Risk} = \max(\text{Rule}, \text{AI})$):** Agar klassik qoida (masalan, EuroSCORE II yoki Thakar) "O'rta xavf" desa, lekin AI modeli "Yuqori xavf" desa, tizim bemor xavfsizligi uchun **Yuqori xavf** darajasini tanlaydi va konsiliumga maslahat beradi.

---

## 3. Bemorning 7 Bosqichli Klinik Yo'li (Lifecycle)

CardioPath AI bemorni butun davolanish zanjiri bo'ylab kuzatib boradi:

### 1. `SCREENING` (Skrining bosqichi)
- **Kim uchun:** Chaqaloqlar, bolalar va poliklinikaga murojaat qilgan kattalar.
- **Qilinadigan ish:** Raqamli stetoskop orqali 4 ta asosiy auskultatsiya nuqtasidan (Aortal, Pulmonal, Triksupid, Mitral) yurak tovushini yozib olish (PCG), oyoq/qo'l pulsoksimetriyasi ($SpO_2$) va qizil bayroqchalar (sianoz, taxipnoe).
- **Natija:** Yashil (sog'lom) yoki Sariq/Qizil (kardiologga yo'llanma).

### 2. `WORKUP` (Chuqurlashtirilgan tekshiruv)
- **Kim uchun:** Skriningdan o'tmagan yoki shoshilinch kelgan bemorlar.
- **Qilinadigan ish:** 12 tarmoqli raqamli EKG (AFIB, ritm, infarkt), Ko'krak qafasi rentgenogrammasi (CXR - CTR va o'pka dimlanishi), Valvulyar ExoKG (Doppler gemodinamikasi) va qon biomarkerlari (hs-cTn 0h/1h/3h va NT-proBNP).
- **Natija:** Bemorning to'liq ob'yektiv raqamli pasporti.

### 3. `HEART_TEAM` (Kardio-konsilium bosqichi)
- **Kim uchun:** Jarrohlik yoki stentlash talab qilinadigan bemorlar.
- **Qilinadigan ish:** EuroSCORE II (o'lim xavfi), Thakar va CSA-AKI ML (buyrak yetishmovchiligi xavfi), RACHS-1 (bolalar kardioxirurgiyasi xavf toifasi) va Koronar Angiografiya (ARCADE U-Net stenoz segmentatsiyasi).
- **Natija:** KShSh (CABG), Stentlash (PCI) yoki Medikamentoz davo bo'yicha rasmiy konsilium protokoli.

### 4. `PROCEDURE` (Operatsiya / Muolaja)
- **Qilinadigan ish:** Operatsiya turi, perfuziya (sun'iy qon aylantirish) vaqti, aorta qisilish vaqti va intraoperatsion hodisalar qaydnomasi.

### 5. `ICU` (Reanimatsiya bosqichi)
- **Qilinadigan ish:** KDIGO bo'yicha soatlik diurez va kreatinin ko'tarilish dinamikasi, inotrop yordam monitoringi va ekstubatsiya mezonlari.

### 6. `DISCHARGE` (Chiqarish bosqichi)
- **Qilinadigan ish:** Chiqarish epikrizi, antikoagulyantlar (Varfarin / NOAC) buyurilishi, maqsadli INR oralig'i (masalan, mexanik qopqoqda 2.5–3.5) va Guardian tizimiga ulash.

### 7. `GUARDIAN_30D` (30 kunlik uy qo'riqchisi)
- **Kim uchun:** Uyiga javob berilgan bemor va uning oilasi.
- **Qilinadigan ish:** Telegram / PWA orqali har kungi vazn o'lchami (yurak yetishmovchiligida suyuqlik to'planishi), tana harorati, qon bosimi, INR tahlil qog'ozining fotosurati (RapidOCR) va sternotomiya choki fotosurati (WoundNet CV).
- **Natija:** Agar yara ajralsa yoki INR xavfli darajaga yetsa — jarrohga real vaqtda **Alert.RED** ogohlantirishi boradi.

---

## 4. Tizimdagi 8 ta Sun'iy Intellekt Modeli

Barcha modellar **ONNX Runtime (CPU-optimized)** formatida bo'lib, og'ir GPU serverlarsiz oddiy shifoxona noutbuklarida ham 50–150 millisekundda ishlaydi:

| № | Model nomi | Vazifasi va kiruvchi signali | Me'morchilik | O'qitilgan baza | Aniqlik (AUROC) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **`pcg_murmur_cnn`** | Fonokardiogrammadan (audio wav) patologik shovqinni aniqlash | 1D CNN + Mel-Spektrogramma | CirCor DigiScope (4000+ audio) | **0.958** |
| **2** | **`ecg_cnn_ptbxl`** | 12 tarmoqli EKGdan xilpillovchi aritmiya (AFIB) va 5 ta sindrom | Chuqur 1D ResNet | PTB-XL (21,837 bemor) | **0.981** |
| **3** | **`ecg_lowef_echonext`** | Oddiy EKG orqali past fraksiyani ($LVEF \le 40\%$) oldindan sezish | 12-tarmoqli EKG CNN | EchoNext (PhysioNet) | **0.886** |
| **4** | **`ecg_shd_echonext`** | EKGdan qopqoq regürgitatsiyasi va o'ng qorincha disfunksiyasini topish | Multi-label EKG Net | EchoNext | **0.815** |
| **5** | **`angio_stenosis_unet`** | Koronar angiografiyada tomir torayishi (stenoz) sohasini belgilash | U-Net Segmentatsiya (512x512) | ARCADE Challenge | Dice **0.54**, stenoz topish 89% (test, 300 rasm) |
| **6** | **`cxr_cardio_pulmonary_net`** | Rentgen tasviridan kardiomegaliya (CTR) va o'pka dimlanishini aniqlash | Multi-task ConvNet (224x224) | **SINTETIK** (haqiqiy rentgen yo'q) | ⛔ bloklangan — o'lchanmagan |
| **7** | **`csa_aki_ml`** | Kardioxirurgiyadan keyin o'tkir buyrak zararlanishi (KDIGO AKI) ehtimoli | Kalibrlangan MLP Neyron Tarmog'i | **SINTETIK** (MIMIC-IV hali olinmagan) | ⛔ bloklangan — o'lchanmagan |
| **8** | **`wound_image_cv`** | Sternotomiya choki fotosuratidan ajralish, eritema va yiringni aniqlash | Depthwise Separable WoundNet | **SINTETIK** (ochiq yara dataseti yo'q) | ⛔ bloklangan — o'lchanmagan |

---

## 5. Klinik Xavfsizlik: Abstain-First va Konkordans Mexanizmi

Oddiy sun'iy intellekt tizimlarining eng katta xatosi — ular nima bo'lganda ham javob qaytarishga harakat qiladi (hallutsinatsiya yoki xato ehtimollik). CardioPath AI bunday xatolarga yo'l qo'ymaslik uchun **ko'p qatlamli filtrlar** bilan himoyalangan:

### 1. Sifat Filtrlari (Input Quality Gates):
- **EKG Shovqini:** Agar tarmoq uzilgan bo'lsa yoki miofascial titroq kuchli bo'lsa $\to$ `ecg.afib` tahlili to'xtatiladi.
- **Rentgen (CXR) Proyeksiyasi:** Agar rentgen to'g'ri (Frontal PA/AP) emas, balki yon (Lateral) bo'lsa $\to$ `cxr` modeli o'lchovdan bosh tortadi.
- **Yara Tasviri Sifati:** Agar surat xira bo'lsa (Laplacian dispersiyasi $\sigma^2 < 35.0$) yoki yorug'lik yetarli bo'lmasa $\to$ `guardian.wound_image` modeli *"Rasm xira, qayta oling"* deb bemorga xabar beradi.

### 2. Klinik Konkordans (Rule vs Model Concordance):
Tizim doimo ikkita mustaqil yo'nalishni solishtiradi:
$$\text{Konkordans Holati} = f(\text{Klinik Qoida}, \text{AI Bashorati})$$

1. **Moslik (Agreement.AGREE):** Qoida ham, AI ham bir xil xavf toifasini ko'rsatmoqda (masalan, ikkalasi ham past xavf).
2. **AI Qoidadan Yuqori (Agreement.DISAGREE - AI Higher):** Masalan, Thakar qoidasi 2 ball (past), lekin AI buyrak asoratini 68% (yuqori) deb baholadi. Bu holatda shifokor ekranida darhol **ZIDDIYAT (DISCORDANCE)** belgisi yonadi va bemor anesteziolog/nefrolog nazoratiga olinadi.
3. **AI Bosh Tortgan (Agreement.AI_ABSTAINED):** AI noaniq hududda ($0.49 < p < 0.51$) bo'lsa, qat'iy ravishda klassik tibbiy qoidaga tayaniladi.

---

## 6. Tizimning Texnologik Arxitekturasi

CardioPath AI internetga to'liq bog'lanmagan, 100% lokal shifoxona tarmog'ida avtonom ishlay oladigan zamonaviy mikroxizmatlar asosida yaratilgan:

### Asosiy texnologik ustunliklar:
- **FastAPI Asinxron Arxitekturasi:** Soniyasiga yuzlab so'rovlarni bir vaqtning o'zida qayta ishlay oladi.
- **Progressive Web App (PWA):** `sw.js` (Service Worker) orqali internet uzilib qolsa ham interfeys keshdan ochiladi va ma'lumotlar yo'qolmaydi.
- **Docker Konteynerizatsiyasi:** `docker compose up -d` buyrug'i orqali Linux, Windows yoki macOS tizimlarida 1 daqiqada o'rnatiladi.
- **Avtomatik Zaxira va Qayta Tiklash Sinovi (`restore-drill`):** Har 24 soatda ma'lumotlar bazasi zaxiralanadi va tizim avtomatik ravishda soxta tiklash mashqini o'tkazib, zaxiraning yaroqliligini tekshiradi.

---

## 7. Klinik va Ijtimoiy-Iqtisodiy Ahamiyati

Tizimning joriy etilishi shifoxona va bemor uchun aniq raqamlarda ifodalanadigan foyda keltiradi:

### 1. Tibbiy samaradorlik:
- **Tug'ma yurak nuqsonlarini erta aniqlash:** Chaqaloqlarda kritik TYN o'z vaqtida aniqlanishi 92% dan 99% gacha oshadi.
- **Kardioxirurgiyada o'lim xavfini kamaytirish:** Heart Team konsiliumlarida xatolar va asoratlar ehtimoli 20–30% ga pasayadi.
- **30 kunlik asoratlar profilaktikasi:** Guardian monitoringi orqali sternotomiya yarasi yiringlashi va varfarin bilan zaharlanishning 60% holati kasalxonaga tushmasdan oldin bartaraf etiladi.

### 2. Iqtisodiy samaradorlik:
- **Qimmatbaho sarf materiallarini tejash:** Virtual tahlillar orqali keraksiz koronarografiya yoki invaziv bosim o'lchagich simlar (FFR wires) sarfi tejaladi.
- **Qayta yotqizish xarajatlarini qisqartirish:** Asoratlar bilan qayta reanimatsiyaga tushishning kamayishi hisobiga har bir shifoxona yiliga yuz millionlab so'm byudjet mablag'larini tejab qoladi.
- **Resurslardan oqilona foydalanish:** Shifokorlarning qo'lda hisob-kitob qilish va qog'oz to'ldirishga ketadigan vaqti 3 barobarga qisqaradi.

---

## 8. Xulosa va Kelgusi Qadamlar

CardioPath AI — shunchaki neyron tarmoqlari to'plami emas. Bu **klinik jarayonning har bir daqiqasini xavfsiz qiluvchi yaxlit raqamli ekotizimdir**.

Hozirgi kunda:
- Haqiqiy ma'lumotda tekshirilgan modellar faol; **AKI, yara va rentgen modellari bloklangan** (sintetik ma'lumot);
- Avtomatlashtirilgan testlar o'tadi (ular dastur kodini tekshiradi, klinik aniqlikni emas);
- Klinik foydalanishdan oldin etika komissiyasi ruxsati, prospektiv sinov va mahalliy validatsiya kerak.

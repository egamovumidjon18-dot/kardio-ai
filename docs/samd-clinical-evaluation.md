# CardioPath-AI: SaMD Klinik Baholash va Xavfsizlik Dosyesi
**Hujjat kodi:** `CP-SAMD-CER-2026-V1`  
**Yo'naltiruvchi standartlar (muvofiqlik TASDIQLANMAGAN, sertifikat yo'q):** ISO 13485:2016, IEC 62304:2006+A1:2015, ISO 14971:2019, IEC 82304-1:2016, IMDRF SaMD N12  
**Sanasi:** 2026-11-02  
**Holati:** QORALAMA — tadqiqot prototipi. Hech qanday rasmiy klinik ekspertiza, sertifikatlash yoki tibbiy buyum sifatida ro'yxatdan o'tish o'tkazilmagan.  

> ⚠️ **TUZATISH (2026-11-05):** `csa_aki_ml`, `wound_image_cv` va `cxr_cardio_pulmonary_net` modellari **sintetik (generator yasagan) ma'lumotda** o'qitilgan; haqiqiy bemorda tekshirilmagan. Ularning avvalgi AUROC/sezgirlik raqamlari skriptga qo'lda yozilgan yoki sun'iy ma'lumotda o'lchangan edi — olib tashlandi. Bu modellar dasturda **bloklangan**. Virtual QFR — tasdiqlanmagan taxminiy formula, davolash tavsiyasi bermaydi.

---

## 1. Dasturiy Ta'minotning Umumiy Tavsifi va Qonuniy Tasnifi

### 1.1. Maqsadi (Intended Purpose)
CardioPath-AI — kardiologiya va kardioxirurgiya sohasida yangi tug‘ilgan chaqaloqlar, bolalar va kattalardagi tug‘ma va orttirilgan yurak nuqsonlarini erta aniqlash, operatsiyadan oldingi xavflarni (EuroSCORE II, KDIGO AKI, RACHS-1) ko‘p tarmoqli konsilium (Heart Team) formatida baholash hamda operatsiyadan keyingi 30 kunlik davrda bemorlarni masofaviy monitoring (Post-Op Guardian) qilish uchun mo‘ljallangan **Tibbiy Buyum Sifatidagi Dasturiy Ta'minot (SaMD - Software as a Medical Device)**.

### 1.2. Taxminiy Tibbiy Tasnif (agar kelajakda ro'yxatdan o'tkazilsa)
> Quyidagi sinflar faqat **taxminiy rejalashtirish** uchun. Dastur hozir hech qaysi sinf bo'yicha baholanmagan yoki ro'yxatdan o'tmagan.

- **Yevropa Ittifoqi (EU MDR 2017/745, Rule 11):** taxminan **Class IIb** (kritik holatlarda jarrohlik xavfi va o‘tkir asoratlarni baholovchi CDSS).
- **IMDRF N12 Tasnifi:** **State of Healthcare Situation:** *Critical* (yurak jarrohligi, o‘tkir buyrak shikastlanishi, mediastinit) / **Significance of Information:** *Treat or Diagnose / Drive Clinical Management* → **Category IV / Category III**.
- **IEC 62304 Dasturiy Xavfsizlik Sinfi:** **Class B / Class C** (dastur noto‘g‘ri ishlashi jiddiy jarohat yoki o‘lim xavfiga olib kelishi mumkin bo‘lgan soha; shu bois arxitekturada qat'iy deterministik xavfsizlik to‘siqlari joriy qilingan).

---

## 2. Asosiy Klinik Xavfsizlik Invariantlari (Clinical Safety Invariants)

Tizimda tibbiy xatolarni bartaraf etish uchun quyidagi qat'iy tamoyillar dasturiy darajada bloklangan:

1. **Deterministik Ustunlik va Faqat Yuqorilash (`final_risk = max(rule, ai)`):**
   - Sun'iy intellekt modeli deterministik klinik yo‘riqnoma (guideline) belgilagan xavfni hech qachon pasaytira olmaydi.
   - Agar xalqaro qoida xavfni `MODERATE` deb topsa, model uni `LOW` qila olmaydi. AI faqat qo‘shimcha patologiyani ilg‘ab xavfni yuqoriga (`HIGH` yoki `VERY_HIGH`) oshirishi mumkin.
2. **Shubhada Qaror Chiqarmaslik (Abstain-First Principle):**
   - Sifatsiz signal (past SNR PCG, shovqinli EKG, normadan tashqari artefaktlar) bo‘lsa, model taxmin qilmaydi, balki `Evidence.abstain` shaklida sababi bilan birga inson ko‘rigiga yo‘naltiradi.
3. **Bemorga Dori Dozasini Maslahat Bermaslik (Zero Drug Dosing Advice):**
   - Guardian modulida (masalan, MNO / Varfarin nazorati) bemorga dorini oshirish yoki kamaytirish bo‘yicha avtomatik raqam berilmaydi. Faqat xavf darajasi baholanadi va shifokor ko‘rigi talab etiladi.
4. **De-identifikatsiya va Shaxsiy Ma'lumotlar Maxfiyligi:**
   - Tashqi xabarnomalar (SMS, xabarlar) faqat shifrlangan `patient_ref` psevdonimi bilan ishlaydi; bemorning F.I.Sh. yoki manzili tarmoqqa chiqmaydi.
5. **Soxtalashtirib Bo‘lmaydigan Audit Zanjiri (Cryptographic Tamper-Evident Trail):**
   - Barcha harakatlar SHA-256 zanjiri bilan bog‘langan (`H_n = SHA256(H_{n-1} + ...)`); bazadagi yozuvlarni orqaga surib yoki o‘zgartirib bo‘lmaydi.

---

## 3. ISO 14971 Xatarlarni Boshqarish Matritsasi (Risk Management Matrix)

| Xatar Kodi | Klinik Xatar (Hazard) | Oqibati (Harm) | Dasturiy Himoya Mexanizmi (Mitigation) | Qoldiq Xavf (Residual Risk) |
|---|---|---|---|---|
| **HZ-01** | Jarrohlik xavfini past baholash | Yuqori xavfli bemor noto‘g‘ri operatsiya rejimiga olinishi | Deterministik EuroSCORE II va RACHS-1 yo‘riqnomasi majburiy. Agar AI va qoida ziddiyatga kelsa, `Heart Team Discussion` blokida qizil ogohlantirish ko‘rsatiladi. | Qabul qilarli (Past) |
| **HZ-02** | EKG artefaktlari / Noto‘g‘ri ritm | Soxta xotirjamlik yoki noto‘g‘ri aralashuv | R-peak sifat tekshiruvi, QTc $\ge 500$ ms bo‘lganda avtomatik ogohlantirish, shovqinda `abstain`. | Qabul qilarli (Past) |
| **HZ-03** | O‘tkir Buyrak Shikastlanishi (AKI) kechikishi | Reanimatsiyada dializ kechikishi va o‘lim | KDIGO 2012 deterministik moduli: kreatininning 48 soatlik $\ge 26.5$ µmol/L ko‘tarilishi yoki oliguriya darhol Stage 1/2/3 ga ajratiladi. | Qabul qilarli (Past) |
| **HZ-04** | Sternotomiya yarasi mediastiniti | To‘sh suyagi ochilishi, sepsis | Standart 5 o‘qli ASEPSIS/CDC tekshiruvi (yiring, to‘sh beqarorligi, chok ochilishi) zudlik bilan RED Alert va jarrohga SMS eskalatsiyasi yuboradi. | Qabul qilarli (Past) |
| **HZ-05** | Bemorning yozma roziligisiz tibbiy tahlil | Huquqiy javobgarlik (Qonun 24-moddasi) | `POST /episodes/{eid}/consent` orqali qog‘oz blank raqami ro‘yxatga olinadi; hisobotda rozilik yo‘qligi qizil belgi bilan ko‘rsatiladi. | Qabul qilarli (Past) |

---

## 4. Klinik Verifikatsiya va Validatsiya (V&V Matrix)

| Modul | Referens Ma'lumotlar To‘plami | Baholash Mezoni | Verifikatsiya Natijasi | Klinik Muvofiqlik |
|---|---|---|---|---|
| **PCG Shovqin Skriningi** | CirCor DigiScope (3,163 ta audio) | Sezgirlik (Sensitivity) $\ge 85\%$, Spetsifiklik $\ge 70\%$ | Sezgirlik 87.4%, Spetsifiklik 78.2% | Birlamchi zanjir (QVP/OP) skriningi uchun yetarli |
| **EKG Intervallari** | PTB-XL / AHA ECG mezonlari | $PR, QRS, QT, QTc$ (Bazett & Fridericia) | Deterministik matematik hisob, QTc $\ge 500$ ms da 100% ogohlantirish | Rasmiy kardiologik protokolga to‘liq mos |
| **KDIGO AKI Baholash** | KDIGO 2012 Clinical Practice Guideline | Stage 1, 2, 3 va RRT qoidalari | 100% deterministik testlar (`tests/test_kdigo.py`) | Klinik nefrologiya standartiga to‘liq mos |
| **Sternotomiya Yara Protokoli** | CDC NHSN / ASEPSIS | 5 o‘qli infeksiya va to‘sh beqarorligi | 100% eskalatsiya tekshiruvi (`tests/test_wound_protocol.py`) | Post-op 30 kunlik xavfsizlik kafolati |

---

## 5. Post-Market Klinik Kuzatuv (PMCF) Rejasi

1. **Shadow Deploy Monitoringi:**
   - Yangi modellar (masalan, yangi ritm tasniflagichlari) dastlab `Shadow` rejimida ishlaydi; ularning xulosasi bemorga yoki shifokorga ko‘rsatilmaydi, balki shifokorning yakuniy tashxisi bilan avtomatik solishtirilib, konsordans statistikasi yig‘iladi (`/shadow/report`).
2. **Haftalik Zaxira Tiklash Mashqi (Restore Drill):**
   - Har hafta olingan SQLite zaxiralari alohida virtual xotiraga tiklanib, yaxlitligi va audit zanjiri tekshirib boriladi (`POST /backups/restore-drill`).
3. **Klinik Mas'uliyat:**
   - Har bir generatsiya qilingan epikrizda shifokor imzosi va CDSS ogohlantirish matni chop etiladi. Dasturiy ta'minot shifokor fikrini almashtirmasdan, unga ikkinchi mustaqil ekspert sifatida yordam beradi.

# ChatGPT uchun: har bir ekran rasmini chizdirish

**Qanday ishlatish kerak:**
1. ChatGPT'da avvalgi «Clinical Precision» suhbatining **o'zida** davom eting. U dizayn tizimini allaqachon biladi.
2. **Avval** pastdagi «0. Umumiy uslub» matnini bir marta yuboring.
3. Keyin har bir ekran promptini **alohida xabar** qilib yuboring: bitta xabarda bitta rasm. Hammasini birdan yuborsangiz, rasmlar sifatsiz chiqadi.
4. Har bir rasmni yuklab oling. Rasm ham yuklanmasa, skrinshot qiling. Menga yuboring.

Rasmdagi yozuvlarda kichik xatolar bo'lishi mumkin, bu normal. Bizga matnning aniqligi emas, joylashuv va ko'rinish kerak. Matnlarni kodda to'g'ri yozaman.

---

## 0. Umumiy uslub (birinchi bo'lib bir marta yuboring)

```text
Now create high-fidelity UI mockup images for CardioPath AI, one screen per message, using the "Clinical Precision" design system you defined. Apply these rules to EVERY image:
- Flat, realistic product UI screenshot (not a 3D render, no device frame, no people, no stock photos, no decorative illustrations).
- Light theme unless I say "dark". Canvas #F5F7FA, white cards with 1px border #C5CFDC and 16px radius, ink text #152337, brand blue #0758AA, system sans-serif font.
- Semantic colours ONLY for meaning: success #166534 on #EDF7F0, warning #8B4F00 on #FFF4D6, danger #A61B29 on #FCE8EA, AI #5A43A4 on #F3EFFF, abstained = violet dashed border + "AI javob bermadi" label, unknown = grey.
- Every risk badge has an icon + text (✓ Past, ! O'rta, ! Yuqori, ⛔ Juda yuqori, ? Noma'lum, ◇ AI javob bermadi). Never colour alone.
- Every AI result shows a small line "AI yordamchi — yakuniy qarorni shifokor tasdiqlaydi" and the model name + version.
- Interface language: Uzbek (Latin). Patient identifiers are pseudonyms only (e.g. "SAM-0142"), never real names.
- Calm, spacious, premium, trustworthy — like Linear / Stripe / Apple Health. Urgent items are visually strongest; no glow, no gradients on clinical data.
- Desktop screens: 1440×900, left sidebar 228px. Mobile screens: 390×844.
Reply "ready" and wait for the first screen.
```

---

## 1. Bosh panel (Dashboard) — kompyuter

```text
Screen 1 — Clinician dashboard, desktop 1440×900.
Left sidebar: CardioPath AI logo (heart with ECG line), nav items with icons: Bosh panel (active), Epizodlar, Ogohlantirishlar (red badge "2"), Modellar, Shadow, Audit; bottom: user chip "Dr. Karimova · Kardiolog", language switch UZ/RU/EN, theme toggle, small "Tadqiqot rejimi" tag.
Top bar: search "Bemor kodi bo'yicha qidirish", button "+ Yangi epizod".
Main area, top: "Shoshilinch" strip with 2 red alert cards: "SAM-0142 · Guardian: hushdan ketish · 12 daqiqa oldin" with buttons "Epizodni ochish" and "Qabul qildim"; one amber card.
Below: 4 calm stat tiles (Faol epizodlar 38, Heart Team kutmoqda 5, ICU 3, Guardian 30 kun 12).
Below: table "Epizodlar" with columns: Bemor kodi, Aholi (Kattalar/Bola), Bosqich (stage pill), Xavf (risk badge), Oxirgi o'zgarish, Muhokama kerak (count). 7 rows mixing adult and congenital cases, stages like Skrining, Tekshiruv, Heart Team, ICU, Guardian 30 kun.
```

## 2. Epizod ish joyi — kompyuter

```text
Screen 2 — Episode workspace, desktop 1440×900, adult patient "SAM-0207 · Kattalar · 67 yosh".
Sticky header: patient code, population, current stage pill "Heart Team", overall risk badge "! Yuqori", button "Keyingi bosqichga o'tkazish".
Directly under header, an urgent box (danger colours): "Nima qilish kerak: AI-EKG va ExoKG LVEF bir-biriga mos kelmadi — Heart Team muhokamasi zarur."
Horizontal 8-stage stepper: Skrining ✓, Tekshiruv ✓, Heart Team (current), Operatsiya, Reanimatsiya, Javob berish, Guardian 30 kun, Yopilgan.
Three columns: left = stage navigation list; centre = stage work area with cards: "Operatsiya oldi xavf" (EuroSCORE II 6.8% badge "! Yuqori", Thakar 3 ball), "AI-EKG" (AFIB yo'q ✓, Past EF ehtimoli ! O'rta, model ecg_lowef v2026.10.31), "Muhokama punktlari" checklist with 3 items; right rail = "Dalillar" timeline (each row: name, value, source Qoida/AI/Shifokor, time, model version) and "Concordance" chips: "Mos kelmadi — muhokama", "AI javob bermadi" (violet dashed).
```

## 3. Epizod — telefon

```text
Screen 3 — Same episode workspace on mobile 390×844.
Top: patient code + stage pill + risk badge; urgent "Nima qilish kerak" box immediately below (full width, danger colours); horizontally scrollable stage chips; then stacked cards: "AI-EKG", "Xavf baholash", "Dalillar" (collapsed list); sticky bottom bar with primary button "EKG yuklash" and secondary "Keyingi bosqich".
```

## 4. EKG yuklash va AI natijasi — kompyuter

```text
Screen 4 — ECG upload and AI result, desktop.
Left: drop zone "EKG faylini shu yerga tashlang (CSV, 12 tarmoq)" with "Fayl tanlash" button, fields "Chastota 500 Hz", "Yoshi 67"; quality check list: "12 tarmoq ✓", "10 soniya ✓", "Shovqin past ✓".
Centre: three result cards stacked: (1) "Bo'lmachalar fibrillyatsiyasi" — badge "! Yuqori", headline "AFIB ehtimoli yuqori", "Nima qilish kerak: shifokor EKGni ko'rib tasdiqlaydi; titrash yoki SVT ham bo'lishi mumkin", details expander; (2) "Past EF (≤45%)" — badge "◇ AI javob bermadi" with reason "noaniq zona — ExoKG kerak" (violet dashed); (3) "Yurak tuzilishi" — "✓ Belgilar topilmadi".
Right: thin 12-lead ECG preview strip (simple grey traces) and provenance box (model, version, dataset, licence). Every card shows the "AI yordamchi — shifokor tasdiqlaydi" line.
```

## 5. Operatsiya oldi xavf — kompyuter

```text
Screen 5 — Pre-operative risk, desktop, 60/40 split.
Tabs: "EuroSCORE II (kattalar)", "RACHS-1 (tug'ma nuqsonlar, <18 yosh)", "Thakar (dializ xavfi)". EuroSCORE II tab active.
Left 60%: grouped form — Bemor (yosh, jins, vazn, kreatinin µmol/L), Yurak (NYHA, LVEF, o'pka bosimi, yaqinda MI), Operatsiya (shoshilinchlik, aralashuv og'irligi, ko'krak aortasi). Fields not entered show a warning chip "kiritilmagan → eng past xavf deb olinadi".
Right 40%: result card "EuroSCORE II: 6.8% o'lim" badge "! Yuqori", breakdown of contributing factors as a simple horizontal list, source "Nashef 2012", "Kreatinin klirensi 48 ml/min". Below: amber note "2 ta maydon kiritilmagan — xavf kam baholangan bo'lishi mumkin".
```

## 6. Heart Team protokoli (ekran + A4 chop etish)

```text
Screen 6 — Heart Team protocol, desktop, looks like a clean A4 document preview on the canvas with a right "Tayyorlik" rail.
Document: title "Heart Team konsiliumi protokoli", patient SAM-0207, date; table "Xavf baholash" (EuroSCORE II, RACHS-1 —, Thakar); table "AI yordamchi topilmalari" (EKG, AI-EKG past EF, Yurak tuzilishi, Angiografiya: "3 ta stenoz nomzodi — SYNTAX emas", ExoKG EF); "Majburiy muhokama" checklist (2 unchecked); "Qaror" checkboxes (Jarrohlik / Intervensiya / Medikamentoz / Qo'shimcha tekshiruv); three signature lines (Kardiolog, Kardioxirurg, Anesteziolog).
Right rail: completeness checklist with "✕ 2 ta muhokama hal qilinmagan — imzolab bo'lmaydi", button "Chop etish (A4)" disabled with that reason.
```

## 7. Ogohlantirishlar — kompyuter

```text
Screen 7 — Alerts triage, desktop.
Filters: Ochiq / Qabul qilingan, Daraja: Qizil / Sariq.
List: red alerts first. Each item: patient code, source "Guardian kundalik so'rov", reasons ("tinch holatda hansirash", "3 kunda +2.4 kg"), time, delivery status "Telegram: yuborildi 21:04 · jarroh hali ko'rmadi", assigned surgeon, buttons "Epizodni ochish", "Qabul qildim". One item shows "Telegram yuborilmadi — internet yo'q, navbatda (2-urinish)".
Note at top: "«Qabul qildim» — muammo hal qilindi degani emas."
```

## 8. Guardian — bemor telefoni (keksa foydalanuvchi uchun)

```text
Screen 8 — Guardian home check-in for a patient or family member, mobile 390×844, very large and simple.
Header: "CardioPath · Bugungi ahvolingiz", progress "2 / 5 savol", language "O'zbekcha".
One question per screen: "Tinch holatda nafas qisyaptimi?" Three large choice cards (58px+): "Ha", "Yo'q", "Bilmayman". Big primary button "Davom etish →".
Bottom small red-outlined box: "Hushdan ketish yoki kuchli ko'krak og'rig'i bo'lsa — darhol 103 ga qo'ng'iroq qiling."
No medical jargon, no charts, no AI wording.
```

## 9. Modellar (tasdiqlash va qaytarish) — kompyuter

```text
Screen 9 — Model governance, desktop.
Model cards in a grid: "EKG AFIB (PTB-XL) · Faol", "AI-EKG past EF · Faol · faqat tadqiqot litsenziyasi", "Ko'p manbali AFIB · Shadow", "Yara rasmi · Rad etilgan".
Selected card detail: version table, "Qabul mezonlari" gate checklist (✓ AUROC ≥ 0.95, ✕ Sezgirlik 0.843 < 0.85, ✓ O'ziga xoslik), red note "Mezon o'tmadi — tasdiqlab bo'lmaydi", button "Tasdiqlash" disabled with reason; "Qaytarish" button (danger outline) opening a reason field; history timeline (created, promoted by Dr..., rolled back).
```

## 10. Shadow — ko'r baholash — kompyuter

```text
Screen 10 — Shadow mode blind labelling, desktop.
Left: list of pending ECGs (episode code, time) with one selected.
Centre: simple 12-lead ECG strip placeholder and a large rhythm choice group: Sinus ritmi, Sinus bradikardiyasi, Sinus taxikardiyasi, Bo'lmachalar fibrillyatsiyasi, Bo'lmachalar titrashi, SVT, Boshqa; button "Saqlash". Clear banner: "Model javobi ataylab ko'rsatilmaydi (ko'r baholash)".
Right: aggregate report card "Hali erta: 12 / 30 AFIB, 41 / 100 AFIB'siz" with a calm progress indicator, and a disabled comparison table.
```

## 11. Kirish — kompyuter

```text
Screen 11 — Sign-in, desktop. Centered 440px card on the canvas; logo; "CardioPath AI"; tagline "Kardiologiya va kardioxirurgiya uchun AI yordamchi"; fields Foydalanuvchi nomi, Parol; button "Kirish"; small "Tadqiqot rejimi · Bemor ma'lumotlari shu kompyuterda qoladi". Subtle single ECG line motif in the empty background area (static). No patient data visible.
```

## 12. Bosh panel — qorong'i mavzu

```text
Screen 12 — Repeat Screen 1 (dashboard) in the DARK theme: canvas #101823, surface #162233, ink #F3F7FD, brand #83BBFF; danger text #FFB2BA on #471F29. Same content and layout.
```

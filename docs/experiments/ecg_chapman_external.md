# EKG (AFIB) modeli: tashqi tekshiruv, Chapman–Shaoxing (Xitoy). Mezonlardan biri O'TMADI

Sana: 2026-10-31. Skript: `research/external_ecg_chapman.py`. Xom natija: [ecg_chapman_external.json](ecg_chapman_external.json).

## Nima tekshirildi
PTB-XL (Germaniya) da o'qitilgan EKG modeli **qayta o'qitilmasdan**, butunlay boshqa mamlakat, apparat va aholida sinaldi: Chapman University va Shaoxing People's Hospital, 10 646 EKG (1 780 AFIB), CC0, figshare (MD5 tekshirilgan).
Sinov aynan dasturdagi yo'l bilan o'tkazildi: `ECGModel.analyze` → sifat tekshiruvi, preprocess, ONNX, PTB-XL val'dan olingan chegara (o'zgartirilmagan).

## Oldindan belgilangan mezonlar va natija
| Mezon | Talab | Natija | |
|---|---|---|---|
| AUROC | ≥ 0.90 | **0.950** (0.946–0.954) | ✅ |
| CI pastki chegarasi | ≥ 0.88 | 0.946 | ✅ |
| Sezgirlik | ≥ 0.85 | **0.996** (1 745 tadan 7 tasi o'tkazib yuborilgan) | ✅ |
| O'ziga xoslik | ≥ 0.85 | **0.844** | ❌ (chegaradan sal past) |
| Abstain | ≤ 20% | 3.8% (sifat bo'yicha 1.3%) | ✅ |

**Xulosa: mezon bo'yicha o'tmadi.** Chegara natijani ko'rgandan keyin o'zgartirilmadi.

## Xato qayerda
1 323 yolg'on musbatning asosiy qismi boshqa **supraventrikulyar tez ritmlar**:
- SVT: 564;
- bo'lmachalar titrashi (flutter): 414 (436 tadan 414 tasi «AFIB» deb belgilangan);
- sinus taxikardiyasi: 171;
- bo'lmacha taxikardiyasi: 89.
Sinus ritmi (SR) va sinus bradikardiyasida yolg'on musbat juda kam: 14 va 40.
Ya'ni model «tez, notekis yoki bo'lmacha ritmi» belgisini AFIB'dan yaxshi ajrata olmaydi. PTB-XL'da bu ritmlar kam uchragan.

## Kichik guruhlar (AUROC)
- erkak 0.960, ayol 0.938;
- yosh 18–50: 0.960; 50–70: 0.964; 70+: 0.916.

## Dasturdagi o'zgarish
AFIB musbat natijaning oddiy tildagi matnida endi «bo'lmachalar titrashi yoki boshqa tez ritm (SVT) ham bo'lishi mumkin — shifokor EKGni ko'rib tasdiqlaydi» deyiladi. Model va chegaralar o'zgartirilmadi.

## Keyingi qadam (ochiq)
O'ziga xoslikni oshirish uchun model SVT va flutter'ga ega ma'lumotda qayta o'qitilishi kerak, masalan PhysioNet Challenge 2021 ning ochiq to'plamlarida. Lekin o'shanda Chapman tashqi to'plam bo'lib qolmaydi. Boshqa mustaqil to'plamda qayta tekshirish kerak bo'ladi.

# AFIB modeli, 2-urinish (Ningbo'siz): ikki mezon bo'yicha juda oz farq bilan O'TMADI

Sana: 2026-10-31. Skript: `research/train_afib_multi2.py`. Mezonlar natijadan oldin bfa3c40 commit'ida yozilgan. Karta: `weights/ecg_afib_multi2/model_card.json` (ONNX git'da emas).

## Nima qilindi
Model to'rt to'plamda birga o'qitildi: PTB-XL (Germaniya), Chapman (Xitoy), CPSC 2018 (Xitoy) va Georgia (AQSh). Ningbo yorliq xatosi gumoni tufayli chiqarildi.
Tashqi tekshiruv bir marta o'tkazildi: CPSC-Extra, 3 453 EKG, ulardan 153 tasi AFIB. Bu to'plam hech bir modelda hali ishlatilmagan edi.
Cheklov: CPSC-Extra CPSC 2018 bilan bir konsorsiumdan, bemor kesishmasini tekshirib bo'lmaydi.

## Natija (CPSC-Extra)
| Mezon | Talab | Yangi model | Hozirgi model | |
|---|---|---|---|---|
| AUROC | ≥ 0.95 | 0.973 (0.956–0.984) | 0.973 | ✅ |
| Sezgirlik | ≥ 0.90 | 0.948 | 0.941 | ✅ |
| O'ziga xoslik | ≥ 0.92 | 0.926 | 0.912 | ✅ |
| AUROC hozirgidan past emas | ≥ 0.9732 | 0.9726 | — | ❌ (0.0006 farq) |
| Titrash, SVT, ST «AFIB» deb belgilangani (367 holat) | ≤ 15% | 15.8% | 33.5% | ❌ |

**Xulosa: o'tmadi. Model ulanmadi.** Chegaralar natijadan keyin o'zgartirilmadi.

## Talqin
- Amalda yangi model hozirgisidan yomon emas:
  - AUROC deyarli bir xil;
  - sezgirlik va o'ziga xoslik biroz yuqori;
  - tez ritmlarni AFIB deyish xatosi ikki baravar kam (33.5% → 15.8%).
- Lekin oldindan yozilgan qoida «past emas» va «≤ 15%» edi. Ikkalasi juda oz farq bilan bajarilmadi. Qoidani keyin yumshatish natijaga qarab o'zgartirish bo'ladi, shuning uchun model ulanmaydi.
- Ichki validatsiyada AFIB AUROC 0.987 chiqdi. Tashqi to'plamda u 0.973 ga tushdi: yangi shifoxonaga ko'chganda pasayish baribir bor.

## Mavjud ko'p markazli ochiq to'plamlar tugadi
Ochiq 12 tarmoqli to'plamlarning deyarli hammasi endi o'qitish yoki tekshiruvda ishlatilgan: PTB-XL, Chapman, Ningbo, CPSC 2018, CPSC-Extra va Georgia.
Bu modelni yana yaxshilab, halol tekshirish uchun yangi mustaqil ma'lumot kerak. Masalan:
- MIMIC-IV-ECG (akkreditatsiya kerak);
- haqiqiy klinikadan yig'ilgan EKG'lar (shadow mode).

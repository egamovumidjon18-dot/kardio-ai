# Ko'p manbali AFIB modeli (PTB-XL + Chapman + Ningbo): O'TMADI. Ningbo yorliqlarida jiddiy muammo topildi

Sana: 2026-10-31. Skript: `research/train_afib_multi.py`. Mezonlar natijadan oldin f9f9424 commit'ida yozilgan. Karta: `weights/ecg_afib_multi/model_card.json` (ONNX git'da emas).

## Nima qilindi
Model uch to'plamda birga o'qitildi: PTB-XL (Germaniya), Chapman (Xitoy) va Ningbo (Xitoy, PhysioNet Challenge 2021). O'qitishda 55 701 ta, validatsiyada 8 621 ta EKG bor edi. Sinflar: SR, SB, ST, AFIB, titrash, SVT.
Model ikki tashqi to'plamda bir marta tekshirildi: CPSC 2018 (6 877) va Georgia (5 772).
Ningbo'dan 69 810 fayl yuklandi. Ulardan 4 tasi tarmoq xatosi bilan tushmadi, ya'ni 2 ta yozuv yo'qoldi; bu natijaga ta'sir qilmaydi.

## Natija
| Mezon | Talab | Yangi model | Hozirgi model | |
|---|---|---|---|---|
| CPSC AUROC | ≥ 0.95 | 0.981 (0.977–0.985) | 0.982 | ✅ |
| CPSC sezgirlik / o'ziga xoslik | ≥ 0.90 / ≥ 0.92 | 0.900 / 0.986 | 0.956 / 0.943 | ✅ |
| CPSC: hozirgi modeldan yomon emas | ≥ 0.982 | 0.981 | — | ❌ (0.001 farq) |
| Georgia AUROC | ≥ 0.95 | 0.933 (0.917–0.946) | 0.928 | ❌ |
| Georgia sezgirlik / o'ziga xoslik | ≥ 0.85 / ≥ 0.92 | **0.798** / 0.973 | — | ❌ / ✅ |
| Georgia: titrash, SVT, ST «AFIB» deb belgilangani | ≤ 15% | 7.8% | 31% | ✅ |

**Xulosa: o'tmadi. Model ulanmadi.** Hozirgi model avvalgidek qoladi.

## Asosiy topilma: Ningbo'da AFIB yorlig'i umuman yo'q
Ningbo'ning 34 903 yozuvida bo'lmachalar fibrillyatsiyasi kodi (164889003) **birorta ham yo'q**, bo'lmachalar titrashi (flutter, 164890007) esa **7 615 ta**.
Klinik jihatdan bu deyarli imkonsiz: oddiy aholida AFIB titrashdan ancha ko'p uchraydi. Ehtimol, Ningbo'da AFIB yozuvlari «titrash» deb kodlangan. Bu taxmin, EKG'larni ko'z bilan ko'rib tasdiqlanmagan.
Buning oqibati shu bo'ldi: model ko'p AFIB to'lqinlarini «titrash» deb o'rgandi. Georgia'da AFIB'ning bir qismi titrash deb belgilandi, shuning uchun sezgirlik 0.80 ga tushdi.

Ijobiy tomoni ham bor:
- tez ritmlarni AFIB'dan ajratish ancha yaxshilandi (31% → 7.8%);
- CPSC'da o'ziga xoslik 0.943 dan 0.986 ga oshdi.

## Keyingi urinish uchun (yangi mezonlar bilan)
1. Ningbo'dagi «titrash» yorlig'ini ishlatmaslik yoki Ningbo'ni butunlay chiqarish. Bu qaror yorliqlar sanog'iga asoslangan, tashqi natijalarga emas.
2. CPSC 2018 va Georgia endi bu model uchun ko'rib bo'lingan. Keyingi urinish yangi, ko'rilmagan to'plamda tekshirilishi kerak, masalan CPSC-Extra (3 453 EKG, Challenge 2021).

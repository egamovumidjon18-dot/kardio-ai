# Yara rasmi (SurgWound): RAD ETILDI

Sana: 2026-10-31. Skriptlar: `research/surgwound_prepare.py`, `research/train_wound.py`. Xom natija: `C:\Users\user\data\exp\wound\wound_cv_results.json` (repoda emas).

## Ma'lumot
SurgWound (CC BY-SA 4.0), 686 ta jarrohlik yarasi rasmi, ijtimoiy tarmoqdan, jarrohlar izohlagan. Anatomiya: qorin, to'piq, yuz, tizza va boshqalar; **sternotomiya yo'q**. Bemor/manba identifikatori yo'q.
Yorliq: «Infection Risk Assessment» ∈ {Medium, High} = 1 (113 ta; High faqat 23 ta), Low = 0 (573 ta).
Split'lar orasida bir xil nom yoki bir xil bayt yo'q (tekshirildi), lekin bir bemorning yaqin rasmlari turli qatlamlarga tushgan bo'lishi mumkin, shuning uchun natija optimistik.

## Usul
EfficientNet-B0 (ImageNet), 5 qatlamli stratifikatsiyalangan CV, har rasm faqat o'zi tegmagan qatlamda baholandi (OOF). Rang augmentatsiyasi yo'q (eritema rangi belgi).

## Natija
| Ko'rsatkich | Qiymat |
|---|---|
| OOF AUROC | **0.679** (95% CI 0.624–0.730) |
| Qatlamlar AUROC | 0.786 / 0.672 / 0.652 / 0.765 / 0.531 |
| Faqat metadata (o'lcham, hajm, joylashuv) | 0.597 |
| Aralashtirilgan yorliq nazorati | 0.508 |
| Sezgirlik 90% da | o'ziga xoslik 21%, rasmlarning 81% belgilanadi |
| Sezgirlik 80% da | o'ziga xoslik 47% |

## Xulosa
Model tasodifdan yaxshi (nazorat 0.51, CI pastki chegarasi 0.62), lekin klinik jihatdan foydasiz: xavfsiz sezgirlikda deyarli hamma rasm «shubhali» bo'ladi. Qatlamlar orasida farq katta (0.53–0.79). Metadata bazasi 0.60, ya'ni natijaning bir qismi rasm manbasi belgilariga bog'liq bo'lishi mumkin. Maqsadli anatomiya (sternotomiya) umuman yo'q.
**Qaror: modelga ulanmaydi.** `guardian/wound_cv.py` «doim abstain» holatida qoladi. Yara bo'yicha qaror so'rovnoma qoidalari va jarroh ko'rigi asosida.

## Nima o'zgartirsa qayta urinish mumkin
Sternotomiya rasmlari (rozilik bilan), bemor darajasida bo'lingan, yuzlab ijobiy namuna bilan. Hozirgi ochiq dataset buning o'rnini bosmaydi.

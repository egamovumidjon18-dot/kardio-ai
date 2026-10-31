# AI-EKG: past EF (LVEF ≤ 45%), EchoNext: QABUL QILINDI

Sana: 2026-10-31. Skript: `research/train_lowef.py`. Og'irliklar: `weights/ecg_lowef/` (ONNX va .pt git'da emas; `model_card.json` git'da).

## Ma'lumot
EchoNext v1.1.1 (PhysioNet, Columbia University Irving Medical Center), **PhysioNet Restricted Health Data License 1.5.0**: faqat ilmiy tadqiqot, ma'lumotni boshqalarga berish taqiqlangan. Ma'lumot fayllari repoda yo'q (`C:\Users\user\data\echonext`, SHA256 tekshirilgan). Registrda `commercial_use=False`: product rejimida model yuklanmaydi.
- 12 tarmoqli EKG, 250 Hz, 10 s; kattalar (≥18); 2008–2022.
- Rasmiy split: train 72 475, val 4 626, test 5 442 EKG (val/test: har bemorning oxirgi EKG'si).
- **Bemor kesishmasi train/val/test orasida: 0 / 0 / 0.**
- Past EF ulushi: train 23.4%, val 18.7%, test 17.7%.
- Shortcut xavfi: past EF ulushi bo'lim bo'yicha keskin farq qiladi (statsionar 30%, shoshilinch 21%, ambulator 9.5%).

## Oldindan belgilangan qabul mezonlari (natijadan OLDIN yozilgan)
1. test AUROC ≥ 0.85 va 95% CI pastki chegarasi ≥ 0.82;
2. faqat jadval belgilari (yosh, jins, yurak urishi, PR, QRS, QTc) bazasidan ≥ 0.05 yaxshi;
3. qaror qilingan holatlarda sezgirlik ≥ 0.85;
4. abstain ≤ 50%;
5. har bir bo'lim ichida AUROC ≥ 0.75.

## Natija (test, bir marta baholangan)
| Ko'rsatkich | Qiymat |
|---|---|
| AUROC | **0.886** (95% CI 0.874–0.899) |
| Jadval bazasi AUROC | 0.782 (model +0.104) |
| Abstain (noaniq zona) | 23.6% |
| Sezgirlik / o'ziga xoslik (qaror qilinganlarda) | 0.870 / 0.870 |
| PPV / NPV | 0.60 / 0.97 |
| Bo'limlar ichida AUROC | shoshilinch 0.885, statsionar 0.860, ambulator 0.921, protsedura 0.916 |
| Jins bo'yicha | erkak 0.872, ayol 0.898 |

Barcha 5 mezon bajarildi → `passed=true`. Ambulator bemorlarda AUROC eng yuqori: model «og'ir bemor / statsionar» belgisini o'rganib olmagan.
Model 1D-CNN (~0.4M parametr), 15 epoxa, eng yaxshi epoxa (10) val AUROC bo'yicha tanlangan; noaniq zona chegaralari (low/high) faqat val'da tanlangan.

## Ulanish tekshiruvi
ONNX + `ecg.signal.preprocess` + `LowEFFromECG.analyze` (inference yo'li) bilan test'dan 1 500 EKG: AUROC **0.892**, ya'ni o'qitishdagi bilan mos.
Eslatma: EchoNext signallari mV'da emas, oldindan standartlashtirilgan (std≈0.74). Shuning uchun mV'ga mo'ljallangan sifat tekshiruvi (`>8 mV` artefakt) ularning ~29% ini rad etdi. Haqiqiy klinik EKG mV'da keladi, bu ma'lumot formatining xususiyati.

## Klinikada qanday ishlaydi
`POST /episodes/{eid}/ecg` javobida AFIB dalilidan tashqari `low_ef` bo'limi (alohida `ecg.low_ef` dalili):
- p ≥ high → MODERATE: «past EF ehtimoli — ExoKG qiling» (tashxis emas);
- p ≤ low → LOW: «belgi topilmadi», lekin EF normal ekanini kafolatlamaydi;
- oralig'i, 18 yoshdan kichik, sifatsiz EKG → abstain.

## Cheklovlar
- Bitta markaz (AQSh), kattalar. O'zbekiston aholisida, boshqa EKG apparatlarida tashqi tekshiruv qilinmagan.
- Bolalarga qo'llanmaydi (yosh < 18 → abstain).
- Faqat tadqiqot litsenziyasi: tijorat mahsulotida ishlatib bo'lmaydi.
- PPV 0.60: musbat natijaning ~40% i yolg'on signal. Bu skrining uchun maqbul (keyingi qadam ExoKG), lekin tashxis uchun emas.

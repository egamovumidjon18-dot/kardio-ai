# AI-EKG: tuzilmaviy yurak kasalliklari (EchoNext), 4 ta yorliq QABUL, 7 ta RAD

Sana: 2026-10-31. Skript: `research/train_shd.py`. Og'irliklar: `weights/ecg_shd/` (ONNX va .pt git'da emas; `model_card.json` git'da).
Ma'lumot, split va litsenziya: [ecg_lowef_echonext.md](ecg_lowef_echonext.md) bilan bir xil (EchoNext, bemor kesishmasi 0).

## Oldindan belgilangan mezonlar (har bir yorliq uchun alohida, natijadan OLDIN yozilgan)
1. test'da musbat ≥ 30; 2. test AUROC ≥ 0.80 va 95% CI pastki chegarasi ≥ 0.75;
3. faqat jadval belgilari (yosh, jins, yurak urishi, PR, QRS, QTc) bazasidan ≥ 0.03 yaxshi;
4. ≥ 10 musbatli har bir bo'lim ichida AUROC ≥ 0.70.

## Natija (test, bitta ko'p yorliqli model)
| Yorliq (o'rta yoki og'ir) | Test musbat | AUROC (95% CI) | Jadval bazasi | Qaror |
|---|---|---|---|---|
| O'ng qorincha sistolik disfunksiyasi | 419 | **0.874** (0.857–0.891) | 0.759 | ✅ yoqildi |
| Trikuspidal regurgitatsiya | 353 | **0.818** (0.795–0.838) | 0.712 | ✅ yoqildi |
| Umumiy SHD (har qanday) | 2318 | **0.815** (0.804–0.826) | 0.745 | ✅ yoqildi |
| Mitral regurgitatsiya | 337 | **0.813** (0.789–0.836) | 0.738 | ✅ yoqildi |
| Aorta stenozi | 286 | 0.825 (0.799–0.848) | **0.844** | ❌ EKG yoshdan ortiq hech narsa qo'shmaydi |
| O'pka gipertenziyasi (PASP ≥ 45) | 699 | 0.766 | 0.690 | ❌ AUROC < 0.80 |
| TR tezligi ≥ 3.2 m/s | 375 | 0.760 | 0.665 | ❌ AUROC < 0.80 |
| Chap qorincha devori ≥ 13 mm | 1061 | 0.742 | 0.672 | ❌ AUROC, bo'lim (protsedura 0.65) |
| Perikard suyuqligi | 69 | 0.719 | 0.642 | ❌ AUROC, CI |
| Aorta regurgitatsiyasi | 66 | 0.717 | 0.688 | ❌ hamma mezon |
| O'pka arteriyasi regurgitatsiyasi | 20 | 0.776 | 0.688 | ❌ musbat < 30 |
| (LVEF ≤ 45%, yordamchi) | 962 | 0.886 | 0.782 | alohida modelda: `ecg/low_ef.py` |

Eng muhim halol topilma: **aorta stenozi** uchun model 0.825 berdi, lekin faqat yosh va jins bilan 0.844. Ya'ni model AS'ni «yoshi katta bemor» orqali taxmin qilgan, EKG'dan qo'shimcha ma'lumot olmagan. Shuning uchun yoqilmadi.

## Ulanish tekshiruvi
ONNX inference yo'li (`StructuralFromECG.analyze`), test'dan 2 000 EKG (sifat tekshiruvidan o'tganlari): SHD 0.797, MR 0.816, TR 0.822, RV 0.887. Natijalar o'qitishdagiga mos.
Yoqilgan 4 yorliqdan biri noaniq zonada bo'lsa va hech biri musbat bo'lmasa, umumiy javob abstain. Bu xavfsiz tomonga qilingan, lekin abstain ulushini oshiradi.

## Klinikada
`/episodes/{eid}/ecg` javobida `structural` bo'limi: musbat → «ExoKG qiling: … ehtimoli» (tashxis emas); manfiy → «belgi topilmadi» (kasallik yo'qligini kafolatlamaydi). Yosh < 18 → abstain.

## Cheklovlar
Bitta markaz (AQSh), kattalar; mahalliy aholida tashqi tekshiruv yo'q. Klapan kasalliklari bo'yicha EKG faqat skrining signali, darajani ExoKG belgilaydi.

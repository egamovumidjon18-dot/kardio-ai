# Ritm modeli (Chapman'da o'qitilgan, PTB-XL'da tashqi tekshirilgan): bitta mezon bo'yicha O'TMADI

Sana: 2026-10-31. Skript: `research/train_rhythm.py`. Karta: `weights/ecg_rhythm/model_card.json` (ONNX git'da emas).

## Nima uchun
PTB-XL'da o'qitilgan AFIB modeli Chapman'da SVT va bo'lmachalar titrashini AFIB deb belgilagan edi (o'ziga xoslik 0.844, [ecg_chapman_external.md](ecg_chapman_external.md)). Bu model shu ritmlarni alohida sinf qilib o'rganadi: SR, SBRAD, STACH, AFIB, AFL (titrash), SVT.
O'qitish Chapman–Shaoxing'da (CC0, 10 646 EKG, 85/15), tashqi tekshiruv PTB-XL'da (Germaniya, 20 484 EKG; PACE/BIGU/TRIGU chiqarilgan). PTB-XL o'qitishda ishlatilmagan.

## Oldindan belgilangan mezonlar va natija (PTB-XL, bir marta)
| Mezon | Talab | Natija | |
|---|---|---|---|
| AFIB AUROC | ≥ 0.95 | **0.988** (0.985–0.991) | ✅ |
| AFIB sezgirligi (Chapman val chegarasida) | ≥ 0.85 | **0.843** | ❌ (chegaradan sal past) |
| AFIB o'ziga xosligi | ≥ 0.92 | **0.993** | ✅ |
| Titrash + SVT + sinus taxikardiyasi «AFIB» deb belgilangani | ≤ 25% | **0.7%** (895 tadan 6) | ✅ |
| Har bir sinf AUROC (≥ 30 holat) | ≥ 0.85 | 0.920–0.993 | ✅ |

**Xulosa: o'tmadi** (sezgirlik 0.843 < 0.85). Chegara natijadan keyin o'zgartirilmadi, model dasturga ulanmadi.

## Muhim ijobiy topilma
Tez ritmlar bilan chalkashlik deyarli yo'qoldi: PTB-XL'dagi 56 titrash va 34 SVT'dan hech biri AFIB deb belgilanmadi (eski modelda Chapman'da 978 ta shunday xato bor edi). AFIB o'tkazib yuborilganlarning ko'pi titrash (163) yoki SVT (52) deb belgilangan. Ya'ni bu holatlar «normal» emas, baribir «aritmiya» deb chiqqan.
Sinus ritmining 17% i sinus bradikardiyasi deb belgilangan: ikki to'plamda yorliq qo'yish me'yori har xil (Chapman'da SB juda ko'p). Bu klinik xavfli xato emas, lekin kalibrlash kerakligini ko'rsatadi.

## Keyingi qadam (ochiq)
Ikki model bir-birini to'ldiradi: PTB-XL modeli AFIB'ni sezgir topadi, Chapman modeli tez ritmlarni ajratadi. Ularning birikmasini (masalan, «AFIB, lekin ritm modeli titrash/SVT deydi → aniqlashtirish») **uchinchi mustaqil to'plamda** oldindan yozilgan mezonlar bilan tekshirish kerak. Masalan, PhysioNet Challenge 2021'ning ochiq to'plamlari (Georgia, CPSC 2018) mos keladi. Ikkala mavjud to'plam o'qitishda ishlatilgani uchun ular bu tekshiruvga yaramaydi.

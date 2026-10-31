# AFIB modeli + ritm modeli birikmasi: uchinchi mustaqil to'plam (Georgia, AQSh). O'TMADI

Sana: 2026-10-31. Skript: `research/external_georgia_rhythm.py` (mezonlar natijadan oldin, 25efda0 commit'ida yozilgan). Xom natija: [ecg_georgia_combined.json](ecg_georgia_combined.json).

## Nima tekshirildi
Ma'lumot: Georgia 12-Lead ECG Challenge (Emory, AQSh), PhysioNet Challenge 2021 v1.0.3, CC BY 4.0, 10 344 EKG. Ikkala model ham bu to'plamni ko'rmagan.
- Ritm yorlig'i bor va kardiostimulyatorsiz 5 772 EKG baholandi: SR 2 083, SB 1 656, ST 1 239, AFIB 570, titrash 171, SVT 53.
- 4 572 tasida ritm kodi yo'q yoki stimulyator bor edi, ular chiqarildi.

Birikma qoidasi: AFIB modeli «AFIB» desa, ritm modeli esa «titrash / SVT / sinus taxikardiyasi» desa, javob «tez supraventrikulyar ritm, shifokor aniqlashtiradi» bo'ladi.

## Natija
| Ko'rsatkich | Talab | AFIB modeli yolg'iz | Birikma | |
|---|---|---|---|---|
| AFIB sezgirligi | ≥ 0.85 | 0.856 | **0.710** | ❌ |
| AFIB o'ziga xosligi | ≥ 0.92 | 0.896 | **0.977** | ✅ |
| Tez ritmlar «AFIB» deb belgilangani | ≤ 25% | 31.3% | **3.6%** | ✅ |
| AFIB'da aritmiya bayrog'i (AFIB yoki «tez ritm») | ≥ 0.95 | — | 0.856 | ❌ |
| O'ziga xoslik yutug'i | ≥ +0.02 | — | +0.080 | ✅ |
| Sezgirlik yo'qotishi | ≤ 0.05 | — | 0.146 | ❌ |
| Abstain | ≤ 20% | — | 0.9% | ✅ |

**Xulosa: o'tmadi. Birikma dasturga ulanmadi.** Chegaralar natijadan keyin o'zgartirilmadi.

## Nimani o'rgandik
1. Ritm modeli yolg'on AFIB'larni kamaytiradi: titrash 131 → 24, SVT 46 → 11, sinus taxikardiyasi 279 → 17. Lekin u haqiqiy AFIB'ning 82 tasini (14.6%) ham «tez ritm»ga o'tkazib yuboradi. Bu xavfli emas, chunki bayroq saqlanadi, lekin aniq AFIB tashxisi yo'qoladi.
2. Hozirgi AFIB modelining **o'zi** ham Georgia'da zaifroq:
   - AUROC 0.930 (0.917–0.942), PTB-XL'da 0.981 edi;
   - sezgirlik 0.856, Chapman'da 0.996 edi.

   AFIB'ning 81 tasini u umuman belgilamagan. Bu holatlar birikmada ham bayroqsiz qoladi, shuning uchun 4-mezon o'tmadi.
3. Uch mamlakatda uch xil natija chiqdi. Demak, bitta to'plamda o'qitilgan model boshqa shifoxonaga ko'chirilganda sezilarli yomonlashadi. Ishonchli AFIB modeli uchun bir nechta manbada birga o'qitish kerak, masalan PTB-XL + Chapman + Ningbo. Keyin u boshqa, to'rtinchi to'plamda tekshiriladi: CPSC 2018 yoki Georgia'ning bu safar ishlatilmagan qismi emas, chunki u endi ko'rilgan.

## Dasturdagi holat
O'zgarish yo'q: AFIB modeli avvalgidek ulangan. Uning matnida allaqachon «titrash yoki SVT ham bo'lishi mumkin — shifokor EKGni tasdiqlaydi» degan ogohlantirish bor. Birikma ulanmadi.

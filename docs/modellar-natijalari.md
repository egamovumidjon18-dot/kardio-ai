# CardioPath AI: barcha AI modellari va ularning halol natijalari (2026-10-31)

Bu jadval maqola va taqdimot uchun yagona manba. Har bir raqam o'z hisobotiga bog'langan. «Ulangan» degani: model dasturda ishlaydi, lekin baribir faqat yordamchi, qaror shifokorniki.

| Model | O'qitish ma'lumoti | Tekshiruv | Asosiy natija | Holat | Hisobot |
|---|---|---|---|---|---|
| Yurak tovushi (PCG): shovqin bor/yo'q (bolalar) | CirCor DigiScope (ODC-By) | ichki test, bemor darajasida | test AUROC 0.958, abstain 3.8%, qaror qilinganda sezgirlik 0.913 / o'ziga xoslik 0.923 | ✅ ulangan | `weights/pcg/model_card.json` |
| PCG: ZCHSound'ga moslashtirish | CirCor + ZCHSound | yozuv-blok nazorati | natija yozuv sharoitiga bog'liq ekani topildi | ❌ rad etilgan | `docs/experiments/zchsound_adaptation.md` |
| EKG: AFIB + 5 toifa | PTB-XL (CC-BY) | ichki test (rasmiy 10-fold, bemor darajasida) | AFIB test AUROC 0.981 (0.963–0.992), sezgirlik 0.941, o'ziga xoslik 0.971; MI 0.934, STTC 0.934, CD 0.920, HYP 0.842 | ✅ ulangan | `weights/ecg/model_card.json` |
| EKG AFIB: tashqi tekshiruv | — | Chapman–Shaoxing (Xitoy, 10 646) | AUROC 0.950, sezgirlik 0.996, o'ziga xoslik 0.844 (talab 0.85) | ⚠️ mezondan o'tmadi; matnga «titrash/SVT bo'lishi mumkin» qo'shildi | `docs/experiments/ecg_chapman_external.md` |
| EKG ritm (6 sinf) | Chapman–Shaoxing (CC0) | PTB-XL (tashqi, 20 484) | AFIB AUROC 0.988, o'ziga xoslik 0.993, sezgirlik 0.843 (talab 0.85) | ❌ ulanmagan | `docs/experiments/ecg_rhythm_chapman.md` |
| EKG AFIB: 2-tashqi tekshiruv | — | Georgia (AQSh, 5 772) | AUROC 0.930 (0.917–0.942), sezgirlik 0.856, o'ziga xoslik 0.896 | ℹ️ ma'lumot uchun | `docs/experiments/ecg_georgia_combined.md` |
| Ko'p manbali AFIB (PTB-XL + Chapman + Ningbo) | Challenge 2021 (CC BY) | CPSC 2018 + Georgia (tashqi) | CPSC AUROC 0.981; Georgia AUROC 0.933, sezgirlik 0.798. Ningbo'da AFIB yorlig'i 0 ta, titrash 7 615 ta (yorliq xatosi gumoni) | ❌ ulanmagan | `docs/experiments/ecg_afib_multi.md` |
| AFIB + ritm modeli birikmasi | — | Georgia (uchinchi mustaqil) | o'ziga xoslik 0.896 → 0.977, lekin sezgirlik 0.856 → 0.710 | ❌ ulanmagan | `docs/experiments/ecg_georgia_combined.md` |
| AI-EKG past EF (LVEF ≤ 45%) | EchoNext (PhysioNet, tadqiqot) | rasmiy test, bemor kesishmasi 0 | AUROC 0.886 (0.874–0.899), jadval bazasi 0.782 | ✅ ulangan | `docs/experiments/ecg_lowef_echonext.md` |
| AI-EKG tuzilmaviy kasalliklar | EchoNext | rasmiy test | RV disfunksiya 0.874, TR 0.818, SHD 0.815, MR 0.813 | ✅ 4 yorliq ulangan | `docs/experiments/ecg_shd_echonext.md` |
| AI-EKG: aorta stenozi | EchoNext | rasmiy test | 0.825, lekin yosh/jins bazasi 0.844 | ❌ rad etilgan | `docs/experiments/ecg_shd_echonext.md` |
| AI-EKG: PH, TR tezligi, devor qalinligi, perikard suyuqligi, AR, PR | EchoNext | rasmiy test | 0.72–0.78 | ❌ rad etilgan | `docs/experiments/ecg_shd_echonext.md` |
| Koronar angiografiya (stenoz nomzodlari) | ARCADE (CC-BY) | ichki test (300 rasm) | lezyon recall 0.892, precision 0.497, Dice 0.538 | ✅ ulangan | `weights/angio/model_card.json` |
| ExoKG videodan EF | EchoNet-Dynamic (NeuroSon-AI og'irligi) | NeuroSon-AI loyihasida | bu loyihada qayta o'lchanmagan | ✅ ulangan | `adapters/echo_ef.py` |
| Yara rasmi: infeksiya xavfi | SurgWound (CC BY-SA) | 5-fold CV | AUROC 0.68; 90% sezgirlikda o'ziga xoslik 21% | ❌ rad etilgan | `docs/experiments/wound_surgwound.md` |
| AKI ML | MIMIC-IV kerak | — | — | ⏳ akkreditatsiya kutilmoqda | `risk/aki.py` |

## Uslubiy tamoyillar (hamma modelga bir xil)
1. Qabul mezonlari natijani ko'rishdan **oldin** yoziladi va keyin o'zgartirilmaydi.
2. Bemor darajasida bo'linish, kesishma avtomatik tekshiriladi.
3. AI-EKG modellari **oddiy bazaga** (yosh, jins, intervallar) qarshi solishtiriladi. Model undan yaxshi bo'lmasa, ulanmaydi (masalan, aorta stenozi). PCG, angiografiya va ExoKG uchun bunday baza hali qo'llanmagan.
4. Shortcut tekshiruvi: bo'lim (shoshilinch, statsionar), yozuv bloki, manba bo'yicha alohida natija.
5. Inference yo'li (ONNX + dasturdagi preprocessing) test ma'lumotida qayta o'lchanadi.
6. Noaniq holatda model javob bermaydi (abstain) va AI hech qachon xavfni pasaytirmaydi.
7. Salbiy natijalar ham hujjatlanadi: yuqoridagi jadvalda ❌ va ⚠️ belgilari.

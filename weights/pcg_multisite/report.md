> ## ⚠ RAD ETILDI (2026-10-30): bu model qabul qilinmagan
>
> Quyidagi jadvalda oldindan belgilangan mezonlar «bajarildi» deb chiqqan, lekin tajribadan **keyin** topilgan holat mezonni bekor qiladi: ZCHSound'da yozuvlar tashxis bo'yicha ketma-ket yig'ilgan (normal ZCH0001–0533, ASD 0534–0652, PDA 0653–0684, PFO 0685–0754, VSD 0755–0941; fayl raqami bilan tashxis AUROC 1.0). Salbiy nazorat (`research/control_zch_batch.py`): faqat sog' bolalar ichida model «erta vs kech yozilgan»ni AUROC ≈0.67 bilan ajratdi (faqat yosh bilan 0.55). Demak, ZCHSound testidagi AUROC 0.97 yozuv-blok izidan kelgan bo'lishi mumkin, B1 va B2 mezonlari isbot emas.
>
> Qo'shimcha zarar ham bor: CirCor testida AUROC 0.960 → 0.937, bitta chegarada abstain ulushi 9.8% → 20.5% (bu mezonlarda yo'q edi). **Qaror:** mahsulot modeli CirCor'da o'qitilgan `weights/pcg` bo'lib qoladi. `pcg_multisite` faqat tajriba artefakti; uning kartasi ataylab `model_card.experimental.json` deb nomlangan, shuning uchun dastur uni o'zi yuklamaydi.

# Ko'p manbali PCG modeli: CirCor + ZCHSound

Urug' 42, 40 epoch. Uchala model bir xil kod bilan o'qitilgan; AUROC — bola darajasida bootstrap 95% CI.

| Model | CirCor testi (n, shovqinli) AUROC | ZCHSound testi (n, nuqsonli) AUROC |
|---|---|---|
| circor_only | 0.960 (0.908–0.992) (132, 27) | 0.681 (0.583–0.769) (197, 75) |
| zch_only | 0.805 (0.707–0.890) (132, 27) | 0.970 (0.939–0.990) (197, 75) |
| multisite | 0.937 (0.868–0.982) (132, 27) | 0.971 (0.949–0.988) (197, 75) |

## Bitta chegarada qaror (chegara birlashgan validatsiyada tanlangan: sezgirlik ≥95%, spetsifiklik ≥90%)

| Model | Sinov | Sezgirlik | Spetsifiklik | Abstain |
|---|---|---|---|---|
| circor_only | circor | 0.885 (0.739–1.000) | 0.925 (0.870–0.969) | 0.098 |
| circor_only | zch | 0.892 (0.817–0.957) | 0.076 (0.033–0.130) | 0.020 |
| zch_only | circor | 1.000 (1.000–1.000) | 0.000 (0.000–0.000) | 0.000 |
| zch_only | zch | 0.892 (0.813–0.952) | 0.965 (0.931–0.992) | 0.041 |
| multisite | circor | 0.952 (0.842–1.000) | 0.917 (0.849–0.967) | 0.205 |
| multisite | zch | 0.903 (0.829–0.965) | 0.923 (0.872–0.967) | 0.041 |

## ZCHSound testi: yosh va tashxis bo'yicha

**circor_only** — «faqat yosh» chizig'i AUROC 0.760; yosh guruhlari ichida: bola (≥1 yosh): n=144 (nuqsonli 37) AUROC 0.625; go'dak (<1 yosh): n=53 (nuqsonli 38) AUROC 0.674; belgilanganlar ulushi: ASD 0.808, NORMAL 0.926, PDA 0.875, VSD 0.951

**multisite** — «faqat yosh» chizig'i AUROC 0.760; yosh guruhlari ichida: bola (≥1 yosh): n=144 (nuqsonli 37) AUROC 0.944; go'dak (<1 yosh): n=53 (nuqsonli 38) AUROC 0.996; belgilanganlar ulushi: ASD 0.731, NORMAL 0.074, PDA 0.750, VSD 0.976

## Oldindan belgilangan qabul mezoni

- A (CirCor'da 0.03 dan ko'p yomonlashmaslik): **bajarildi**
- B1 (ZCHSound'da kamida +0.10): **bajarildi**
- B2 («faqat yosh»dan kamida +0.05 yuqori): **bajarildi**
- Xulosa: **QABUL QILINDI**

Cheklov: ZCHSound sinov to'plami o'qitish to'plami bilan BIR MANBADAN (boshqa bolalar, lekin bir shifoxona). Bu «uchinchi, ko'rilmagan klinika»da ishlashini isbotlamaydi; haqiqiy tashqi tekshiruv uchun mahalliy yozuvlar kerak.
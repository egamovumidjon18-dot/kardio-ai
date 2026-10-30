# Tajriba: mahalliy ma'lumot bilan moslashtirish (ZCHSound "yangi klinika" sifatida)

Qat'iy test: 315 bola (TYN 119: ASD/VSD/PDA; PFO va neonatlar chiqarilgan). Fine-tuning havzasi: 474 bola. 15 epoch, lr 0.0003.

| Mahalliy bolalar soni (N) | AUROC (o'rtacha ± SD) | Sezgirlik @ 80% spetsifiklik | Takrorlar |
|---|---|---|---|
| 0 (moslashtirishsiz) | 0.748 ± 0.000 | 0.630 ± 0.000 | 1 |
| 50 | 0.968 ± 0.007 | 0.956 ± 0.008 | 5 |
| 100 | 0.968 ± 0.005 | 0.953 ± 0.019 | 5 |
| 200 | 0.976 ± 0.004 | 0.960 ± 0.013 | 5 |
| 474 | 0.982 ± 0.003 | 0.975 ± 0.007 | 3 |

Izoh: 'Sezgirlik @ 80% spetsifiklik' chegarasi test to'plamidagi ROC egri chizig'idan olingan (egri chiziq nuqtasi, mustaqil chegara emas).
## Shortcut (yashirin omil) tekshiruvi

| Tekshiruv | Natija |
|---|---|
| Median yosh: TYN / normal | 395 kun / 1215 kun |
| **Faqat yosh** bilan AUROC | 0.747 — kuchli yashirin omil (moslashtirishsiz model ham 0.748 edi) |
| Ovoz balandligi (RMS) / davomiylik AUROC | 0.52 / 0.58 — bashorat qilmaydi |
| N=50 model, go'daklar (<1 yosh, n=78) | AUROC 0.986 |
| N=50 model, ≥1 yosh (n=237) | AUROC 0.966 |
| N=50 model, 1–6 yosh (n=182) | AUROC 0.970 |
| N=50 model: VSD / ASD / PDA vs normal | 0.996 / 0.943 / 0.969 |

**Xulosa:** moslashtirilgan model yosh guruhlari ichida ham yuqori natija beradi, ya'ni u yoshni emas, yurak tovushini o'rganadi. Lekin yozuv sharoiti (bo'lim, xona, qurilma) TYN va normal guruhlarda farq qilgan bo'lishi mumkin va buni bu ma'lumotdan tekshirib bo'lmaydi.

**Mahalliy ma'lumot yig'ish uchun amaliy tavsiya:**
- **Boshlang'ich nuqta:** ~50–100 bola (TYN + sog'lar), ExoKG bilan tasdiqlangan.
- **Bitta qurilma va bitta protokol:** TYN'li va sog' bolalar bir xil stetoskop bilan, bir xil xona sharoitida yozilsin, aks holda model qurilma yoki xonani o'rganib qoladi.
- **Yoshlar mos bo'lsin:** sog' bolalar TYN'lilar bilan bir xil yosh oralig'idan olinsin.
- **Mustaqil test:** baholash uchun alohida, keyinroq yig'ilgan bolalar to'plami qoldirilsin.

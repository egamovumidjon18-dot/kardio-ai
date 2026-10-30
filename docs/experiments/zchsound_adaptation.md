> ## ⚠ TUZATISH (2026-10-30): bu tajribaning xulosalariga ISHONMANG
>
> ZCHSound'da yozuvlar **tashxis bo'yicha ketma-ket** yig'ilgan: normal ZCH0001–0533, ASD 0534–0652, PDA 0653–0684, PFO 0685–0754, VSD 0755–0941. Fayl raqami bilan tashxis AUROC **1.0** (normaldan nuqsonlilarga faqat bitta o'tish). Salbiy nazorat (`research/control_zch_batch.py`): **faqat sog' bolalar** ichida model «erta yoki kech yozilgan» yozuvni AUROC **≈0.67** bilan ajratdi (faqat yosh bilan 0.55): yozuvlarda kun/sharoit izi bor. Normal va nuqsonli bloklar orasidagi vaqt masofasi kattaroq, shuning uchun iz u yerda kuchliroq bo'lishi mumkin.
>
> Demak, quyidagi AUROC (0.97–0.98) qisman yoki to'liq shu izdan kelgan bo'lishi mumkin va **«50 ta mahalliy bola yetarli» degan xulosa dalilsiz**. Kerakli mahalliy ma'lumot hajmi hozircha NOMA'LUM. Pastdagi jadvallar tarixiy yozuv sifatida qoldirilgan; «yosh guruhlari ichida ham yuqori, demak tovushni o'rganadi» degan xulosa bekor qilingan.

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

**Xulosa (BEKOR QILINGAN, yuqoridagi tuzatishga qarang):** moslashtirilgan model yosh guruhlari ichida ham yuqori natija berdi, lekin bu uning tovushni o'rganganini isbotlamaydi: yozuv-blok izi tekshirilmagan edi va keyin topildi.

**Mahalliy ma'lumot yig'ish uchun amaliy tavsiya:**
- **Kerakli hajm:** noma'lum (bu tajriba buni aniqlay olmaydi). Quyidagi qoidalar esa qat'iy:
- **Bitta qurilma va bitta protokol:** TYN'li va sog' bolalar bir xil stetoskop bilan, bir xil xona sharoitida yozilsin, aks holda model qurilma yoki xonani o'rganib qoladi.
- **ARALASH TARTIBDA yozing:** sog' va kasal bolalarni bir xil kunlarda, navbatma-navbat yozing. Avval hamma sog'larni, keyin hamma kasallarni yozmang (ZCHSound'dagi xato shu edi). Eksport buyrug'i (`research.export_local`) tartib va qurilma aralashuvini tekshirib, ogohlantiradi.
- **Yoshlar mos bo'lsin:** sog' bolalar TYN'lilar bilan bir xil yosh oralig'idan olinsin.
- **Mustaqil test:** baholash uchun alohida, keyinroq yig'ilgan bolalar to'plami qoldirilsin.

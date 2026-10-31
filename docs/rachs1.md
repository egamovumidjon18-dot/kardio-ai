# RACHS-1: bolalar yurak operatsiyalari xavf toifasi

Sana: 2026-10-31. Kod: `risk/rachs1.py`. API:
- `GET /rachs1/procedures`
- `POST /episodes/{eid}/rachs1`

Testlar: `tests/test_rachs1.py`.

## Nima
RACHS-1 tug'ma yurak nuqsoni operatsiyasini 6 ta xavf toifasiga ajratadi. Manba: Jenkins KJ et al., *J Thorac Cardiovasc Surg* 2002;123:110–118. Bu AI emas, nashr qilingan qoida. U kattalardagi EuroSCORE II ning bolalardagi o'rinbosari.

| Toifa | Asl kogortada o'lim (2002) | Zamonaviy markazlar (CHSS, 2006) | Platformadagi xavf darajasi |
|---|---|---|---|
| 1 | 0.4% | 0.7% | past |
| 2 | 3.8% | 0.9% | o'rta |
| 3 | 8.5% | 2.7% | yuqori |
| 4 | 19.4% | 7.7% | juda yuqori |
| 5 | holat kam | — | juda yuqori |
| 6 | 47.7% | 17.2% | juda yuqori |

Foizlar bemorning shaxsiy xavfi emas, ular toifaning nisbiy og'irligini ko'rsatadi. Platforma buni har bir natijada yozadi.

## Qoidalar
- Ba'zi operatsiyalarning toifasi yoshga bog'liq: ≤ 30 kun yoki > 30 kun. Masalan, koarktatsiyani tuzatish yoki to'liq anomal o'pka venalari drenajini tuzatish.
- Bir nechta operatsiya bo'lsa, eng yuqori toifa olinadi.
- Quyidagi hollarda model javob bermaydi (abstain), toifani kardioxirurg belgilaydi:
  - ro'yxatda yo'q operatsiya;
  - yurak ko'chirib o'tkazish;
  - chala tug'ilgan chaqaloqda faqat arterial yo'lni yopish;
  - 30 kungacha bo'lgan chaqaloqda arterial yo'lni yopish (nashrda toifa berilmagan);
  - 18 yoshdan katta bemor (unda EuroSCORE II ishlatiladi).
- Natija Heart Team protokolining «Xavf baholash» jadvaliga chiqadi.

## Cheklov
- Operatsiyalar ro'yxati nashr ilovasi asosida yozilgan. Klinik ishlatishdan oldin kardioxirurg uni asl jadval bilan bir marta solishtirib chiqishi kerak.
- RACHS-1 dan keyin aniqroq tizimlar chiqqan: STAT (2009) va Aristotle. Ular yuzlab operatsiya kodlarini talab qiladi va keyingi bosqich bo'lishi mumkin.

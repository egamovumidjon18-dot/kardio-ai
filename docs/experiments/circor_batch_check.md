# CirCor: yozuv-sharoit (kampaniya/vaqt) izi tekshiruvi

ZCHSound'da topilgan xato (tashxis bo'yicha ketma-ket yozuv) CirCor'da bormi? `research/control_circor_batch.py`.

## 1. Metama'lumot

| Belgi | Murmur bilan AUROC (0.5 = bog'lanish yo'q) |
|---|---|
| Faqat kampaniya (CC2014/CC2015) | 0.541 |
| Yosh toifasi | 0.507 |
| Bo'y | 0.550 |
| Vazn | 0.564 |
| Bemor raqami, CC2014 (n=385, murmur ulushi 0.17) | 0.619; raqam kvartillari bo'yicha murmur ulushi [0.24, 0.21, 0.14, 0.1] |
| Bemor raqami, CC2015 (n=557, murmur ulushi 0.23) | 0.622; raqam kvartillari bo'yicha murmur ulushi [0.33, 0.23, 0.19, 0.16] |

Bayt-ma-bayt takror yozuv: 0. Ikki ID li bolalar: 70 (hammasi ikkala kampaniyada); ularda murmur belgisi mos kelmagan: 15 / 70 (belgi shovqini).

## 2. Salbiy nazorat: murmur YO'Q bolalar ichida audiodan kampaniyani ajratish

AUROC (urug'lar bo'yicha): 0.838, 0.859, 0.798; o'rtacha **0.832** (0.5 = iz yo'q). Solishtirish uchun ZCHSound'da erta-vs-kech: 0.669.

## 3. Kampaniyalararo tekshiruv

| O'qitilgan → sinalgan | AUROC (95% CI) | Sezgirlik | Spetsifiklik |
|---|---|---|---|
| CC2014->CC2015: ichki (xuddi shu kampaniya, ko'rilmagan bolalar) (n=44, murmur 4) | 0.919 (0.772–1.000) | 0.667 (0.000–1.000) | 0.897 (0.784–0.975) |
| CC2014->CC2015: TASHQI (CC2015) (n=445, murmur 92) | 0.903 (0.858–0.943) | 0.795 (0.705–0.876) | 0.922 (0.890–0.950) |
| CC2015->CC2014: ichki (xuddi shu kampaniya, ko'rilmagan bolalar) (n=66, murmur 14) | 0.880 (0.725–0.992) | 0.857 (0.636–1.000) | 0.900 (0.800–0.976) |
| CC2015->CC2014: TASHQI (CC2014) (n=301, murmur 42) | 0.907 (0.847–0.952) | 0.914 (0.800–1.000) | 0.820 (0.769–0.871) |
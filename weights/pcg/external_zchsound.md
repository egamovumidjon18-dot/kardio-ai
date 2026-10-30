# Tashqi validatsiya — ZCHSound (Xitoy, haqiqiy TYN tashxislari)

Model: `pcg_murmur_cnn` v2026.10.30, CirCor'da o'qitilgan, **qayta o'qitishsiz**. Chegaralar: {'murmur_low': 0.318729, 'murmur_high': 0.318729, 'window_agreement': 0.6}

## Toza to'plam (941 bola)

| Taqqoslash | n (TYN) | AUROC (95% CI) | Sezgirlik (95% CI) | Spetsifiklik (95% CI) | Abstain |
|---|---|---|---|---|---|
| Barcha TYN vs normal | 941 (408) | 0.676 (0.639–0.715) | 0.604 (0.556–0.656) | 0.687 (0.646–0.732) | 0.117 |
| TYN (PFO'siz) vs normal | 871 (338) | 0.737 (0.696–0.776) | 0.696 (0.643–0.749) | 0.687 (0.644–0.732) | 0.121 |

| Tashxis | n | Abstain | 'Shovqin bor' deb belgilangan | Median p |
|---|---|---|---|---|
| ASD | 119 | 14 | 49 (0.467) | 0.297 |
| NORMAL | 533 | 66 | 146 (0.313) | 0.150 |
| PDA | 32 | 2 | 19 (0.633) | 0.716 |
| PFO | 70 | 5 | 12 (0.185) | 0.071 |
| VSD | 187 | 23 | 140 (0.854) | 0.991 |

| Yosh | n (TYN) | AUROC | Sezgirlik | Spetsifiklik | Abstain |
|---|---|---|---|---|---|
| bola (≥1 yosh) | 673 (200) | 0.714 | 0.685 | 0.682 | 0.119 |
| go'dak (<1 yosh) | 259 (199) | 0.665 | 0.531 | 0.727 | 0.112 |
| neonat (≤28 kun) | 9 (9) | — | 0.375 | — | 0.111 |

Abstain sabablari: oynalar kelishmadi: 31, sifatli yozuv yo'q: 79

## Shovqinli to'plam (318 bola)

| Taqqoslash | n (TYN) | AUROC (95% CI) | Sezgirlik (95% CI) | Spetsifiklik (95% CI) | Abstain |
|---|---|---|---|---|---|
| Barcha TYN vs normal | 318 (158) | 0.568 (0.510–0.627) | 0.280 (0.205–0.359) | 0.824 (0.758–0.883) | 0.069 |
| TYN (PFO'siz) vs normal | 283 (123) | 0.521 (0.448–0.587) | 0.228 (0.153–0.307) | 0.824 (0.755–0.880) | 0.057 |

| Tashxis | n | Abstain | 'Shovqin bor' deb belgilangan | Median p |
|---|---|---|---|---|
| ASD | 102 | 7 | 20 (0.211) | 0.090 |
| NORMAL | 160 | 7 | 27 (0.176) | 0.105 |
| PDA | 7 | 1 | 1 (0.167) | 0.112 |
| PFO | 35 | 6 | 14 (0.483) | 0.356 |
| VSD | 14 | 1 | 5 (0.385) | 0.253 |

| Yosh | n (TYN) | AUROC | Sezgirlik | Spetsifiklik | Abstain |
|---|---|---|---|---|---|
| neonat (≤28 kun) | 318 (158) | 0.568 | 0.280 | 0.824 | 0.069 |

Abstain sabablari: oynalar kelishmadi: 22

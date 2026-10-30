# PCG modeli — test to'plami (production yo'li, bola darajasida bootstrap 95% CI)

Model: `pcg_murmur_cnn` v2026.10.30 · chegaralar: {'murmur_low': 0.318729, 'murmur_high': 0.318729, 'window_agreement': 0.6}

| Metrika | Qiymat (95% CI) |
|---|---|
| auroc | 0.958 (0.909–0.990) |
| sensitivity | 0.913 (0.778–1.000) |
| specificity | 0.923 (0.870–0.971) |
| ppv | 0.724 (0.552–0.882) |
| npv | 0.980 (0.950–1.000) |
| abstain_rate | 0.038 (0.008–0.071) |

Bemorlar: 132 (shovqin bor: 27); qaror qilinganlar: TP 21, FN 2, TN 96, FP 8

## Kichik guruhlar
| Guruh | n | AUROC | Sezgirlik | Spetsifiklik | Abstain |
|---|---|---|---|---|---|
| Age=Adolescent | 14 | 1.000 | 1.000 | 1.000 | 0.000 |
| Age=Child | 85 | 0.940 | 0.929 | 0.925 | 0.047 |
| Age=Infant | 18 | 0.985 | 0.750 | 1.000 | 0.056 |
| Age=nan | 15 | 1.000 | 1.000 | 0.786 | 0.000 |
| Campaign=CC2014 | 59 | 1.000 | 1.000 | 0.959 | 0.034 |
| Campaign=CC2015 | 73 | 0.925 | 0.867 | 0.891 | 0.041 |

## Abstain sabablari
- oynalar kelishmadi: 6
- sifatli yozuv yo'q: 1
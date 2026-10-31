# Uchidan-uchiga tekshiruv: modellar dastur orqali (haqiqiy og'irliklar)

Sana: 2026-11-01. Skript: `research/e2e_check.py`. Har sinfdan 15 ta namuna, HTTP API orqali.

| Modul | Ma'lumot | Musbat: topildi | Manfiy: to'g'ri «yo'q» | Javob bermadi | Xato |
|---|---|---|---|---|---|
| Yurak tovushi: shovqin bor/yo'q | CirCor test (bemor darajasida) | 12/12 | 15/15 | 3 | 0 |
| EKG: bo'lmachalar fibrillyatsiyasi | PTB-XL fold 10 (500 Hz, mV) | 13/14 | 15/15 | 1 | 0 |
| AI-EKG: past EF (≤45%) | EchoNext test (250 Hz, oldindan standartlashtirilgan) | 7/7 | 5/8 | 15 | 0 |
| AI-EKG: tuzilmaviy kasallik | EchoNext test, xuddi shu EKG'lar | 10/10 | 1/3 | 17 | 0 |
| Angiografiya: stenoz nomzodi | ARCADE test (stenozli kadrlar) | 30/30 | — | 0 | 0 |
| MNO qog'ozi: raqamni o'qish | sun'iy laboratoriya rasmi (qiymat ma'lum) | 4/4 | — | 0 | 0 |

Shadow model ishga tushgan EKG'lar: 60. Umumiy vaqt: 119.1 s.

## Izohlar

- **MNO qog'ozi:** birinchi ishga tushirishda 4 tadan 0 tasi o'qildi. Sabab: «MNO (INR): 3.8» kabi qavsli yozuvni dastur tanimas edi. Tuzatildi, endi 4 tadan 4 tasi o'qiladi. Qog'ozda ikki xil raqam bo'lsa, dastur taxmin qilmaydi va javob bermaydi.
- **AI-EKG (past EF va tuzilmaviy kasallik):** «javob bermadi» ulushi yuqori. Shu sababli 400 ta test EKG'si alohida tekshirildi:
  - 27% holatda «signal sifati yomon» degan javob chiqdi. Sabab EchoNext to'plamining formatida: signallar millivoltda emas, oldindan normallashtirilgan, sifat tekshiruvi esa millivolt kutadi. EKG apparatidan olingan haqiqiy faylda bu muammo bo'lmaydi;
  - 16% holatda model ataylab «aniq emas» dedi;
  - javob bergan holatlarda sezgirlik 22/26 (85%), o'ziga xoslik 184/202 (91%).
- **ExoKG videodan EF:** haqiqiy ExoKG videosi qo'lda yo'q, shuning uchun bu modul faqat sun'iy videoda ishga tushishi bo'yicha tekshirildi, aniqligi tekshirilmadi.
- Bu natijalar asosiy validatsiyalar o'rnini bosmaydi (`docs/modellar-natijalari.md`). Bu tekshiruv modellar dasturga to'g'ri ulanganini va kutilgan javobni berishini ko'rsatadi.

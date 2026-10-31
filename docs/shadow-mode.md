# Shadow rejimi: yangi modelni haqiqiy EKG'larda xavfsiz sinash

Sana: 2026-10-31. Kod:
- `core/shadow.py`
- `api/shadow_routes.py`
- `api/static/shadow.html`
- testlar: `tests/test_shadow.py`

## Nima uchun
Ochiq 12 tarmoqli EKG to'plamlari tugadi ([ecg_afib_multi2.md](experiments/ecg_afib_multi2.md)). Yangi modelni halol tekshirishning yagona yo'li — u hech qachon ko'rmagan, mahalliy, haqiqiy EKG'lar.

## Qanday ishlaydi
1. Shifokor odatdagidek EKG yuklaydi. Ulangan model javob beradi, hammasi avvalgidek.
2. Shu paytning o'zida shadow model, hozir `ecg_afib_multi2`, shu EKG'ni jim tahlil qiladi. Uning javobi faqat `shadow_runs` jadvaliga yoziladi. U quyidagilarning birortasida ham chiqmaydi:
   - shifokorga yoki bemorga;
   - epizod xulosasiga;
   - Heart Team protokoliga;
   - eskalatsiyaga.

   Shadow model xato bersa, asosiy yo'l buzilmaydi.
3. Kardiolog «Shadow» sahifasiga (`/shadow-ui`) kiradi va har bir EKG'ning asl yozuviga qarab ritmni tanlaydi. Bu ro'yxatda model javobi **ataylab ko'rsatilmaydi** (ko'r baholash).
4. Hisobotda faqat umumlashgan ko'rsatkichlar bor. U ulangan va shadow modelni shifokor yorlig'i bilan yonma-yon solishtiradi:
   - AFIB sezgirligi;
   - o'ziga xoslik;
   - tez ritmni AFIB deyish;
   - ritm mosligi.

## Kim nima qila oladi (kirish yoqilganda)
| Rol | Yorliq kiritish | Hisobot |
|---|---|---|
| kardiolog, jarroh | ✅ | ✅ |
| administrator | — | ✅ |
| klinitsist, ICU, bemor | — | — |

## Yoqish va o'chirish
- **Standart holat:** `weights/ecg_afib_multi2` papkasi bo'lsa, shadow yoqiladi.
- **Boshqa modellar:** `CARDIOPATH_SHADOW=papka1,papka2`.
- **O'chirish:** `CARDIOPATH_SHADOW=` (bo'sh qiymat).
- **Litsenziya:** product rejimida tijoratga ruxsat bo'lmagan model yuklanmaydi.

## Oldindan belgilangan qaror qoidasi (natijadan OLDIN yozilgan, o'zgartirilmaydi)
1. Ko'rsatkichlar kamida **30 ta AFIB** va **100 ta AFIB'siz** yorliq to'plangandan keyingina talqin qilinadi. Undan oldin sahifada «hali erta» deb yoziladi.
2. Shadow modelni ulashni taklif qilish uchun shifokor yorlig'iga nisbatan quyidagilar bajarilishi kerak:
   - AFIB sezgirligi ≥ 0.90;
   - o'ziga xoslik ≥ 0.92;
   - tez ritmlarning (titrash, SVT, sinus taxikardiyasi) AFIB deb belgilangani ≤ 15%;
   - sezgirlik ham, o'ziga xoslik ham ulangan modeldan past emas.
3. Bajarilsa ham model avtomatik ulanmaydi. Hisobot kardiologga ko'rsatiladi va ulash alohida, inson qarori bilan bo'ladi.
4. Hisobotga faqat ikkala model ham javob bergan va yorlig'i «Boshqa» bo'lmagan EKG'lar kiradi.

## Cheklovlar
- Yorliqni bitta shifokor qo'yadi. Ideal holatda ikkinchi shifokor ham ko'r o'qishi kerak, kelishmovchiliklar uchinchi shifokor bilan hal qilinadi. Hozircha buning imkoni yo'q.
- Shadow modelning ehtimol chegarasi juda past (0.047). Bu sezgirlikni oshiradi, lekin o'ziga xoslikni pasaytirishi mumkin. Chegara shadow natijasiga qarab **o'zgartirilmaydi**.

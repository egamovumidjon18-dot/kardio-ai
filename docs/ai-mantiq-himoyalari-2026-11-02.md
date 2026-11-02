# AI va qaror mantiqi — 2026-11-02 o‘zgarishlari

Telegramga o‘zgartirish kiritilmadi. Model og‘irliklari qayta o‘qitilmadi; quyidagilar ma’lumot va qaror chegaralaridagi dasturiy himoyalar.

- EKG, past EF, SHD, ExoKG va PCG yosh noma’lum, yaroqsiz yoki mos bo‘lmaganda xulosa bermaydi. EKG/ExoKG API yosh va epizod populyatsiyasi zidligini rad etadi.
- EKG, past EF, SHD, PCG, angiografiya va AKI ehtimolliklari tekshiriladi: NaN/Infinity, 0–1 dan tashqaridagi qiymat va noto‘g‘ri chiqish shakli past xavfga aylanmaydi.
- Ehtimollikni yaxlitlash qaror chegarasidan oldin bajarilmaydi. Chegaraga yaqin noaniq natija yaxlitlash sababli qat’iy javobga aylanmaydi.
- Risk kiritishlaridagi noto‘g‘ri LVEF, yaroqsiz sonlar va ikki blokdagi umumiy ko‘rsatkichlar zidligi saqlashdan oldin to‘xtatiladi. Keyingi to‘liq baholash eski “maydonlar kiritilmagan” ogohlantirishini bekor qiladi, tarixni o‘chirmaydi.
- `measured_at` haqiqiy o‘lchov sanasi, `created_at` yozuv yaratilgan sana. LVEF va AI taqqoslashlari o‘lchov sanasiga asoslanadi. Eski yozuvda sana yo‘q bo‘lsa, “solishtirib bo‘lmaydi” chiqadi. EKG va xavf baholash ekranlarida sanani kiritish mumkin; bo‘sh qoldirish “bugun” degani emas.
- Kech kiritilgan vaznning asl qiymati saqlanadi.
- Mahalliy o‘rgatish guruhlari normallashtirilgan bemor kodi xeshi orqali ajratiladi. Qayta tashriflar ichidan oxirgi tasdiqlangan yozuv olinadi. Yosh yoki bemor kaliti noma’lum yozuvlar o‘rgatishga kirmaydi. Eski epizod bo‘linishida o‘qitilgan mahalliy modeldan yangi bo‘linishga bevosita davom etish bloklanadi.

## Muhim cheklovlar

Bir bemorga turli kod berilsa, dastur ularning bir odam ekanini avtomatik bilmaydi. Bir xil barqaror bemor kodidan foydalanish kerak. Avvalgi mahalliy model mavjud bo‘lsa, yangi mustaqil baholash uchun bazaviy modeldan boshlash zarur; bu audit modelni avtomatik almashtirmaydi.

CirCor aniq yosh o‘rniga yosh guruhini beradi. Child va Adolescent guruhlarining butun oralig‘i mavjud PCG yosh chekloviga mos keladi; aniq yosh uydirilmaydi. Infant guruhi 28-kundan boshlangani uchun amaldagi 29-kun cheklovini to‘liq kafolatlamaydi va aniq yosh bo‘lmasa javob berilmaydi. Manba: [PhysioNet CirCor 1.0.3 dataset tavsifi](https://physionet.org/content/circor-heart-sound/1.0.3/).

Bu o‘zgarishlar qaysi yozuvlarga model javob berishini o‘zgartiradi. Eski AUROC/sezgirlik raqamlarini yangi ishlash tartibining o‘lchovi deb qabul qilib bo‘lmaydi: tegishli mustaqil datasetlarda qayta baholash kerak. Sun’iy signal bilan ONNX sinovi hisoblash yo‘lini tekshiradi, klinik aniqlikni isbotlamaydi.

AKI ML va ExoKG video modeli avvalgi muhitda ulanmagan; ularni bu tuzatishlar o‘z-o‘zidan yaratmaydi. Barcha muammolar bartaraf etildi yoki tizim klinik qo‘llash uchun tasdiqlandi degan da’vo yo‘q.

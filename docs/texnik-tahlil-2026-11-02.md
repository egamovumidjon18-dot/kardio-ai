# CardioPath AI — texnik tahlil

Sana: 2026-11-02, Toshkent. Tekshirilgan mahalliy commit: b793150.

## Qamrov va chegaralar

Asosiy API, saqlash, autentifikatsiya, Guardian, zaxiralash, model yuklash, o‘rgatish sikli, natijalarni birlashtirish, interfeys kodi, Docker sozlamalari va mavjud testlar ko‘rib chiqildi. Tadqiqot hisobotlari va o‘rgatish kodining asosiy oqimi tekshirildi. Bu har bir tadqiqot skriptini qayta bajarish yoki klinik validatsiya emas. Model sifat raqamlari mustaqil qayta hisoblanmadi; tibbiy formulalar tashqi klinik manbalar bilan qayta tasdiqlanmadi. Brauzerda vizual va barcha foydalanuvchi oqimlari sinovi bajarilmadi. Bemor yozuvlari o‘qilmadi va o‘zgartirilmadi.

## Haqiqiy ishlash holati

- Docker konteyneri healthy; /health javobi ok.
- research rejimi, auth off. Compose portni 127.0.0.1 bilan cheklaydi; shu sabab hozirgi holatni internetga ochiq deb bo‘lmaydi.
- PCG, EKG, angiografiya, past EF va SHD modullari ulangan.
- AKI ML va ExoKG video EF ulanmagan. ExoKG hujjatda ulangan deyilishi hozirgi Docker holatiga mos emas: adapter standartida Windows’dagi boshqa loyiha yo‘li bor, Compose esa EF yo‘lini bermaydi.
- Konteynerdagi testlar: 309 passed, 3 skipped, 37.30 s. 315 test degan oldingi hisobot qayta tasdiqlanmadi. Konteyner va mahalliy manbalar faylma-fayl solishtirilmadi.
- Mahalliy Python testlarni boshlay olmadi: numpy yo‘q. Docker testlari o‘tdi, lekin eskirayotgan API va pytest cache ruxsatlari haqida ogohlantirishlar bor.

## Ustuvor topilmalar

### 1. P1 — yuborilmagan xabar yetkazilgan hisoblanadi (sun’iy misolda tasdiqlandi)

`guardian/escalation.py:52–55`: LogNotifier faqat jurnalga yozib True qaytaradi. `api/main.py` Telegram sozlanmaganida uni tanlaydi. Natija notified=True; alert sent sifatida saqlanadi, qayta yuborish navbatiga kirmaydi. Bemor interfeysi ham yetkazilmaganlik izohini ko‘rsatmaydi. Bundan tashqari PATIENT_MESSAGES xabar yetkazilganini natijadan oldin ta’kidlaydi.

Taklif: jurnalga yozish, tashqi xizmatga yetkazish va shifokor qabul qilishini alohida holatlarda yuritish. Sozlanmagan kanalni sent demaslik, bemor matnini haqiqiy holatga moslash.

### 2. P1 — mavjud bo‘lmagan zaxiradan tiklash bo‘sh baza bilan almashtiradi (sun’iy bazada tasdiqlandi)

`core/backup.py:56–70`: sqlite3.connect mavjud bo‘lmagan manba faylini yaratadi; bo‘sh bazada integrity_check “ok” bo‘ladi. Keyin shu fayl amaldagi bazaga ko‘chiriladi. Sinovda patients jadvali bor baza tiklashdan keyin jadvalsiz qoldi. Avvalgi baza .before-restore nusxasida qoladi, ammo xizmat ma’lumotsiz bazaga o‘tadi.

Taklif: mavjud faylni read-only ochish, kerakli jadvallar va sxemani tekshirish, xizmat to‘xtaganini ta’minlash, tiklashni vaqtinchalik fayl va atomik almashtirish orqali bajarish. create_backup manbasi uchun ham mavjudlik tekshiruvi kerak.

### 3. P1 — yosh kiritilmasa kattalar modeli bolalarda ishlashi mumkin (kod bilan tasdiqlangan)

`ecg/model.py:73`, `api/ai_routes.py`: yosh ixtiyoriy; cheklov faqat yosh berilganda ishlaydi. Epizod population=pediatric bo‘lsa ham endpoint buni modelga cheklov sifatida bermaydi. Xuddi shunday ixtiyoriy yosh tekshiruvlari PCG va ExoKG adapterida bor.

Taklif: tug‘ilgan sana/yoshni epizodga bog‘lash, modelga mos yosh aniqlanmaguncha abstain qilish, populyatsiya va yosh nomuvofiqligini rad etish.

### 4. P1 — o‘rgatish/sinov ajratilishi bemor emas, epizod bo‘yicha (kod bilan tasdiqlangan)

`learning/dataset.py:31–42`, `research/export_local.py:collect_children`: guruh hash(eid) bilan belgilanadi. Episode.id har yangi epizodda boshqa UUID; patient_ref bo‘yicha guruhlash yo‘q. Bitta bemorning ikki epizodi train va testga tushib, sifat bahosini sun’iy yaxshilashi mumkin. “Bola darajasida ajratish” izohi shu sharoitda bajarilmaydi.

Taklif: barqaror bemor identifikatori bilan guruhlash, guruhlar o‘rtasidagi bemor va yozuv takrorlarini tekshirish. Model tanlashda muntazam ishlatiladigan testdan tashqari yakuniy mustaqil to‘plam saqlash.

### 5. P2 — eski sana bilan vazn yuborilganda noto‘g‘ri qiymat shu sanaga yoziladi

`api/guardian_routes.py:81–84`, `guardian/checkin.py:weight_trend`: funksiya vaqt bo‘yicha eng yangi qiymatni qaytaradi, endpoint esa uning sanasini yangi so‘rov sanasiga almashtiradi. Misol: 2-noyabrda 80 kg bor; keyin 1-noyabr uchun 75 kg yuborilsa, funksiya 80 qaytaradi va endpoint uni 1-noyabrga bog‘laydi. Funksiya qismi sun’iy misolda tasdiqlandi.

Taklif: yangi o‘lchovning asli va trend xulosasini alohida saqlash; kelajak sanalari, takroriy va kech kiritilgan o‘lchovlarni tekshirish.

### 6. P2 — “30 kun” taqqoslash o‘lchov sanasi emas, kiritish sanasidan foydalanadi

`integration/concordances.py:16–30`: lvef_evidence yangi created_at oladi; risk shaklida haqiqiy ExoKG o‘lchov sanasi yo‘q. Eski tekshiruv natijasi bugun kiritilsa, u bugungi AI bilan yangi o‘lchovdek solishtiriladi.

Taklif: measured_at va recorded_at ni ajratish, solishtirishda measured_at dan foydalanish; sana noma’lum holatni ochiq ko‘rsatish.

### 7. P2 — PCG yuklamasi va model hisobi serverni band qilib qo‘yishi mumkin

`api/main.py:331`: audio to‘liq await f.read() bilan, ilova darajasida fayl hajmi chegarasisiz o‘qiladi. AI endpointlarida CPU hisoblari async funksiya ichida bevosita bajariladi; shu vaqtda hodisalar sikli boshqa ishlarni kechiktiradi. EKG/rasm/video uchun hajm cheklovlari bor, PCG yo‘lida teng himoya yo‘q.

Taklif: umumiy so‘rov/fayl/signal davomiyligi limitlari; hisoblarni chegaralangan ishchi navbatiga chiqarish va vaqt cheklovlari.

### 8. P2 — parallel so‘rov qulfi uchun yuqori yuk sinovi yetishmaydi

`api/main.py:117`: lock.acquire umumiy AnyIO ishchi oqimlari orqali kutiladi; shu oqimlar sinxron endpointlarga ham kerak. Kutuvchilar barcha o‘rinlarni band qilsa, qulf egasining endpointi bajarilishiga o‘rin qolmasligi mumkin. Qulflar lug‘ati ham tozalanmaydi va autentifikatsiyadan oldin to‘ldiriladi. Mavjud test 12 ta so‘rovni tekshiradi. Yuqori yukdagi to‘xtash bu auditda qayta namoyish qilinmadi — alohida stress sinovi kerak.

Taklif: kutishda ishchi oqimni band qilmaydigan navbat, boshqariladigan qulf hayot sikli, bitta event loop va haqiqiy server sharoitidagi yuqori yuk testi.

### 9. P2 — ogohlantirish va epizod bir tranzaksiyada saqlanmaydi

`api/guardian_routes.py:_finish`: avval tashqi xabar yuboriladi, keyin alert alohida saqlanadi, so‘ng epizod saqlanadi. Oxirgi qadam yiqilsa, saqlanmagan o‘lchovga tegishli alert qoladi. `api/ai_routes.py` EKG natijalarini ham bosqichma-bosqich saqlaydi: keyingi model yiqilsa, mijoz xato oladi, ammo birinchi natija allaqachon yozilgan. Guardian interfeysidagi checkin va INR ikki so‘rov; ikkinchisi yiqilganda qayta urinish birinchisini takrorlaydi.

Taklif: ma’lumot+alert+jo‘natish navbatini bitta tranzaksiyada saqlash, so‘rovlarga takrorlashdan himoya kaliti, qisman saqlashni aniq qaytarish.

### 10. P2 — kirish ma’lumotlari va eski ogohlantirish holati to‘liq nazorat qilinmagan

`risk/euroscore2.py`, `risk/aki.py`: LVEF uchun API modelida son diapazoni cheklovi yo‘q. API ikki blokdagi LVEF ni solishtiradi, lekin jins/kreatinin/operatsiya xususiyatlarining boshqa nomuvofiqliklarini birlashtirmaydi. `api/risk_routes.py` risk.assumptions ni faqat yetishmagan maydon bo‘lganda yozadi; keyingi to‘liq baholash eski assumptions ni bekor qilmaydi. Digest esa shu eski dalilni latest sifatida ko‘rsatishda davom etadi.

Taklif: umumiy tekshirilgan bemor kiritishlari, sonlar diapazoni va finite tekshiruvi; har baholashda assumptions holatini yangilash.

## Ekspluatatsiya va saqlash

- Zaxira faqat SQLite bazani qamraydi. Research audio fayllari, model versiyalari va ishga tushirish sozlamalari alohida. Bazani tiklash barcha o‘rgatish imkoniyatlarini tiklamaydi.
- Bir diskdagi nusxa boshqa diskdagi nusxa o‘rnini bosa olmaydi; amaliy tiklash mashqi va tashqi nusxa kerak.
- Zaxira nomi vaqtgacha bo‘lgan tekshiruv asosida tanlanadi; qo‘lda va avtomatik nusxa bir vaqtda ishlashiga qarshi qulf yo‘q.
- Auth off mahalliy tajriba uchun tushunarli; tarmoqqa chiqarishdan oldin hisoblar, rollar va transport himoyasi kerak. Patient havolasidagi localhost boshqa qurilmada shu serverni ochmaydi.
- requirements.txt pastki versiya chegaralarini beradi, aniq takrorlanuvchi dependency to‘plami yo‘q. Repozitoriyda CI konfiguratsiyasi topilmadi.
- Model tasdiqlash va rollback fayl holatini o‘qib-qayta yozadi, parallel amallarga qarshi umumiy qulf ko‘rinmadi. Yangi model faqat restartdan keyin yuklanishi interfeysga qaytariladi — bu qismi ochiq ko‘rsatilgan.

## Yaxshi ishlangan qismlar

- Evidence, provenance va audit ajratilgan; qaror manbasini kuzatish mumkin.
- SQLite revision tekshiruvi eskirgan yozuv bilan boshqa natijani bosishni to‘sadi; testlari bor.
- Auth yoqilganda ruxsat jadvaliga kirmagan API avtomatik rad etiladi; bemor o‘z epizodi bilan cheklanadi.
- Parollar scrypt, seanslar token hash bilan saqlanadi; oxirgi admin himoyasi bor.
- Modelning abstain holati, rad etilgan tajribalar va inson tasdig‘i jarayoni mavjud.
- Zaxira olish SQLite backup API orqali amalga oshiriladi; oddiy ishlayotgan baza faylini ko‘chirishdan yaxshiroq.

## Tavsiya etilgan ketma-ketlik

1. Yetkazish holati va zaxiradan tiklash xatolarini tuzatish, chegaraviy testlar qo‘shish.
2. Yosh va o‘lchov vaqtini ishonchli saqlash; vazn va risk kiritish xatolarini yopish.
3. Barqaror bemor identifikatori bilan o‘rgatish bo‘linishini tuzatish.
4. Parallel yuk, atomik saqlash va takroriy so‘rov himoyasi.
5. Docker modeli/sozlamalari, tashqi zaxira, CI va brauzer oqimlari sinovi.
6. Shundan keyin mustaqil klinik validatsiya va yangi AKI/POAF tadqiqotlari.

Xulosa: asosli tadqiqot prototipi, lekin testlarning o‘tishi barcha xavfsizlik holatlari qamralganini anglatmaydi. Yangi funksiyalardan avval tasdiqlangan ma’lumot va xabar yetkazish xatolarini yopish maqsadga muvofiq. Audit davomida dastur kodi o‘zgartirilmadi; faqat ushbu hisobot qo‘shildi.

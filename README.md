# VECTOR — kirish va ro'yxatdan o'tish (API + web)

Django + DRF (JWT) asosidagi autentifikatsiya. Tasdiqlash **SMS orqali emas,
Telegram bot orqali** amalga oshiriladi. Backend to'liq API ko'rinishida —
keyinchalik mobil ilova ham xuddi shu endpointlardan foydalanadi.

## 1. O'rnatish

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # Windows  (Linux/macOS: cp .env.example .env)
```

`.env` fayli allaqachon to'ldirilgan (bot: **@vectortalim_bot**).
Bu fayl `.gitignore` da — git'ga tushmaydi.

## 2. Ma'lumotlar bazasi va server

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Ikkinchi terminalda **botni ishga tushiring**:

```bash
python manage.py runbot
```

Sahifalar:

| Manzil | Vazifasi |
|---|---|
| `/kirish/` | Telefon + parol bilan kirish |
| `/royxatdan-otish/` | Ro'yxatdan o'tish formasi |
| `/tasdiqlash/` | Telegram orqali kod tasdiqlash |
| `/parolni-tiklash/` | Parolni unutganlar uchun |
| `/kabinet/` | Kirgandan keyingi sahifa (namuna) |
| `/boshqaruv/` | **Admin panel** (asosiy boshqaruv) |
| `/admin/` | Django admin (texnik) |

## 3. Ro'yxatdan o'tish jarayoni

1. Foydalanuvchi formani to'ldiradi → `POST /api/auth/register/`
   Server foydalanuvchini **nofaol** holatda yaratadi va Telegram havolasini qaytaradi:
   `https://t.me/<bot>?start=<token>`
2. Foydalanuvchi botni ochadi → **«📱 Telefon raqamni ulashish»** tugmasini bosadi.
3. Bot raqamni formadagi raqam bilan solishtiradi. Mos kelsa — 5 xonali kod yuboradi.
   Mos kelmasa, ogohlantirish beradi (boshqa odamning raqamini yuborish ham bloklanadi).
4. Sayt har 3 soniyada `GET /api/auth/verification/<id>/` orqali holatni tekshiradi.
   Kod yuborilgach, kod kiritish oynasi ochiladi.
5. `POST /api/auth/verify/` → foydalanuvchi faollashadi va **JWT** token beriladi.

## 4. API endpointlar

| Metod | Manzil | Izoh |
|---|---|---|
| POST | `/api/auth/register/` | Ro'yxatdan o'tish, Telegram havolasini qaytaradi |
| GET | `/api/auth/verification/<uuid>/` | Tasdiqlash holati: `waiting_start` / `code_sent` / `expired` / `used` |
| POST | `/api/auth/verify/` | `{verification_id, code}` → JWT |
| POST | `/api/auth/resend/` | Kodni qayta yuborish (60 soniyada 1 marta) |
| POST | `/api/auth/login/` | `{phone, password}` → JWT |
| POST | `/api/auth/password-reset/` | `{phone}` → Telegramga kod yuboradi |
| POST | `/api/auth/password-reset/confirm/` | `{verification_id, code, password, password2}` → yangi parol + JWT |
| POST | `/api/auth/token/refresh/` | `{refresh}` → yangi `access` |
| GET | `/api/auth/me/` | Joriy foydalanuvchi (Bearer token) |

Telefon raqam har qanday ko'rinishda yuborilishi mumkin — server uni
`+998XXXXXXXXX` formatiga keltiradi.

## 5. Rollar

| Rol | Qiymat | Qanday beriladi |
|---|---|---|
| O'quvchi | `student` | Ro'yxatdan o'tishda tanlanadi (standart) |
| O'qituvchi | `teacher` | Ro'yxatdan o'tishda tanlanadi; qo'shimcha "Fan" maydoni |
| Administrator | `admin` | Faqat `createsuperuser` yoki admin panel orqali |

Saytdan `admin` rolini tanlab ro'yxatdan o'tib bo'lmaydi — API buni rad etadi.
Rol `GET /api/auth/me/` javobida `role` va `role_display` sifatida qaytadi.

O'quvchi uchun "Sinf", o'qituvchi uchun "Fan" maydoni ko'rsatiladi —
ikkinchisi serverda ham tozalanadi (o'qituvchida `grade` bo'sh qoladi).

## 6. Parolni tiklash

1. `/parolni-tiklash/` sahifasida telefon raqam kiritiladi.
2. Foydalanuvchi allaqachon bot bilan bog'langani uchun kod **darhol Telegramga** yuboriladi.
   (Agar bog'lanmagan bo'lsa — bot havolasi ko'rsatiladi.)
3. Kod + yangi parol kiritiladi → parol almashadi va JWT beriladi.

## 7. Xavfsizlik

- Kod bazada **hash** holida saqlanadi (ochiq matnda emas).
- Kod amal qilish muddati — 5 daqiqa (`OTP_TTL_SECONDS`).
- Noto'g'ri urinishlar cheklovi — 5 ta (`OTP_MAX_ATTEMPTS`).
- Endpointlarda throttling: ro'yxatdan o'tish 10/soat, kirish 20/soat va h.k.
- Bot faqat foydalanuvchining **o'z** kontaktini qabul qiladi.

## 8. Productionga chiqarish

Long polling o'rniga webhook ishlatish qulayroq:

```bash
python manage.py setwebhook https://sizning-domeningiz.uz
```

Shuningdek `.env` da `DEBUG=False`, `ALLOWED_HOSTS` ni to'ldiring va
`CORS_ALLOWED_ORIGINS` ro'yxatiga mobil/frontend manzillarini qo'shing.

## 9. Loyiha tuzilmasi

```
config/      — Django sozlamalari va asosiy URL'lar
accounts/    — User modeli, Telegram OTP, API view'lar, bot buyruqlari
bot/         — Telegram xabarlarini qayta ishlash mantig'i
frontend/    — Sahifalarni ko'rsatuvchi view'lar
templates/   — HTML sahifalar
static/      — CSS, JS, logotip
```


---

# 10. Admin panel

Manzil: **`/boshqaruv/`** — telefon raqam va parol bilan kiriladi.
Panelga faqat `is_staff` yoki `role=admin` bo'lgan hisoblar kira oladi.

## Bo'limlar

| Bo'lim | Nima qilinadi |
|---|---|
| 📊 Dashboard | Jami foydalanuvchilar, bugun kirganlar, kurslar, darslar, premium, do'kon, daromad; 30 kunlik grafiklar; so'nggi ro'yxatdan o'tganlar va buyurtmalar |
| 👥 Foydalanuvchilar | Qidiruv va filtr (rol, premium/oddiy, bloklangan, tasdiqlanmagan), profil, kurslardagi progress, obunalar, to'lovlar, **bloklash/blokdan chiqarish**, o'chirish |
| 📚 Kurslar | Qo'shish/tahrirlash/o'chirish, kategoriya, o'qituvchi, bepul/premium/pullik, narx, daraja, bosh sahifada ko'rsatish |
| 🏷️ Kategoriyalar | Ikonka, rang, tartib |
| 🎬 Darslar | `Kurs → Modul → Dars` daraxti; video, matn, PDF/fayl biriktirish, bepul demo dars, darsni bloklash |
| 🛒 Mahsulotlar | Rasm, narx, eski narx, qoldiq, artikul, sotuvdan chiqarish |
| 📦 Buyurtmalar | Holat (yangi → to'langan → yuborilgan → yakunlangan), mijoz ma'lumotlari; "to'langan" qilinganda qoldiq avtomatik kamayadi |
| 💎 Premium tariflar | START/PRO/VIP kartalari, imkoniyatlar ro'yxati, muddat, rang, "eng ommabop" belgisi |
| ⭐ Obunalar | Ro'yxat, qo'lda premium berish, bekor qilish |
| 💳 To'lovlar | Payme/Click tranzaksiyalari, holati, summasi |
| 🔔 Bildirishnomalar | Sarlavha, matn, rasm; auditoriya (barcha / premium / oddiy / o'quvchi / o'qituvchi / muayyan kurs); Telegramga ham yuborish |
| 🖼️ Bannerlar | Rasm, tugma, havola, boshlanish/tugash sanasi, joylashuv |
| 📈 Statistika | 7/30/90/365 kunlik grafiklar, daromad manbalari, tariflar bo'yicha ulush, eng ommabop kurslar |
| 🔐 Adminlar | Admin qo'shish, huquqlarni olib tashlash |
| 🕘 Amallar jurnali | Kim nimani o'zgartirgani |
| ⚙️ Sozlamalar | Sayt nomi, aloqa, ilova havolalari, texnik ish rejimi |

## Tungi rejim va tillar

- Yuqori o'ng burchakdagi 🌙 tugmasi mavzuni almashtiradi (tanlov cookie'da saqlanadi).
- 🌐 tugmasi orqali **4 til**: O'zbekcha, Ўзбекча (kirill), Русский, English.
  Panel interfeysi to'liq tarjima qilingan (`locale/` papkasi).
- Kurs/dars/mahsulot **matnlari** ham 4 tilda saqlanadi: har bir forma ostida
  «Boshqa tillardagi matnlar» bloki bor. Tarjima bo'sh bo'lsa — o'zbekchasi ko'rsatiladi.

Tarjimani o'zgartirgandan keyin:

```bash
python manage.py makemessages -l ru -l en -l uz_Cyrl
python manage.py compilemessages
```

---

# 11. Videolarni Telegramda saqlash

Videolar **serverda saqlanmaydi** — yopiq Telegram kanaliga yuklanadi,
bazada faqat `file_id` qoladi. Yuklash/yuklab olish **Pyrogram (MTProto)**
orqali amalga oshiriladi — rasmiy Bot API'ning HTTP chegaralari (50/20 MB)
bunga tegishli emas, shuning uchun alohida Local Bot API server kerak emas.

## Sozlash

1. Telegramda **yopiq kanal** oching.
2. `@vectortalim_bot` ni o'sha kanalga **admin** qilib qo'shing.
3. Kanal ID sini oling (masalan `-1001234567890`) va `.env` ga yozing:
   `TELEGRAM_STORAGE_CHAT_ID=-1001234567890`
4. https://my.telegram.org/apps sahifasiga shaxsiy Telegram hisobingiz bilan
   kiring va yangi ilova yarating — u yerdan **`api_id`** va **`api_hash`**
   olasiz. Buni `.env`ga yozing:
   ```
   TELEGRAM_API_ID=1234567
   TELEGRAM_API_HASH=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
5. Kutubxonalarni o'rnating: `pip install -r requirements.txt` (`pyrogram` va
   `tgcrypto`ni qo'shadi).

Birinchi ishga tushirishda Pyrogram `telegram_sessions/` papkasida sessiya
faylini avtomatik yaratadi (bu — botning login holati, `.env` kabi maxfiy;
`.gitignore`ga qo'shilgan).

## Himoya qanday ishlaydi

```
Admin panel  →  video  →  yopiq Telegram kanali
                              ↓ (faqat file_id bazada)
Ilova  ←  /api/lessons/<id>/video/?t=<imzo>  ←  server oqim qilib uzatadi
```

- Havola **imzolangan** va 5 daqiqa amal qiladi (`VIDEO_LINK_TTL`).
- Havola **bitta foydalanuvchiga** bog'langan — boshqa odam ishlatolmaydi.
- Bot tokeni hech qachon mijozga chiqmaydi.
- Qulflangan (premium) dars uchun API umuman havola bermaydi.
- `Range` so'rovi qo'llab-quvvatlanadi — video oldinga suriladi.

## ⚠️ Hajm chegarasi

MTProto orqali ulanganda bot uchun yuklash va yuklab olish chegarasi —
**taxminan 2 GB** (rasmiy Bot API'dagi 50/20 MB cheklovlari qo'llanilmaydi).

## Muqobil variant: Local Bot API server

Agar biror sababga ko'ra Pyrogram/MTProto o'rniga rasmiy Bot API'ning HTTP
qatlamida qolishni xohlasangiz, `telegram-bot-api` binaryni o'zingiz ishga
tushirib, shu orqali ham 2 GB gacha chegaraga erishish mumkin — lekin bu
qo'shimcha jarayonni serverda doimiy ishga tushirib turishni talab qiladi.
Hozirgi loyihada bu yo'l ishlatilmaydi.

---

# 12. To'lov tizimlari (Payme va Click)

`.env` ga kalitlarni yozing, so'ng to'lov tizimlarining kabinetida quyidagi
manzillarni ko'rsating:

| Tizim | Endpoint |
|---|---|
| Payme (Merchant API) | `https://domeningiz.uz/tolov/payme/` |
| Click (Prepare/Complete) | `https://domeningiz.uz/tolov/click/` |

Ilova to'lovni shunday boshlaydi:

```
POST /api/subscribe/        {"plan": 2, "provider": "payme"}
POST /api/shop/orders/      {...mahsulotlar..., "provider": "click"}
→ javobda checkout.payme va checkout.click havolalari keladi
```

To'lov muvaffaqiyatli bo'lganda tizim **avtomatik**: obunani faollashtiradi,
buyurtmani "to'langan" qiladi va qoldiqni kamaytiradi, yoki kursga yozadi.

Qo'llab-quvvatlanadigan Payme metodlari: `CheckPerformTransaction`,
`CreateTransaction`, `PerformTransaction`, `CancelTransaction`,
`CheckTransaction`, `GetStatement`.

---

# 13. Mobil ilova uchun API

| Metod | Manzil | Izoh |
|---|---|---|
| GET | `/api/config/` | Sayt sozlamalari, tillar, umumiy statistika |
| GET | `/api/banners/` | Bosh sahifa bannerlari |
| GET | `/api/categories/` | Kurs kategoriyalari |
| GET | `/api/courses/` | Kurslar (`?category=`, `?featured=1`, `?q=`) |
| GET | `/api/courses/<slug>/` | Kurs + modullar + darslar (lock holati bilan) |
| POST | `/api/courses/<slug>/enroll/` | Kursga yozilish |
| GET | `/api/lessons/<id>/` | Dars + video havolasi + fayllar |
| GET | `/api/lessons/<id>/video/?t=` | Video oqimi (imzolangan havola) |
| POST | `/api/lessons/<id>/complete/` | Darsni tugatish, progress qaytadi |
| GET | `/api/my/courses/` | Mening kurslarim |
| GET | `/api/plans/` | Premium tariflar |
| POST | `/api/subscribe/` | Obuna + to'lov havolasi |
| GET | `/api/my/subscription/` | Joriy obuna |
| GET | `/api/shop/products/` | Mahsulotlar |
| POST | `/api/shop/orders/` | Buyurtma + to'lov havolasi |
| GET | `/api/notifications/` | Bildirishnomalar |
| POST | `/api/notifications/<id>/read/` | O'qilgan deb belgilash |

Har bir so'rovga `?lang=ru` (yoki `uz-cyrl`, `en`) qo'shsangiz, matnlar
o'sha tilda qaytadi.

---

# 14. Sinov ma'lumotlari

```bash
python manage.py seed_demo          # 40 foydalanuvchi, kurslar, darslar, buyurtmalar
python manage.py seed_demo --users 200
```

Bu faqat sinov uchun — productionda ishlatmang.

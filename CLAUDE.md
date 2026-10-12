# Kararsızım — Proje Planı ve Claude Code Rehberi

> Bu dosya Claude Code için ana referanstır. Projeye başlarken repo köküne `CLAUDE.md` adıyla da kopyalanabilir.
> **Çalışma kuralı:** Aynı anda yalnızca **bir faz** yap. Faz bitince dur, kabul kriterlerini kontrol et, benden onay bekle.

---

## 0. Netleşen Kararlar (Faz 0 öncesi)

- **Supabase projesi:** `kararsizim` (ref `ehkeupuuvzmowyedheaj`), bölge `eu-central-1` (Frankfurt), ücretsiz plan. Vercel fonksiyon bölgesi de `fra1`.
- **Deploy:** GitHub repo → Vercel Git entegrasyonu (her push otomatik deploy).
- **Anonim oy kesindir:** Anonim ziyaretçi oyunu değiştiremez; sadece giriş yapmış kullanıcı oyunu değiştirebilir.
- **Çalışma şekli:** Claude kodu kendi bulut ortamında yazar ve test eder, dosyaları proje klasörüne yazar; son kontrol yerelde `runserver` ile yapılır.
- **Sürümler:** Python 3.14 (yerel + Vercel, `.python-version`). Her bağımlılığın en güncel kararlı sürümü tercih edilir; `requirements.txt`'te tam sürümle sabitlenir (şu an Django 6.1).
- **Pooler notu:** Transaction pooler sunucu tarafı prepared statement desteklemez → `OPTIONS["prepare_threshold"] = None` (settings.py'de ayarlı).

---

## 1. Proje Özeti

**Ad:** Kararsızım

**Amaç:** Kullanıcılar kararsız kaldıkları konularda ("Bugün sinemaya mı gitsem, restorana mı?") kısa anketler açar, diğer kullanıcılar oylayarak yardımcı olur.

**Temel kurallar**
- Bir anketin **en az 2, en fazla 5** seçeneği olur.
- Platformdaki her anket herkese açıktır. Takip/follow, arkadaşlık, feed kişiselleştirme **yok**.
- **Üye olmadan** anketleri görmek ve oy vermek serbest.
- **Anket oluşturmak için** üyelik/giriş zorunlu. Giriş yapmamış kullanıcı "Anket Oluştur"a basarsa giriş/kayıt sayfasına yönlendirilir (giriş sonrası geri döner).
- Kayıt: **e-posta + kullanıcı adı + parola**. Anketlerde sadece **kullanıcı adı** görünür, e-posta asla herkese açık API/HTML çıktısında yer almaz.
- Bu bir **prototip**. Basit tut, aşırı mühendislik yapma.

**Kapsam dışı (şimdilik yapma):** yorumlar, bildirimler, takip sistemi, kategori/etiket, arama, admin paneli özelleştirme, e-posta doğrulama, parola sıfırlama, sosyal giriş, çoklu dil, PWA, test otomasyonu altyapısı (temel birkaç test yeterli).

---

## 2. Teknoloji Yığını

| Katman | Seçim | Not |
|---|---|---|
| Backend | Python 3.14 + Django 6.1 | Django'nun kendi auth sistemi (özel User modeli) |
| Veritabanı | Supabase (PostgreSQL) | Sadece **Postgres olarak** kullanılır; Supabase Auth/Client SDK **kullanılmaz** |
| Frontend | Saf HTML + CSS + JS | Framework yok, build adımı yok. Aynı repo içinde |
| Deploy | Vercel | Python runtime (serverless) |
| API stili | Django `JsonResponse` ile basit JSON endpoint'leri | DRF kullanma (prototip için gereksiz) |

**Neden Django Auth, Supabase Auth değil?** Tek bir kimlik sistemi, tek bir yer. Supabase yalnızca yönetilen Postgres sağlar; böylece RLS/JWT/iki sistem senkronu karmaşıklığından kaçınırız.

### Önemli teknik kararlar
1. **Vercel serverless** olduğu için dosya sistemi kalıcı değil → **SQLite kullanma**. Her şey Supabase Postgres'te.
2. Supabase bağlantısı için **Connection Pooler (transaction mode, port 6543)** adresini kullan. Bu modda: `DISABLE_SERVER_SIDE_CURSORS = True`, `CONN_MAX_AGE = 0`.
3. Session'lar veritabanında (`django.contrib.sessions` varsayılan backend) tutulur.
4. Statik dosyalar: `whitenoise` ile servis et. Vercel'in güncel Django dağıtım dokümanını kontrol et; gerekirse `collectstatic` çıktısını Vercel'in beklediği yapıya uyarla.
5. **Migration'lar yerelde çalıştırılır** (`python manage.py migrate` ile doğrudan Supabase'e). Vercel build'inde migrate çalıştırma.
6. Gizli bilgiler (`SECRET_KEY`, `DATABASE_URL`) sadece ortam değişkenlerinde. `.env` dosyası `.gitignore`'da olacak, `.env.example` commit'lenecek.

---

## 3. Klasör Yapısı (hedef)

```
kararsizim/
├── CLAUDE.md                  # bu dosyanın kopyası (isteğe bağlı)
├── manage.py
├── requirements.txt
├── vercel.json
├── .env.example
├── .gitignore
├── config/                    # Django proje ayarları
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/                  # kullanıcı & auth
│   ├── models.py              # özel User
│   ├── views.py               # register / login / logout / me
│   └── urls.py
├── polls/                     # anketler
│   ├── models.py              # Poll, Option, Vote
│   ├── views.py               # sayfa + JSON endpoint'leri
│   └── urls.py
├── templates/
│   ├── base.html
│   ├── index.html             # anket akışı
│   ├── poll_detail.html       # (opsiyonel, paylaşılabilir tek anket sayfası)
│   ├── create.html
│   ├── login.html
│   └── register.html
└── static/
    ├── css/
    │   ├── tokens.css         # renk, font, aralık değişkenleri
    │   └── app.css
    └── js/
        ├── api.js             # fetch yardımcıları (CSRF dahil)
        ├── feed.js
        ├── vote.js
        ├── create.js
        └── auth.js
```

Frontend, Django template'leri ile servis edilen sayfalar + sayfa içinde `fetch` ile JSON API çağıran vanilla JS'ten oluşur.

---

## 4. Veri Modeli

**User** (`accounts.User`, `AbstractUser` türevi)
- `username` — benzersiz, 3–20 karakter, harf/rakam/`_`, büyük-küçük harf duyarsız benzersizlik (örn. `username__iexact` kontrolü)
- `email` — benzersiz, zorunlu (giriş için de kullanılabilir; giriş **e-posta veya kullanıcı adı** ile olabilir)
- `password` — Django hash'li
- `created_at`

**Poll**
- `id`
- `author` → FK(User, on_delete=CASCADE)
- `question` — CharField(max 140), zorunlu
- `created_at`

**Option**
- `id`
- `poll` → FK(Poll, related_name="options", on_delete=CASCADE)
- `text` — CharField(max 60)
- `position` — küçük tamsayı (sıralama)

**Vote**
- `id`
- `poll` → FK(Poll)
- `option` → FK(Option, on_delete=CASCADE)
- `user` → FK(User, null=True, blank=True) — anonim oyda `NULL`
- `created_at`
- Kısıt: `user` dolu ise `(poll, user)` benzersiz (UniqueConstraint, condition=`user IS NOT NULL`)

### Oy kuralları ("takip mekanizması yok" ilkesi)
- **Sunucu tarafında IP, cihaz parmak izi, çerez ile izleme/analitik YAPILMAZ.**
- Giriş yapmış kullanıcı: bir ankette **1 oy**; seçimini değiştirirse mevcut oy güncellenir.
- Anonim ziyaretçi: oy `user=NULL` olarak kaydedilir. Tekrar oy vermeyi engellemek için **sadece tarayıcıda** `localStorage` kullanılır (`voted_<pollId> = optionId`). Bu bilinçli bir prototip tavizidir; kullanıcı temizlerse tekrar oy verebilir. İleride iyileştirilecek (kod yorumuna not düş).
- Kullanıcı kendi anketine de oy verebilir.
- Oy verenlerin kimliği **kimseye gösterilmez**; sadece toplam sayılar ve yüzdeler görünür.

---

## 5. API Tasarımı (JSON)

Tüm yanıtlar `application/json`. POST/PUT/DELETE istekleri Django CSRF korumalı (`X-CSRFToken` header'ı; `api.js` bunu cookie'den okuyup ekler).

| Method | Yol | Yetki | Açıklama |
|---|---|---|---|
| GET | `/api/polls/?page=1` | herkes | Anketleri yeniden eskiye listeler (sayfa başı 10) |
| GET | `/api/polls/<id>/` | herkes | Tek anket |
| POST | `/api/polls/` | giriş şart (401 döner) | Anket oluşturur |
| POST | `/api/polls/<id>/vote/` | herkes | Oy verir/günceller |
| DELETE | `/api/polls/<id>/` | sadece yazar | Kendi anketini siler (Faz 5) |
| POST | `/api/auth/register/` | herkes | Kayıt + otomatik giriş |
| POST | `/api/auth/login/` | herkes | `identifier` (e-posta veya kullanıcı adı) + `password` |
| POST | `/api/auth/logout/` | giriş | Çıkış |
| GET | `/api/auth/me/` | herkes | `{ "authenticated": bool, "username": str\|null }` |

**Anket JSON şekli**
```json
{
  "id": 12,
  "question": "Bugün sinemaya mı gitsem restorana mı?",
  "author": "ali_k",
  "created_at": "2026-10-07T12:30:00Z",
  "total_votes": 14,
  "options": [
    { "id": 31, "text": "Sinema", "votes": 8, "percent": 57 },
    { "id": 32, "text": "Restoran", "votes": 6, "percent": 43 }
  ],
  "my_vote": 31
}
```
- `my_vote`: yalnızca giriş yapmış kullanıcı için dolu (kendi oyu); anonim için `null` (frontend `localStorage`'a bakar).
- **E-posta hiçbir yanıtta yer almaz.**

**Oy isteği:** `{ "option_id": 31 }` → güncel anket JSON'u döner.

**Doğrulama kuralları (sunucu tarafı zorunlu)**
- `question`: boşluk kırpılmış, 1–140 karakter.
- `options`: 2–5 adet, her biri boşluk kırpılmış 1–60 karakter, aynı anket içinde tekrar yok (büyük-küçük harf duyarsız).
- `option_id` o ankete ait olmalı.
- Kayıt: parola min 8 karakter (Django `validate_password`), e-posta formatı, e-posta ve kullanıcı adı benzersiz. Hata mesajları Türkçe ve alan bazlı: `{ "errors": { "username": ["..."] } }`.
- Anket oluşturma ve oy kaydı `transaction.atomic` içinde.
- Oy sayıları için N+1 sorgudan kaçın (`annotate(Count)` / `prefetch_related`).

---

## 6. Sayfalar ve Davranışlar

1. **Ana sayfa `/`** — Üstte logo + "Anket Oluştur" butonu + giriş durumu (Giriş / Kayıt veya `@kullanici` / Çıkış). Altta anket kartları akışı, "Daha fazla yükle" butonu.
2. **Anket kartı** — Soru, `@yazar · x dk önce`, seçenek butonları. Oy verilmeden önce seçenekler tıklanabilir butondur; oy verildikten sonra her seçenekte yüzde çubuğu + oy sayısı gösterilir, seçilen vurgulanır. Oy verilmeden sonuçlar gizli kalır (isteğe bağlı: "Sonuçları gör" bağlantısı). Oy veren kullanıcı seçimini değiştirebilir.
3. **Anket oluştur `/olustur`** — Soru alanı, başlangıçta 2 seçenek input'u, "+ Seçenek ekle" (maks. 5), seçenek silme (min. 2), karakter sayaçları. Giriş yoksa `/giris?next=/olustur`.
4. **Giriş `/giris`** ve **Kayıt `/kayit`** — Basit formlar, satır içi hata mesajları. Kayıt formunda: kullanıcı adı, e-posta, parola.
5. **Tek anket `/anket/<id>`** — Paylaşılabilir bağlantı (Faz 5; kart + "Bağlantıyı kopyala").
6. Boş durum, yükleniyor ve hata durumları için kullanıcı dostu Türkçe mesajlar.

Tüm arayüz metinleri **Türkçe**.

---

## 7. Tasarım Yönergesi

**His:** Genç, enerjik, temiz. **Açık arka plan**, üstüne **canlı renk tonları**. Bol boşluk, yuvarlak köşeler, hafif gölgeler, oyunsu ama okunaklı.

**Tasarım token'ları** (`static/css/tokens.css`):
```css
:root {
  --bg: #FAF8FF;            /* çok açık lavanta-beyaz */
  --surface: #FFFFFF;
  --text: #1E1B2E;
  --muted: #6B6880;
  --primary: #6C4DFF;       /* canlı mor */
  --primary-soft: #ECE8FF;
  --accent-pink: #FF5C93;
  --accent-yellow: #FFC83D;
  --accent-teal: #1FD1B3;
  --accent-orange: #FF8A3D;
  --border: #E7E3F5;
  --radius: 16px;
  --shadow: 0 6px 20px rgba(108, 77, 255, 0.10);
  --font: "Poppins", "Inter", system-ui, sans-serif;
}
```
- Her seçenek çubuğu sırayla farklı bir canlı renk alır (mor, pembe, sarı, turkuaz, turuncu); sarı üzerinde koyu metin kullan.
- Birincil butonlar mor dolgu, hover'da hafif yükselme + gölge. Geçişler 150–200 ms.
- Google Fonts'tan Poppins (veya Inter) kullanılabilir.
- **Mobil öncelikli**, tek sütun; masaüstünde max ~640px ortalanmış akış.
- Erişilebilirlik: yeterli kontrast, odak halkası görünür, butonlar gerçek `<button>`, yüzde çubuklarında `aria` metni.
- Emoji/ikon kullanımı ölçülü ve neşeli olabilir (örn. 🤔 logo).

---

## 8. Güvenlik ve Kalite Kontrol Listesi

- [ ] `DEBUG` ortam değişkeninden gelir, üretimde `False`.
- [ ] `ALLOWED_HOSTS` ve `CSRF_TRUSTED_ORIGINS` Vercel alan adını içerir.
- [ ] Üretimde `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT` ayarlı.
- [ ] Kullanıcı girdisi DOM'a `textContent` ile yazılır; `innerHTML` ile ham kullanıcı verisi **asla** basılmaz (XSS).
- [ ] E-posta hiçbir API yanıtında / şablonda dışarı sızmaz.
- [ ] Giriş zorunlu endpoint'ler 401 döner; sahiplik kontrolü olan işlemler 403 döner.
- [ ] Hatalı kullanıcı adı/parola mesajı hangisinin yanlış olduğunu açıklamaz.
- [ ] Gizli bilgiler repoda yok.
- [ ] Temel birim testleri: seçenek sayısı sınırı (1 ve 6 reddedilir), giriş yapmış kullanıcının çift oyu güncelleme olarak çalışır, e-posta yanıtta yok, anonim anket oluşturma 401.

---

## 9. Fazlar

Her faz: **hedef → yapılacaklar → kabul kriterleri**. Bir faz bitmeden sonrakine geçme.

### Faz 0 — Proje iskeleti ve bağlantılar
**Hedef:** Boş ama çalışan Django projesi, Supabase'e bağlı, Vercel'e deploy edilebilir.
- Django projesini (`config`) ve `accounts`, `polls` uygulamalarını oluştur.
- `requirements.txt`: `django`, `psycopg[binary]`, `dj-database-url`, `python-dotenv`, `whitenoise`.
- `settings.py`: ortam değişkenleri, `DATABASE_URL` ile Postgres (pooler uyumlu ayarlar), whitenoise, Türkçe dil/`Europe/Istanbul` saat dilimi, `AUTH_USER_MODEL = "accounts.User"` (**ilk migration'dan önce!**).
- `.env.example`, `.gitignore`, `vercel.json`, `config/wsgi.py` Vercel uyumu.
- `base.html` + `tokens.css` + `app.css` ile "Merhaba Kararsızım" sayfası.
- **Kabul:** `python manage.py runserver` ile ana sayfa açılır; `migrate` Supabase'e başarıyla uygulanır; Vercel'e deploy edildiğinde sayfa açılır. README'ye kurulum adımları yazılır.

### Faz 1 — Kullanıcı hesapları
**Hedef:** Kayıt, giriş, çıkış çalışır.
- Özel `User` modeli (case-insensitive benzersiz kullanıcı adı, benzersiz e-posta).
- `/api/auth/*` endpoint'leri, `/giris` ve `/kayit` sayfaları, `auth.js`.
- Header'da giriş durumu (`/api/auth/me/` ile).
- **Kabul:** Kayıt olunca otomatik giriş yapılır; hatalı girdilerde alan bazlı Türkçe hata görünür; e-posta veya kullanıcı adıyla giriş çalışır; çıkış çalışır.

### Faz 2 — Anket modeli ve akışı (sadece okuma)
**Hedef:** Anketler listelenir.
- `Poll`, `Option`, `Vote` modelleri + migration.
- `GET /api/polls/` ve `GET /api/polls/<id>/` (sayfalama, oy sayıları, yüzdeler).
- Ana sayfada kart akışı (`feed.js`), boş durum, "daha fazla yükle".
- Test için `seed_polls` management komutu (5–6 örnek anket, `ali_k` gibi demo kullanıcılar).
- **Kabul:** Seed sonrası ana sayfada anketler görünür; N+1 sorgu yok; e-posta sızmaz.

### Faz 3 — Oy verme
**Hedef:** Herkes oy verebilir, sonuçlar canlı güncellenir.
- `POST /api/polls/<id>/vote/` (giriş yapmış: tek oy + değiştirme; anonim: `user=NULL`).
- `vote.js`: oy sonrası kart sonuç görünümüne geçer; `localStorage` ile anonim tekrar oy engeli; giriş yapmış kullanıcı için `my_vote` ile durum.
- Yüzde çubuğu animasyonu.
- **Kabul:** Anonim ve giriş yapmış kullanıcı oy verebilir; sayfa yenilenince durum korunur; farklı anketin seçeneğiyle oy verme reddedilir.

### Faz 4 — Anket oluşturma
**Hedef:** Üyeler anket açabilir.
- `POST /api/polls/` (doğrulamalar bölüm 5'teki gibi, atomik).
- `/olustur` sayfası (`create.js`): dinamik seçenek ekle/sil (2–5), sayaçlar, istemci + sunucu doğrulaması.
- Girişsiz erişimde `/giris?next=...` yönlendirmesi; giriş sonrası geri dönüş.
- Oluşturulunca ana sayfaya yönlendir, yeni anket en üstte görünür.
- **Kabul:** 2 altı / 5 üstü seçenek hem arayüzde hem API'de engellenir; anonim POST 401 döner; anket yazarı olarak sadece kullanıcı adı görünür.

### Faz 5 — Cila, paylaşım ve yayın
**Hedef:** Prototip demo'ya hazır.
- Tek anket sayfası `/anket/<id>` + "Bağlantıyı kopyala".
- Yazarın kendi anketini silmesi (`DELETE`, onay penceresi).
- Yükleniyor/hata/boş durum cilaları, mobil kontroller, erişilebilirlik gözden geçirme, 404 sayfası.
- Güvenlik kontrol listesi (bölüm 8) ve temel testler.
- Vercel üretim ortam değişkenleri ve üretim deploy'u; README'yi güncelle.
- **Kabul:** Bölüm 8'deki tüm maddeler işaretli; canlı URL'de uçtan uca akış çalışır (kayıt → anket aç → başka tarayıcıdan oy ver).

### Faz 6+ — Sonraki adımlar (şimdi yapma, sadece fikir)
Anket bitiş süresi, yorumlar, kategori/etiketler, arama, raporlama/moderasyon, e-posta doğrulama ve parola sıfırlama, rate limiting, anonim oy için daha sağlam (ama gizlilik dostu) tekrar engelleme, "karışık sonuç" paylaşım kartları.

---

## 10. Claude Code İçin Çalışma Kuralları

1. Her fazın başında kısa bir plan çıkar, sonra uygula; faz sonunda neyin yapıldığını ve kabul kriterlerinin durumunu özetle.
2. Kapsam dışına çıkma; yeni kütüphane eklemeden önce gerekçeni söyle. Frontend'e framework/build aracı **ekleme**.
3. Kod stili: Python için PEP 8, anlamlı isimler; JS'te `const/let`, ES modülü veya düz script, bağımlılık yok. Kod ve yorumlar İngilizce, **arayüz metinleri Türkçe**.
4. Veritabanına dokunan işlemlerde (migrate, seed) önce hangi veritabanına bağlı olduğunu doğrula; Supabase'de mevcut tabloları silme/yeniden oluşturma.
5. Gizli bilgileri sohbete yazdırma, repoya koyma.
6. Belirsiz bir durumda varsayım yapıp ilerlemek yerine kısa bir soru sor; ama küçük kararlarda bu dosyadaki varsayılanları kullan.
7. Her fazın sonunda uygulamayı çalıştırıp ilgili akışı gerçekten dene (tarayıcıda ya da `curl` ile).

---

## 11. Hazır Başlangıç Promptları

Aşağıdakileri sırayla, her seferinde **bir tanesini** Claude Code'a ver.

**Faz 0**
```
KARARSIZIM_PLAN.md dosyasını baştan sona oku. Sadece "Faz 0"ı uygula: Django iskeleti, accounts ve polls uygulamaları, özel User modeli için AUTH_USER_MODEL ayarı (ilk migration'dan önce), Supabase Postgres bağlantısı (DATABASE_URL, pooler uyumlu ayarlar), whitenoise, vercel.json, .env.example, .gitignore ve "Merhaba Kararsızım" sayfası. Sonraki fazlara dokunma. Bitince Faz 0 kabul kriterlerini tek tek kontrol edip raporla; Supabase bağlantı bilgisini benden iste, tahmin etme.
```

**Faz 1**
```
KARARSIZIM_PLAN.md'yi oku. Faz 0 tamam. Sadece "Faz 1"i uygula: özel User modeli (case-insensitive benzersiz kullanıcı adı, benzersiz e-posta), /api/auth/* endpoint'leri, /giris ve /kayit sayfaları, auth.js ve header'daki giriş durumu. Bölüm 7'deki tasarım token'larına uy. Bitince kabul kriterlerini dene ve raporla.
```

**Faz 2**
```
KARARSIZIM_PLAN.md'yi oku. Faz 1 tamam. Sadece "Faz 2"yi uygula: Poll/Option/Vote modelleri ve migration, GET /api/polls/ ve /api/polls/<id>/, ana sayfada anket kartı akışı, seed_polls komutu. N+1 sorgu olmasın, e-posta hiçbir yanıtta yer almasın. Bitince raporla.
```

**Faz 3**
```
KARARSIZIM_PLAN.md'yi oku. Faz 2 tamam. Sadece "Faz 3"ü uygula: oy verme endpoint'i ve vote.js. Giriş yapmış kullanıcı için tek oy + değiştirme, anonim için user=NULL ve sadece localStorage tabanlı tekrar engelleme (sunucuda IP/parmak izi YOK). Yüzde çubuğu animasyonu ekle. Bitince raporla.
```

**Faz 4**
```
KARARSIZIM_PLAN.md'yi oku. Faz 3 tamam. Sadece "Faz 4"ü uygula: POST /api/polls/ (2–5 seçenek doğrulaması, atomik), /olustur sayfası ve create.js, girişsiz kullanıcı için /giris?next= yönlendirmesi. Bitince 1 ve 6 seçenekli geçersiz istekleri ve anonim isteği deneyip sonuçları raporla.
```

**Faz 5**
```
KARARSIZIM_PLAN.md'yi oku. Faz 4 tamam. Sadece "Faz 5"i uygula: tek anket sayfası ve bağlantı kopyalama, anket silme, UI cilaları, bölüm 8 güvenlik listesi ve temel testler, Vercel üretim deploy'u ve README. Kontrol listesini madde madde işaretleyerek raporla.
```

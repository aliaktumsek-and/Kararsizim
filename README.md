# Kararsızım 🤔

Kararsız kaldığın konularda kısa anketler aç, başkaları oylayarak yardım etsin.

Python 3.14 + Django 6.1 + Supabase (PostgreSQL) + vanilla HTML/CSS/JS, Vercel üzerinde çalışır.
Proje planı ve kurallar: [`CLAUDE.md`](CLAUDE.md) (kaynak: `docs/KARARSIZIM_PLAN.md`).

**Canlı adres:** https://kararsizim-sigma.vercel.app

## Özellikler

- Üye olmadan anketleri görme ve oy verme; anket oluşturmak için kayıt/giriş gerekir (e-posta + kullanıcı adı + parola).
  Anketlerde yalnızca kullanıcı adı görünür, e-posta hiçbir yerde paylaşılmaz.
- 2–5 seçenekli anketler. Üyeler oyunu değiştirebilir; anonim oy tarayıcıda (`localStorage`) tekrar oy vermeye karşı korunur, sunucuda izleme yoktur.
- Akış sekmeleri: **Yeni**, **Popüler** (oy sayısına göre), **Kapananlar**.
- Anketler oluşturulduktan **2 saat sonra kendiliğinden kapanır**; yazar daha önce de kapatabilir. Kapalı ankete oy verilemez, sonuçlar herkese açıktır.
  Kapanma durumu zaman damgalarından hesaplanır (arka plan görevi yoktur).
- Yazar kendi anketini silebilir. Her anketin paylaşılabilir bir sayfası vardır (`/anket/<id>/`).
- Demo veri: `python manage.py seed_polls` (temizlemek için `--clear`).

## Testler

```powershell
$env:DATABASE_URL = "sqlite://:memory:"; $env:DEBUG = "True"
python manage.py test
```

Testler Supabase'e değil bellekteki SQLite'a bağlanır (Supabase pooler test veritabanı oluşturamaz).

## Yerel kurulum (Windows / PowerShell)

```powershell
# 1. Sanal ortam ve bağımlılıklar (Python 3.14)
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Ortam değişkenleri
copy .env.example .env
# .env dosyasını açıp SECRET_KEY ve DATABASE_URL değerlerini doldur
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 3. Veritabanı (Supabase'e doğrudan uygulanır)
python manage.py showmigrations   # önce doğru veritabanına bağlı olduğunu doğrula
python manage.py migrate

# 4. Çalıştır
python manage.py runserver
```

Tarayıcıda http://127.0.0.1:8000 adresini aç.

macOS / Linux için: `source .venv/bin/activate` ve `cp .env.example .env`.

### Supabase bağlantı adresi

Supabase panelinde **Connect → Transaction pooler** (port **6543**) adresini kopyala ve
`[YOUR-PASSWORD]` yerine veritabanı şifreni yazarak `.env` içindeki `DATABASE_URL`'e koy.
Şifreyi bilmiyorsan: **Project Settings → Database → Reset database password**.

Pooler (transaction mode) için gerekli ayarlar `config/settings.py`'de hazır:
`CONN_MAX_AGE = 0`, `DISABLE_SERVER_SIDE_CURSORS = True`, `prepare_threshold = None`, `sslmode=require`.

## Ortam değişkenleri

| Değişken | Zorunlu | Açıklama |
|---|---|---|
| `SECRET_KEY` | Üretimde evet | Django gizli anahtarı |
| `DEBUG` | Hayır | Yerelde `True`, üretimde `False` (varsayılan `False`) |
| `DATABASE_URL` | Evet | Supabase transaction pooler adresi |
| `ALLOWED_HOSTS` | Hayır | Virgülle ayrılmış ek alan adları (`*.vercel.app` üretimde otomatik kabul edilir) |
| `CSRF_TRUSTED_ORIGINS` | Hayır | Virgülle ayrılmış ek origin'ler, örn. `https://kararsizim.com` |

## Vercel'e deploy

1. Repoyu GitHub'a gönder.
2. Vercel'de **Add New → Project** ile repoyu içe aktar. Framework otomatik olarak Django algılanır
   (`manage.py` → `config.wsgi.application`); `collectstatic` build sırasında Vercel tarafından çalıştırılır.
3. **Settings → Environment Variables** altına `SECRET_KEY`, `DATABASE_URL` ekle (`DEBUG` ekleme ya da `False` yap).
4. **Settings → Deployment Protection** altında **Vercel Authentication**'ı kapat; açık kalırsa site herkese değil
   yalnızca Vercel hesabı olanlara açılır.
5. Deploy et. Fonksiyon bölgesi `vercel.json` ile Supabase'e yakın olsun diye `fra1` (Frankfurt).

Sık karşılaşılan hatalar:

- *`SECRET_KEY environment variable is required`* → `SECRET_KEY` tanımlı değil; ekledikten sonra yeniden deploy et.
- *`DATABASE_URL` ayrıştırılamıyor* → adreste `[ ]`, tırnak veya şifrede `# / ? @` gibi özel karakter var; sade bir şifre kullan.
- *Bad Request (400)* → alan adı `ALLOWED_HOSTS`'ta yok (Vercel'in atadığı `*.vercel.app` adresleri zaten kabul edilir).

> Migration'lar Vercel build'inde **çalışmaz**; model değişikliklerinden sonra yerelde `python manage.py migrate` çalıştır.

## Proje yapısı

```
config/      Django ayarları, URL'ler, WSGI
accounts/    Özel User modeli ve kimlik doğrulama
polls/       Anketler, oylar, kapatma ve API
templates/   HTML şablonları
static/      CSS (tasarım token'ları) ve JS
docs/        Proje planı
```

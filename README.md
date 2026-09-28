# Optik Form Okuyucu

## Yerel çalıştırma

```bash
./start.sh
```

Backend 8000, arayüz http://localhost:5173 portunda açılır. Şifreli denemek için `ADMIN_PASSWORD=... ./start.sh`. İlk çalıştırmada Python ortamı ve npm
paketleri otomatik kurulur (Python 3.9+, Node 20+ gerekir). Ctrl+C ikisini de kapatır.

Testler:

```bash
cd backend && ../.venv/bin/python -m pytest
```

## Dokploy'da yayınlama

1. Projeyi bir git deposuna gönderin (GitHub/GitLab/Gitea). `samples/` gerçek öğrenci verisi
   içerdiğinden depoya eklemeyin (`.gitignore` içinde).
2. Dokploy'da **Create Service → Compose** seçin, depo ve dalı bağlayın; compose yolu
   `docker-compose.yml`.
3. İnternete açık kurulumda **Environment** bölümüne `ADMIN_PASSWORD=<güçlü bir şifre>` ekleyin;
   uygulamanın tamamı bu şifreyle korunur. Yalnız yerel ağda çalışacaksa boş bırakılabilir (şifresiz).
4. **Domains** bölümünde alan adını `frontend` servisine, **80** portuna bağlayın (HTTPS: Let's Encrypt).
5. **Deploy**. İlk derleme 3-5 dk sürer (OpenCV + Node build).

Notlar:
- `dokploy-network` Dokploy'un kendi ağıdır; alan adı yönlendirmesi için `frontend` bu ağa bağlıdır.
- Veriler `appData` volume'unda: `/data/forms` (şablonlar, referans görseller) ve `/data/jobs`
  (okuma görselleri, `JOB_TTL_HOURS` sonra silinir). Yeniden dağıtımda korunur.
- Paketle gelen şablonlar (`backend/omr/forms/*.json`) volume'da yoksa ilk açılışta kopyalanır;
  referans görselleri editörden "Referans görsel yükle" ile ekleyin.
- Backend tek worker çalışır (iş durumu bellekte). Yeniden başlatınca bitmemiş işler kaybolur.
- Giriş: tek yönetici şifresi (`ADMIN_PASSWORD`), oturum çerezi 30 gün. 8 yanlış denemede IP 5 dk kilitlenir.
  Şifreyi değiştirmek tüm oturumları düşürür. `ADMIN_PASSWORD` verilmezse uygulama açık çalışır (yerel ağ).
- Yükleme boyutu sınırı yok (nginx `client_max_body_size 0`); büyük PDF'ler 30 dk zaman aşımıyla işlenir.

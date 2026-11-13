# MVP doğrulama sayfası

Python 3.12+ ve Node.js 20.9+ gerekir. Graf verisi depodaki `knowledge/` klasöründen okunur; yerel geliştirme klasöründeki `data/graph/` varsa o kullanılır.

API'yi başlatın:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload
```

İkinci terminalde Next.js sayfasını başlatın:

```powershell
cd frontend
npm install
npm run dev
```

Sayfa `http://localhost:3000` adresindedir. HS6 örneği `850760`; API uç noktası `/api/hs/850760`. API `graph.pkl` dosyasını açılışta yükler. Kaynak graf değiştiyse Pydantic ile doğrulanmış grafı üretip 5.615 HS6 sorgusunun 50 ms altı kontrolünü çalıştırmak için `.venv\Scripts\python -m app.schemas.hs_graph` komutunu kullanın.

GRI sınıflandırma çağrısı Google AI Studio kullanır. API terminalinde anahtar ve model adını ortam değişkeni olarak ayarlayın; anahtarı repoya veya `.env` dosyasına commit etmeyin:

```powershell
$env:GEMINI_API_KEY = "<Google AI Studio API key>"
# İsteğe bağlı: varsayılan gemini-2.5-pro'dur.
$env:GEMINI_MODEL = "gemini-2.5-pro"
```

Sonra API sürecini yeniden başlatıp sayfadaki **GRI ile sınıflandır** düğmesini kullanın. API anahtarı yoksa `/api/classify` 503 döndürür; sahte sınıflandırma üretmez. Görselde istenen `gemini-2.5-pro` modelinin hesabınızda kullanılabildiğini doğrulayın; Google yeni projeler için güncel modelleri öneriyor. FTA değerlendirmesinde `rule_source_verified=true` resmi kuralın çağıran tarafından kontrol edildiğini belirtir; bu işaret olmadan sonuç `insufficient_data` kalır.

Başka bir API adresine yayınlarken Next.js derleme ortamında `FASTAPI_URL` değişkenini API'nin tam adresine ayarlayın. Bu prototip e-posta adreslerini yerel SQLite dosyasına kaydeder; herkese açık kullanım öncesi kalıcı veritabanı ve gizlilik metni yapılandırılmalıdır.

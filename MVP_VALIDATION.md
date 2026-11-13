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

Sayfa `http://localhost:3000` adresindedir. HS6 örneği `850760`; API uç noktası `/api/hs/850760`.

GRI sınıflandırma çağrısı Google AI Studio kullanır. API terminalinde anahtar ve model adını ortam değişkeni olarak ayarlayın; anahtarı repoya veya `.env` dosyasına commit etmeyin:

```powershell
$env:GEMINI_API_KEY = "<Google AI Studio API key>"
$env:GEMINI_MODEL = "<enabled Gemini model id>"
```

Sonra API sürecini yeniden başlatıp sayfadaki **GRI ile sınıflandır** düğmesini kullanın. Gemini ayarı yoksa `/api/classify` 503 döndürür; sahte sınıflandırma üretmez. FTA ve monte/demonte uç noktaları yalnızca kullanıcı tarafından sağlanan kural/kanıtlarla değerlendirme yapar.

Başka bir API adresine yayınlarken Next.js derleme ortamında `FASTAPI_URL` değişkenini API'nin tam adresine ayarlayın. Bu prototip e-posta adreslerini yerel SQLite dosyasına kaydeder; herkese açık kullanım öncesi kalıcı veritabanı ve gizlilik metni yapılandırılmalıdır.


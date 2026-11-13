# TarifeLab — HS/GTİP sınıflandırma prototipi

## Tek sınıflandırma sözleşmesi

`app/schemas/classification.py` bütün sınıflandırma yanıtlarının Pydantic v2 modelidir. JSON Schema çıktısı `schemas/classification_response.schema.json` dosyasına `.venv\Scripts\python -m app.schemas.classification` komutuyla üretilir. Eski `ClassificationResponse.txt` taslağı bu sözleşmeye dönüştürülmüştür; uygulama ve prompt artık generated şemayı kullanır.

`gri_system_prompt.md`, `/api/classify` içinde Google AI Studio çağrısının sistem promptudur. İstekler önce 5–8 HS terimine genişletilir, en fazla beş aday aranır ve model yanıtı Pydantic sözleşmesiyle doğrulanır. HS6 kodu aday listesi ve bilgi grafiğiyle tekrar kontrol edilir. Model varsayılanı görseldeki `gemini-2.5-pro` değeridir; `GEMINI_MODEL` ile değiştirilebilir. Google yeni projelerde daha güncel modelleri önerdiğinden 2.5 Pro erişimini API anahtarınızla doğrulayın. Sınıflandırma için `GEMINI_API_KEY` gerekir.

## Uç noktalar

- `POST /api/classify`: ürün olgularından GRI 1–6 analizi ve canonical JSON yanıtı.
- `GET /api/contracts/classification-response`: aynı Pydantic modelinden üretilen JSON Schema.
- `GET /api/hs/{code}`: fasıl, pozisyon ve bilgi grafiğindeki hariç tutma kuralları.
- `POST /api/tariff-engineering/compare`: monte/demonte oran karşılaştırması ve GRI 2(a) inceleme kapısı.
- `POST /api/fta/evaluate`: çağıranın resmi kaynağını doğruladığını açıkça belirtmesi halinde, yürürlük tarihi verilen FTA şartlarını BOM/menşe kanıtıyla değerlendirir. Kaynak doğrulama işareti yoksa sonuç `insufficient_data` kalır.

## Çalıştırma

Python 3.12+ ve Node.js 20.9+ gerekir. API:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m uvicorn app.main:app --reload
```

Next.js arayüzü ayrı terminalde:

```powershell
cd frontend
npm install
npm run dev
```

FAISS indeksini ve Harvard sınıflandırıcısını kullanmak için `.venv\Scripts\python -m pip install -e ".[search]"`, Atlas bağlantı değişkenleri ve `data/intermediate/hs12_4_index.parquet` gerekir. Bunlar yoksa arama 375 kodluk örnek tarife tablosuna düşer; örnek veri resmi sınıflandırma kaynağı değildir.

## Veri kapsamı ve sınırlar

- HSBench düğüm, taksonomi ve hariç tutma verileri Pydantic v2 ile doğrulanır; API başlangıcında `graph.pkl` yüklenir ve kaynak JSON ile düğüm/kenar tutarlılığı denetlenir. Kaynak grafik Çincedir. Upstream depoda lisans dosyası bulunmadığından graf verisini yeniden dağıtma hakkı teyit edilmelidir.
- HSBench kaynağında bazı 4 haneli pozisyon → 6 haneli alt pozisyon kenarları yoktur. Grafik üreticisi bu standart HS kod öneklerinden ebeveyn kenarlarını ekler; tüm 5.615 HS6 düğümü için fasıl/pozisyon yolu sorgulanıp 50 ms sınırı denetlenir.
- `data/tariffs/hs6-tariff-sample.csv` 375 örnek HS6 satırıdır; oranlar 2026-08-03 tarihinde doğrulanmıştır, canlı tarife API'si değildir. Kodun 8–12 haneli ulusal uzantıları mevcut veriyle doğrulanamaz ve `null` kalır.
- GenPark reposundaki tasarruf aritmetiği kullanılır. Orijinal depoda uygulanabilir FTA kural tablosu yoktur; menşe motoru burada anlaşma adı, resmi kural metni/kaynağı, yürürlük tarihi ve BOM kanıtı verilmeden uygunluk kararı üretmez.
- GRI 2(a) olguları demonte sunumda farklı vergi oranı önermekten önce incelenir. Aday kodlar resmi kaynakla doğrulanmamışsa tahmini tasarruf gösterilmez.
- Ürün URL'si açılmaz; yalnız görünen yol/metin kullanılır. Erken erişim e-postası yerel SQLite dosyasına kaydedilir. Kamuya açık kullanım için resmi tarife kaynakları, kalıcı veri tabanı, gizlilik metni ve servis dağıtımı yapılandırılmalıdır.

## Kaynak repolar

- HSBench: `data/graph/` ve `.sources/HSBench/knowledge/`.
- Harvard `hscode-mapping`: `core/search/hs_classifier/` ve `core/search/language.py`.
- GenPark savings arithmetic: `core/tariff_engine/savings.py`; deterministic FTA and GRI 2(a) scenario evaluation: `core/tariff_engine/`.
- `hs-code-lookup`: `core/duty_lookup/` ve `data/tariffs/`.


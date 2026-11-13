"use client";

import { useState } from "react";

export default function Home() {
  const [query, setQuery] = useState("");
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState("");
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [accessStatus, setAccessStatus] = useState("");
  const [hsCode, setHsCode] = useState("");
  const [hsResult, setHsResult] = useState(null);
  const [hsError, setHsError] = useState("");
  const [busy, setBusy] = useState(false);

  async function showPreview(event) {
    event.preventDefault(); setBusy(true); setPreviewError(""); setPreview(null);
    try {
      const response = await fetch("/api/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Önizleme alınamadı.");
      setPreview(data);
    } catch (error) { setPreviewError(error.message); }
    finally { setBusy(false); }
  }

  async function showHsContext(event) {
    event.preventDefault(); setBusy(true); setHsError(""); setHsResult(null);
    try {
      const response = await fetch(`/api/hs/${encodeURIComponent(hsCode)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "HS kodu bulunamadı.");
      setHsResult(data);
    } catch (error) { setHsError(error.message); }
    finally { setBusy(false); }
  }

  async function joinEarlyAccess(event) {
    event.preventDefault(); setAccessStatus("");
    try {
      const response = await fetch("/api/early-access", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, consent }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Kayıt yapılamadı.");
      setAccessStatus(data.message); setEmail(""); setConsent(false);
    } catch (error) { setAccessStatus(error.message); }
  }

  return (
    <>
      <header className="topbar"><a className="brand" href="#">TARİFE<span>LAB</span></a><span className="pill">Açıklanabilir GTİP · Erken erişim</span></header>
      <main>
        <section className="hero">
          <div className="intro">
            <p className="eyebrow">Amazon FBA satıcıları ve gümrük müşavirleri için</p>
            <h1>Ürününüzü tarifede doğru yere oturtun.</h1>
            <p className="lede">Ürün bağlantınızı bırakın veya altı haneli HS kodunu sorgulayın. Fasıl, pozisyon ve hariç tutma notlarını kaynak veriden birlikte görün.</p>
            <p className="fine">Bu MVP doğrulama prototipidir; ürün bağlantısını açmaz ve resmi GTİP kararı vermez.</p>
          </div>
          <section className="card">
            <form onSubmit={showPreview}>
              <label htmlFor="query">Amazon ürün bağlantısı veya ürün açıklaması</label>
              <textarea id="query" value={query} onChange={e => setQuery(e.target.value)} maxLength={2000} required placeholder="Örn. stainless steel insulated water bottle, 750 ml" />
              <p className="hint">Bağlantıda yalnızca URL metni kullanılır; sayfa sunucudan ziyaret edilmez.</p>
              <button className="primary" disabled={busy}>{busy ? "Kontrol ediliyor…" : "Önizleme iste"} <span aria-hidden="true">→</span></button>
            </form>
            {previewError && <p className="error" role="alert">{previewError}</p>}
            {preview && <div className="results" aria-live="polite"><p className="notice">{preview.notice}</p>{preview.candidates.length ? preview.candidates.map(item => <article className="candidate" key={item.code}><strong>HS {item.code}</strong><p>{item.description}</p><div className="rates">{Object.entries(item.rates).map(([country, rate]) => <span key={country}>{country}: {rate === null ? "veri yok" : `${rate}%`}</span>)}</div><small>Örnek veri doğrulama tarihi: {item.verified}</small></article>) : <p className="hint">Örnek tarifede eşleşme bulunamadı. İngilizce ürün adını deneyin.</p>}</div>}
            <form className="access" onSubmit={joinEarlyAccess}>
              <label htmlFor="email">Ürün hazır olduğunda haber verelim</label>
              <div className="emailrow"><input id="email" type="email" maxLength={254} value={email} onChange={e => setEmail(e.target.value)} placeholder="e-posta@örnek.com" required /><button type="submit">Erken erişim</button></div>
              <label className="consent"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} required /><span>Adresimin erken erişim bilgilendirmesi için kaydedilmesini kabul ediyorum.</span></label>
              <small className="hint">Prototipte adres yerel SQLite veritabanına kaydedilir.</small>
              <p className="status" aria-live="polite">{accessStatus}</p>
            </form>
          </section>
        </section>

        <section className="lookup card" aria-labelledby="lookup-title">
          <div><p className="eyebrow">Faz 0 kalite kapısı</p><h2 id="lookup-title">Altı haneli HS yolunu doğrulayın</h2><p className="hint">Fasıl, pozisyon ve bu hiyerarşi yolundaki tüm hariç tutma notları bellekteki graf üzerinden aranır.</p></div>
          <form className="lookupform" onSubmit={showHsContext}>
            <label htmlFor="hs-code">HS6 kodu</label><div className="emailrow"><input id="hs-code" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={hsCode} onChange={e => setHsCode(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="850760" required /><button disabled={busy}>{busy ? "Aranıyor…" : "Kodu sorgula"}</button></div>
          </form>
          {hsError && <p className="error" role="alert">{hsError}</p>}
          {hsResult && <div className="hsresult" aria-live="polite">
            <div className="quality"><strong>{hsResult.within_50ms ? "Kalite kapısı geçti" : "50 ms hedefi aşıldı"}</strong><span>{hsResult.query_ms} ms · {hsResult.exclusion_count} hariç tutma · kaynak dili: Çince</span></div>
            <div className="pathgrid"><article><small>FASIL · {hsResult.chapter.code}</small><p>{hsResult.chapter.description}</p></article><article><small>POZİSYON · {hsResult.heading.code}</small><p>{hsResult.heading.description}</p></article></div>
            <h3>Hariç tutma notları</h3>
            {hsResult.exclusions.length ? <ul className="exclusions">{hsResult.exclusions.map((item, index) => <li key={`${item.source_code}-${item.target_code}-${index}`}><b>{item.source_code} → {item.target_code}</b><span>{item.condition}</span></li>)}</ul> : <p className="hint">Bu hiyerarşi yolunda kayıtlı hariç tutma notu yok.</p>}
          </div>}
        </section>

        <section className="steps" aria-label="Nasıl çalışır"><article><b>01 · Ürünü tanımlayın</b><p>Ürün bağlantısı veya malzeme ve kullanım açıklaması girin.</p></article><article><b>02 · Gerekçeyi inceleyin</b><p>HS6 sorgusunda fasıl, pozisyon ve ilgili istisna notlarını görün.</p></article><article><b>03 · Uzmanla doğrulayın</b><p>Kaynak graf Çincedir; gerçek ithalat kararını güncel ulusal tarife ve müşavirle doğrulayın.</p></article></section>
      </main>
      <footer>Ürün URL’leri sunucuda açılmaz. Ürün önizlemesi örnek tarifede İngilizce metin eşleşmesidir. HS grafiği resmi hukuki karar veya Türkiye GTİP 10/12 hane doğrulaması değildir.</footer>
    </>
  );
}


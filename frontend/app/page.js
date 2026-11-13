"use client";

import { useState } from "react";

export default function Home() {
  const [query, setQuery] = useState("");
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState("");
  const [classification, setClassification] = useState(null);
  const [classificationError, setClassificationError] = useState("");
  const [materials, setMaterials] = useState("");
  const [primaryFunction, setPrimaryFunction] = useState("");
  const [packaging, setPackaging] = useState("");
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

  async function classifyProduct() {
    setBusy(true); setClassificationError(""); setClassification(null);
    try {
      const response = await fetch("/api/classify", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_description: query,
          material_composition: materials.split(/[;,\n]/).map(value => value.trim()).filter(Boolean),
          primary_function: primaryFunction || null,
          form_and_packaging: packaging || null,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "GRI analizi tamamlanamadı.");
      setClassification(data);
    } catch (error) { setClassificationError(error.message); }
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
            <div className="gri-inputs">
              <label htmlFor="materials">Malzemeler ve oranları (biliniyorsa)</label>
              <input id="materials" value={materials} onChange={e => setMaterials(e.target.value)} placeholder="Örn. çelik %70; plastik %30" />
              <label htmlFor="function">Temel işlev / kullanım amacı</label>
              <input id="function" value={primaryFunction} onChange={e => setPrimaryFunction(e.target.value)} placeholder="Ürün ne yapar?" />
              <label htmlFor="packaging">İthalattaki sunuluş şekli</label>
              <input id="packaging" value={packaging} onChange={e => setPackaging(e.target.value)} placeholder="Örn. monte, demonte, perakende set" />
              <button type="button" className="primary" disabled={busy || query.trim().length < 3} onClick={classifyProduct}>{busy ? "GRI inceleniyor…" : "GRI ile sınıflandır"}</button>
            </div>
            {previewError && <p className="error" role="alert">{previewError}</p>}
            {preview && <div className="results" aria-live="polite"><p className="notice">{preview.notice}</p>{preview.candidates.length ? preview.candidates.map(item => <article className="candidate" key={item.code}><strong>HS {item.code}</strong><p>{item.description}</p><div className="rates">{["US", "EU", "UK", "CN"].map(country => <span key={country}>{country}: {item.rates[country] === null ? "veri yok" : `${item.rates[country]}%`}</span>)}</div><small>Diğer pazar örnek oranları doğrulama tarihi: {item.rates.verified_on || item.verified}</small>{item.us_tariff_data.status === "available" && <ul>{item.us_tariff_data.lines.map(line => <li key={line.hts_code}>US HTS {line.hts_code}: Genel {line.general_rate || "—"}; Özel {line.special_rate || "—"}; Sütun 2 {line.column_2_rate || "—"}</li>)}</ul>}</article>) : <p className="hint">Örnek tarifede eşleşme bulunamadı. İngilizce ürün adını deneyin.</p>}</div>}
            {classificationError && <p className="error" role="alert">{classificationError}</p>}
            {classification && <section className="results" aria-live="polite">
              <p className="notice">Durum: {classification.classification_status} · Güven: {classification.final_classification.confidence_score}</p>
              {classification.hs_code_6 ? <h3>HS6: {classification.hs_code_6}{classification.hs_code_10 ? ` · Ulusal kod: ${classification.hs_code_10}` : " · Ulusal kod resmi kaynakla doğrulanmadı"}</h3> : <p className="hint">Henüz desteklenen nihai HS6 kodu yok.</p>}
              {classification.missing_information.needs_more_info && <><h3>Gerekli ek bilgiler</h3><ul>{classification.missing_information.clarification_questions.map(question => <li key={question}>{question}</li>)}</ul></>}
              <p className="hint">{classification.product_analysis.normalized_description}</p>
              {classification.candidate_headings.length > 0 && <><h3>Aday pozisyonlar</h3><ul>{classification.candidate_headings.map(item => <li key={`${item.code}-${item.status}`}><b>{item.code}</b> · {item.status} · {item.elimination_or_selection_reason}</li>)}</ul></>}
              <h3>GYK değerlendirmesi</h3><ol>{classification.gri_decision_tree.map(step => <li key={step.rule}><b>{step.rule}</b> · {step.reasoning}</li>)}</ol>
              <p className="hint">{classification.final_classification.legal_justification}</p>
              {classification.excluded_paths_reason.length > 0 && <><h3>Hariç tutma / eleme gerekçeleri</h3><ul>{classification.excluded_paths_reason.map((item, index) => <li key={`${item.code}-${index}`}><b>{item.code}</b> · {item.reason}</li>)}</ul></>}
              <h3>MFN oranları</h3><div className="rates">{["US", "EU", "UK", "CN"].map(market => <span key={market}>{market}: {classification.mfn_rates[market] === null ? "veri yok" : `${classification.mfn_rates[market]}%`}</span>)}</div>
              <p className="hint">Tarife kaynağı: {classification.mfn_rates.source}; doğrulama tarihi: {classification.mfn_rates.verified_on || "yok"}</p>
              <h3>ABD resmi HTS oranları</h3>
              {classification.us_tariff_data.status === "available" ? <><p className="hint">USITC’den alındı: {classification.us_tariff_data.retrieved_at}</p><ul>{classification.us_tariff_data.lines.map(line => <li key={line.hts_code}><b>HTS {line.hts_code}</b> · {line.description} · Genel: {line.general_rate || "—"} · Özel: {line.special_rate || "—"} · Sütun 2: {line.column_2_rate || "—"}</li>)}</ul></> : <p className="hint">{classification.us_tariff_data.message || "ABD HTS oranı alınmadı."}</p>}
              <h3>Monte / demonte</h3><p className="hint">{classification.tariff_engineering_advice.explanation}{classification.tariff_engineering_advice.potential_savings !== null ? ` Örnek hesap: ${classification.tariff_engineering_advice.potential_savings} ${classification.tariff_engineering_advice.currency}.` : ""}</p>
              <h3>FTA menşe</h3><p className="hint">{classification.fta_origin.status} · {classification.fta_origin.explanation}</p>
            </section>}
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
      <footer>Ürün URL’leri sunucuda açılmaz. GRI yerel Ollama modeliyle çalışır; Gemini isteğe bağlıdır. ABD oranları USITC’den sorgu anında alınır; AB, İngiltere ve Çin oranları örnek veridir. Sonuçlar gümrük idaresi kararı değildir.</footer>
    </>
  );
}

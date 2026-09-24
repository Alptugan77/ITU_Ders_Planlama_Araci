/* itucap — statik site çalıştırıcısı.
 *
 * Motoru (Python) tarayıcıda Pyodide ile çalıştırır. Arayüzün kendisi
 * `ui.py`'deki şablon; burada yalnız ONU BESLEYEN katman var:
 *
 *   1. Pyodide'i yükle
 *   2. Motor dosyalarını ve katalogu sanal dosya sistemine yaz
 *   3. Kullanıcının verisini IndexedDB'den geri yükle
 *   4. `server.State` kur, ilk durumu arayüze ver
 *   5. Arayüzün `api()` çağrılarını ağa değil, Python'a yönlendir
 *   6. Her yazmadan sonra kullanıcı verisini IndexedDB'ye geri kaydet
 *
 * ★ GİZLİLİK — bu dosyanın en önemli özelliği ne YAPMADIĞI:
 *   hiçbir yere istek atmıyor. `fetch` yalnız kendi statik dosyalarını
 *   (motor, katalog) çekmek için kullanılıyor; kullanıcı verisi hiçbir
 *   isteğin gövdesine girmiyor. Sunucu yok, uç yok, telemetri yok.
 */
"use strict";

/* ★★ Pyodide sürümü BURADA SABİT DEĞİL — `manifest.json`dan geliyor.
   Sürüm `tools/site_kur.py`de tek yerde duruyor.

   Sebep: 22.08.2026'da site `ModuleNotFoundError: sqlite3` ile açılmadı.
   Yerelde `pyodide@latest` ile test edilmişti, burada ise 0.28.3 yazıyordu.
   O sürümde sqlite3 stdlib'de yok — motor `import sqlite3` ile ayakta.
   Test edilen sürüm ile yayınlanan sürüm aynı olmalı; sabit iki yerde
   durdukça bir gün yine ayrışırdı. */
const cdnUrl = (v) => `https://cdn.jsdelivr.net/pyodide/v${v}/full/`;
const DB_ADI = "itucap", DEPO = "kullanici";
// Kullanıcıya ait, kalıcı olması gereken dosyalar. Katalog burada YOK:
// o herkese açık ve her açılışta yeniden indiriliyor.
const KULLANICI_DOSYALARI = [
  "/app/data/user.sqlite3",
  "/app/config/settings.toml",
  "/app/config/denklikler.toml",
];

const el = (id) => document.getElementById(id);

/* ==================================================================
   ★★ FAZ 52 — İLERLEME GERÇEK İŞİ GÖSTERİYOR.

   Ölçüm (önce, ~200 KB/s'lik bağlantı, toplam 93 sn):
     0,2 sn  %16,7  Python çalışma ortamı … 68,2 sn BOYUNCA KIPIRDAMADI
    68,4 sn  %33    Motor
    72,6 sn  %50    Ders kataloğu (14,8 sn donuk)
    88,5 sn  %100   Hesaplanıyor … %100'DEYKEN 4,7 sn daha
   Çubuk ADIM sayıyordu ve adımlar eşit değildi (68 sn ile 0,0 sn).

   Şimdi:
     · %90'ı İNEN BAYT — `fetch` sarmalayıcısı akan her parçayı sayıyor,
       beklenen boyları `manifest.json` biliyor (site_kur yazıyor),
     · %10'u biten adım,
     · bayt akmıyor ama iş sürüyorsa (derleme, hesap) kayan şerit,
     · indirme 12 sn takılırsa "sayfayı kapatma" uyarısı,
     · çubuk %100'e ancak GERÇEKTEN bitince varıyor.
   ⚠️ Beklenen boylar bilinmiyorsa (eski kurulum, CDN'den Pyodide) uydurma
   bir sayı gösterilmiyor: o zaman çubuk adım sayar, eskisi gibi.
   ================================================================== */
const ASAMALAR = ["python", "motor", "katalog", "veri", "hesap"];
const ETIKET = {
  python:  "Python çalışma ortamı indiriliyor",
  motor:   "Motor dosyaları yükleniyor",
  katalog: "Ders kataloğu indiriliyor",
  veri:    "Kayıtlı verin geri yükleniyor",
  hesap:   "Programın hesaplanıyor",
};
const PYODIDE_ADLARI = ["pyodide.js", "pyodide.asm.mjs", "pyodide.asm.wasm",
                        "python_stdlib.zip", "pyodide-lock.json"];
const IZ = {
  beklenen: {}, toplam: 0, alinan: {},
  asama: null, asamaBas: 0, biten: 0,
  t0: performance.now(), sonDegisim: performance.now(),
  pyHazirlaniyor: false, yuzde: -1, zaman: null, bitti: false,
};

function mb(n){
  return (n / 1e6).toLocaleString("tr-TR",
    {minimumFractionDigits: 1, maximumFractionDigits: 1});
}
function sn(ms){
  const s = ms / 1000;
  return s < 10
    ? s.toLocaleString("tr-TR", {maximumFractionDigits: 1}) + " sn"
    : Math.round(s) + " sn";
}

/* İsteğin yolu hangi beklenen dosya? Pyodide CDN'den gelirse yolu farklı
   (`/pyodide/v…/full/…`), o yüzden eşleme yolun SONUNA göre. */
function baytAnahtari(url){
  let yol;
  try{ yol = new URL(url, location.href).pathname; }catch(e){ return null; }
  for(const k of Object.keys(IZ.beklenen))
    if(yol === "/" + k || yol.endsWith("/" + k)) return k;
  return null;
}
function baytEkle(anahtar, n){
  const ust = IZ.beklenen[anahtar] || 0;
  // Sunucu sıkıştırıp açarsa akan bayt dosya boyunu aşabilir: tavanla.
  IZ.alinan[anahtar] = Math.min(ust, (IZ.alinan[anahtar] || 0) + n);
  IZ.sonDegisim = performance.now();
}
const alinanToplam = () =>
  Object.values(IZ.alinan).reduce((a, b) => a + b, 0);
const pyodideIndi = () => PYODIDE_ADLARI.every(k =>
  !(k in IZ.beklenen) || (IZ.alinan[k] || 0) >= IZ.beklenen[k]);

/* `fetch` sarmalayıcısı: yanıt gövdesini SAYAN bir akışa çeviriyor.
   ⚠️ Başlıklar AYNEN korunuyor — `WebAssembly.instantiateStreaming`
   `application/wasm` türünü şart koşuyor; kaybolsaydı Pyodide dosyayı
   İKİNCİ KEZ indirirdi. Yükleme bitince asıl `fetch` geri konuyor. */
const _asilFetch = window.fetch.bind(window);
window.fetch = async function(girdi, secenek){
  const res = await _asilFetch(girdi, secenek);
  /* ⚠️ Pyodide `fetch`e DİZGE değil `URL` NESNESİ veriyor. İlk sürüm
     yalnız dizge ve `Request.url` okuyordu: ölçüldü, 17,3 MB'ın yalnız
     5,2'si sayıldı, `.wasm` (9,6 MB) hiç sayılmadı ve indirme sürerken
     yanlış "takıldı" uyarısı çıktı. `String(URL)` tam adresi veriyor. */
  const url = girdi && typeof girdi === "object" && typeof girdi.url === "string"
    ? girdi.url : String(girdi || "");
  const anahtar = IZ.bitti ? null : baytAnahtari(url);
  if(!anahtar || !res.body || !res.ok ||
     (secenek && (secenek.method || "").toUpperCase() === "HEAD")) return res;
  const okuyucu = res.body.getReader();
  const akis = new ReadableStream({
    async pull(denetim){
      try{
        const {done, value} = await okuyucu.read();
        if(done){ denetim.close(); return; }
        baytEkle(anahtar, value.byteLength);
        denetim.enqueue(value);
      }catch(e){ denetim.error(e); }
    },
    cancel(neden){ return okuyucu.cancel(neden); },
  });
  return new Response(akis, {status: res.status, statusText: res.statusText,
                             headers: res.headers});
};
/* `<script>` ile gelenler (`pyodide.js`, `pyodide.asm.mjs`) akıtılamıyor;
   bitince sayılıyor. */
try{
  new PerformanceObserver(liste => {
    for(const g of liste.getEntries()){
      if(g.initiatorType === "fetch") continue;          // akıştan sayıldı
      const k = baytAnahtari(g.name);
      if(k && !(IZ.alinan[k] >= IZ.beklenen[k])) baytEkle(k, IZ.beklenen[k]);
    }
  }).observe({type: "resource", buffered: true});
}catch(e){ /* eski tarayıcı: adım kipi yine çalışır */ }

function listeOgesi(ad){
  return document.querySelector(`#yukListe li[data-a="${ad}"]`);
}
function durumYaz(metin){
  const a = el("yukAdim");
  if(a && a.textContent !== metin) a.textContent = metin;   // canlı bölge
}
function asama(ad){
  const simdi = performance.now();
  if(IZ.asama){
    const li = listeOgesi(IZ.asama);
    if(li){
      li.dataset.durum = "bitti";
      const s = li.querySelector(".sure");
      if(s) s.textContent = sn(simdi - IZ.asamaBas);
    }
    IZ.biten++;
  }
  IZ.asama = ad; IZ.asamaBas = simdi; IZ.pyHazirlaniyor = false;
  const li = listeOgesi(ad);
  if(li) li.dataset.durum = "simdi";
  durumYaz(ETIKET[ad] + "…");
  ciz();
}
function oran(){
  if(IZ.bitti) return 1;
  if(IZ.toplam > 0)
    return Math.min(0.99, 0.9 * (alinanToplam() / IZ.toplam)
                          + 0.1 * (IZ.biten / ASAMALAR.length));
  return Math.min(0.99, IZ.biten / ASAMALAR.length);
}
function ciz(){
  const simdi = performance.now();
  const kap = el("yukCubukKap"), cubuk = el("yukCubuk");
  const o = oran();
  if(cubuk) cubuk.style.width = (o * 100).toFixed(1) + "%";
  const yuzde = Math.round(o * 100);
  if(kap && yuzde !== IZ.yuzde){
    IZ.yuzde = yuzde;
    kap.setAttribute("aria-valuenow", String(yuzde));
  }
  // Python bitti mi, yoksa derleniyor mu? (bayt tamam, ortam hazır değil)
  if(IZ.asama === "python" && IZ.toplam > 0 && pyodideIndi() && !IZ.pyHazirlaniyor){
    IZ.pyHazirlaniyor = true;
    durumYaz("Python çalışma ortamı hazırlanıyor…");
  }
  const indiriyor = (IZ.asama === "python" && !pyodideIndi()) ||
                    (IZ.asama === "katalog" && IZ.toplam > 0);
  if(kap) kap.classList.toggle("calisiyor", !indiriyor && !IZ.bitti);
  const sayi = el("yukSayi");
  if(sayi){
    const gecen = sn(simdi - IZ.t0);
    sayi.textContent = IZ.toplam > 0
      ? `${mb(alinanToplam())} / ${mb(IZ.toplam)} MB · ${gecen}`
      : gecen;
  }
  // Takılma: indirirken 12 sn hiç bayt gelmediyse söyle — kullanıcı
  // "dondu" sanıp sayfayı kapatmasın.
  const uyari = el("yukUyari");
  if(uyari){
    const takildi = indiriyor && simdi - IZ.sonDegisim > 12000;
    if(takildi && uyari.hidden){
      uyari.textContent = "Bağlantı yavaş görünüyor — sayfayı açık bırak, " +
        "indirme sürüyor. İlk açılıştan sonra büyük dosyalar önbellekten gelir.";
      uyari.hidden = false;
    }else if(!takildi && !uyari.hidden){
      uyari.hidden = true;
    }
  }
}
function izlemeyiBaslat(manifest){
  const y = manifest && manifest.yuk;
  if(y && y.dosyalar && y.toplam > 0){
    IZ.beklenen = y.dosyalar;
    IZ.toplam = y.toplam;
  }
  ciz();
  IZ.zaman = setInterval(ciz, 500);
}
function izlemeyiBitir(){
  IZ.bitti = true;
  clearInterval(IZ.zaman);
  window.fetch = _asilFetch;              // sarmalayıcı yalnız yükleme için
}

/* Hata: donmuş bir ekran değil, ne olduğu + tek tıkla yeniden deneme. */
function hataGoster(err){
  izlemeyiBitir();
  const li = IZ.asama && listeOgesi(IZ.asama);
  if(li) li.dataset.durum = "hata";
  const kap = el("yukCubukKap");
  if(kap) kap.classList.remove("calisiyor");
  durumYaz("Yüklenemedi");
  const kutu = el("yukHata");
  if(!kutu) return;
  const ad = li ? li.firstChild.textContent.trim() : "yükleme";
  kutu.innerHTML = `<h2>Site açılamadı</h2>
    <p><b></b> adımında durdu. Çoğunlukla bağlantı kesintisidir — bir kez daha
      denemek yeter. Sorun sürerse aşağıdaki hatayı GitHub'da bildir.</p>
    <code></code>
    <button type="button" id="yukTekrar">Yeniden dene</button>`;
  kutu.querySelector("b").textContent = ad;             // innerHTML'e değil
  kutu.querySelector("code").textContent = String((err && err.message) || err);
  kutu.hidden = false;
  const yuk = el("yukleniyor");
  if(yuk) yuk.removeAttribute("aria-busy");
  const tekrar = el("yukTekrar");
  if(tekrar){
    tekrar.addEventListener("click", () => location.reload());
    tekrar.focus();
  }
}

/* ---------------------------------------------------------------- IndexedDB
   Neden localStorage değil: `user.sqlite3` ikili veri ve büyüyebilir;
   localStorage yalnız metin tutuyor ve ~5MB'da tıkanıyor. */
function idb(){
  return new Promise((ok, hata) => {
    const r = indexedDB.open(DB_ADI, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(DEPO);
    r.onsuccess = () => ok(r.result);
    r.onerror = () => hata(r.error);
  });
}
async function idbOku(anahtar){
  const db = await idb();
  return new Promise((ok) => {
    const r = db.transaction(DEPO, "readonly").objectStore(DEPO).get(anahtar);
    r.onsuccess = () => ok(r.result || null);
    r.onerror = () => ok(null);
  });
}
async function idbYaz(anahtar, deger){
  const db = await idb();
  return new Promise((ok, hata) => {
    const t = db.transaction(DEPO, "readwrite");
    t.objectStore(DEPO).put(deger, anahtar);
    t.oncomplete = () => ok();
    t.onerror = () => hata(t.error);
  });
}

async function idbSil(anahtar){
  const db = await idb();
  return new Promise((ok, hata) => {
    const t = db.transaction(DEPO, "readwrite");
    t.objectStore(DEPO).delete(anahtar);
    t.oncomplete = () => ok();
    t.onerror = () => hata(t.error);
  });
}

/* --------------------------------------------------------------- yükleme */
async function dosyaYaz(py, hedef, yol, ikili = false){
  const res = await fetch(yol);
  if(!res.ok) throw new Error(`${yol} alınamadı (${res.status})`);
  py.FS.writeFile(hedef, ikili
    ? new Uint8Array(await res.arrayBuffer())
    : await res.text());
}

async function katalogYukle(py, manifest){
  const res = await fetch("./" + manifest.catalog.file);
  /* Faz 60 — katalog cihazdaki kopyadan geldiyse (sw.js işaretliyor) sayfa
     bunu SÖYLEYECEK: eski kontenjanı canlıymış gibi göstermemek için. */
  if(res.headers.get("X-Itucap-Onbellek")) window.__ITUCAP_ONBELLEK__ = true;
  if(!res.ok) throw new Error("katalog alınamadı");
  let buf;
  if(typeof DecompressionStream === "function"){
    buf = await new Response(
      res.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();
  }else{
    // Eski tarayıcı: sunucu Content-Encoding ile açmış olabilir.
    buf = await res.arrayBuffer();
  }
  py.FS.writeFile("/app/data/reference.sqlite3", new Uint8Array(buf));
}

/* Kullanıcının kaydedilmiş verisini sanal diske geri koyar.
   Yoksa sessizce geçer — ilk ziyaret. */
async function kullaniciGeriYukle(py){
  let bulundu = false;
  for(const yol of KULLANICI_DOSYALARI){
    const veri = await idbOku(yol);
    if(veri == null) continue;
    py.FS.writeFile(yol, typeof veri === "string" ? veri : new Uint8Array(veri));
    bulundu = true;
  }
  return bulundu;
}

/* Yazma sonrası: değişen kullanıcı dosyalarını geri kaydet.
   ★ Katalog KAYDEDİLMİYOR — 8.7 MB'ı her seferinde IndexedDB'ye yazmak
   hem yavaş hem gereksiz; o zaten herkese açık ve yeniden indirilebilir. */
async function kullaniciKaydet(py){
  for(const yol of KULLANICI_DOSYALARI){
    let veri;
    try{ veri = py.FS.readFile(yol); }
    catch(e){ continue; }                       // dosya henüz yok
    const metin = yol.endsWith(".toml");
    await idbYaz(yol, metin ? new TextDecoder().decode(veri) : veri);
  }
}

/* ★ Faz 52: bu betik artık yükleyicinin HEMEN ARKASINDAN, `async` olarak
   geliyor — indirme HTML bitmeden başlasın diye. Arayüzün kendisi
   (`__ITUCAP_APPLY__`) sayfanın sonunda tanımlanıyor; onu beslemeden önce
   DOM'un bitmesini bekliyoruz. */
function domHazir(){
  return document.readyState === "loading"
    ? new Promise(ok => document.addEventListener("DOMContentLoaded", ok,
                                                  {once: true}))
    : Promise.resolve();
}

/* ★★ FAZ 60 — ÇEVRİMDIŞI KATMAN (fikirler Y.8). Site AÇILDIKTAN sonra
   kaydediliyor: ilk ziyarette büyük indirmeyle yarışmasın, önbelleğe alma
   tarayıcının HTTP önbelleğinden beslensin. Yalnız güvenli bağlamda
   (https ya da localhost) — tarayıcı başka türlü izin vermiyor zaten. */
function cevrimdisiKatmanKur(){
  if(!("serviceWorker" in navigator) || !window.isSecureContext) return;
  navigator.serviceWorker.register("./sw.js").catch(() => {
    /* Kayıt olmazsa site yine çalışıyor; yalnız çevrimdışı açılmıyor. */
  });
}

/* ------------------------------------------------------------------ boot */
async function calistir(){
  const t0 = performance.now();
  const manifest = await (await _asilFetch("./manifest.json")).json();
  izlemeyiBaslat(manifest);

  asama("python");
  const surum = (manifest.pyodide && manifest.pyodide.version) || "";
  // Pakete alınmış kopya asıl yol: CDN'e istek atmıyoruz (gizlilik) ve
  // CDN engellense de site çalışıyor. CDN yalnız son çare.
  let indexURL = "./pyodide/";
  try{
    if(!(await _asilFetch("./pyodide/pyodide.js", {method: "HEAD"})).ok)
      indexURL = cdnUrl(surum);
  }catch(e){ indexURL = cdnUrl(surum); }
  await new Promise((ok, hata) => {
    const s = document.createElement("script");
    s.src = indexURL + "pyodide.js";
    s.onload = ok;
    s.onerror = () => hata(new Error("Pyodide yüklenemedi: " + s.src));
    document.head.appendChild(s);
  });
  const py = await loadPyodide({ indexURL });

  /* Motorun her modülü `import sqlite3` ile ayakta. Bazı Pyodide
     sürümlerinde sqlite3 stdlib'den ayrılmış ve ayrı yükleniyor; bazılarında
     vendor edilmiş. İkisini de karşılayalım — ve olmuyorsa anlaşılır bir
     hata verelim, ham bir ModuleNotFoundError değil. */
  try{
    py.runPython("import sqlite3");
  }catch(e){
    durumYaz("Veritabanı desteği yükleniyor…");
    try{
      await py.loadPackage("sqlite3");
      py.runPython("import sqlite3");
    }catch(e2){
      throw new Error(
        `Bu Pyodide sürümünde (${surum || "?"}) sqlite3 yok ve yüklenemedi. ` +
        `Site sqlite3 içeren bir sürümle kurulmalı ` +
        `(tools/site_kur.py → PYODIDE_VERSION).`);
    }
  }

  asama("motor");
  py.FS.mkdirTree("/app/itucap");
  py.FS.mkdirTree("/app/config");
  py.FS.mkdirTree("/app/data");
  await Promise.all([
    ...manifest.engine.map(f => dosyaYaz(py, `/app/itucap/${f}.py`, `./itucap/${f}.py`)),
    ...manifest.schema.map(f => dosyaYaz(py, `/app/itucap/${f}`, `./itucap/${f}`)),
    ...manifest.config.map(f => dosyaYaz(py, `/app/config/${f}`, `./config/${f}`)),
  ]);

  asama("katalog");
  durumYaz(`Ders kataloğu indiriliyor (${mb(manifest.catalog.bytes)} MB)…`);
  await katalogYukle(py, manifest);

  asama("veri");
  const vardi = await kullaniciGeriYukle(py);

  asama("hesap");
  await py.runPythonAsync(`
import sys, pathlib
sys.path.insert(0, "/app")
from itucap import config
# Sanal dosya sistemine yerleş — paket kökü burada /app.
config.ROOT     = pathlib.Path("/app")
config.DATA_DIR = config.ROOT / "data"
config.ARCHIVE_DIR = config.DATA_DIR / "raw_archive"
config.REF_DB   = config.DATA_DIR / "reference.sqlite3"
config.USER_DB  = config.DATA_DIR / "user.sqlite3"

from itucap import policy as POL, declared, server as SRV
POL.DEFAULT_PATH      = config.ROOT / "config" / "kurallar.toml"
declared.CATALOG_PATH = config.ROOT / "config" / "katalog-duzeltmeleri.toml"
declared.DEFAULT_PATH = config.ROOT / "config" / "denklikler.toml"

if not (config.ROOT / "config" / "settings.toml").exists():
    (config.ROOT / "config" / "settings.toml").write_text(
        '[student]\\nanadal_program = ""\\nsecond_kind = "yok"\\n', encoding="utf-8")

_state = SRV.State(label="ben", n_schedules=3)

def _durum():
    import json
    return json.dumps(_state.snapshot(), ensure_ascii=False)

def _yedek_ozet(db_yolu, ayar_metni):
    """Yedek dosyasının İÇİNİ doğrula ve özetle — uygulamadan önce (Faz 54)."""
    import json, sqlite3, tomllib
    out = {"ders": None, "anadal": None, "hata": ""}
    try:
        c = sqlite3.connect(db_yolu)
        out["ders"] = c.execute("SELECT COUNT(*) FROM earned_course").fetchone()[0]
        c.close()
    except Exception as exc:
        out["hata"] = f"veritabanı okunamadı ({exc})"
    if ayar_metni:
        try:
            out["anadal"] = tomllib.loads(ayar_metni).get("student", {}).get("anadal_program") or ""
        except Exception as exc:
            out["hata"] = (out["hata"] + " · " if out["hata"] else "") + f"ayar dosyası okunamadı ({exc})"
    return json.dumps(out, ensure_ascii=False)

def _cagir(path, govde):
    """Arayüzün api() çağrısı — HTTP yok, doğrudan State.dispatch.
    Sunucudakiyle AYNI yönlendirme; iki sürüm ayrışamaz."""
    import json
    try:
        r = _state.dispatch(path, json.loads(govde or "{}"))
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": f"beklenmedik hata: {exc}"}, ensure_ascii=False)
    if r is None:
        return json.dumps({"error": "böyle bir uç yok: " + path})
    return json.dumps(r, ensure_ascii=False)
`);

  // Arayüzün api() çağrılarını Python'a yönlendir.
  const cagir = py.globals.get("_cagir");
  window.__ITUCAP_API__ = async (path, payload) => {
    const ham = cagir(path, JSON.stringify(payload || {}));
    const cevap = JSON.parse(ham);
    if(cevap.error) throw new Error(cevap.error);
    await kullaniciKaydet(py);           // her yazmadan sonra kalıcı yap
    return cevap;
  };

  /* ★★ FAZ 54 — YEDEK. Sitede transkriptin, bölümün ve kilitlerin YALNIZ bu
     tarayıcının deposunda (IndexedDB). Tarayıcı verisi silinince, başka
     cihaza geçince ya da Safari 7 gün ziyaret edilmeyen sitenin deposunu
     temizleyince HEPSİ gidiyordu ve geri almanın yolu yoktu. Yedek bir JSON
     dosyası: indirmek ve yüklemek tamamen tarayıcıda, hiçbir yere gitmiyor.
     ⚠️ Yüklemede YALNIZ bilinen üç dosya yazılıyor (yol listeden), SQLite
     başlığı ve TOML Python'da doğrulanıyor — uygulanmadan önce özet
     gösteriliyor. */
  const yedekOzet = py.globals.get("_yedek_ozet");
  const b64 = (u8) => {
    let s = ""; for(let i = 0; i < u8.length; i += 0x8000)
      s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
    return btoa(s);
  };
  const b64ten = (t) => Uint8Array.from(atob(t), c => c.charCodeAt(0));
  window.__ITUCAP_YEDEK__ = {
    async indir(){
      const dosyalar = {};
      for(const yol of KULLANICI_DOSYALARI){
        const v = await idbOku(yol);
        if(v == null) continue;
        dosyalar[yol] = typeof v === "string" ? {metin: v} : {b64: b64(new Uint8Array(v))};
      }
      const yedek = {tur: "itucap-yedek", surum: 1,
                     tarih: new Date().toISOString(), dosyalar};
      const blob = new Blob([JSON.stringify(yedek)], {type: "application/json"});
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `itucap-yedek-${yedek.tarih.slice(0, 10)}.json`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
      return Object.keys(dosyalar).length;
    },
    /** Dosyayı OKU ve DOĞRULA; yazma. `{yedek, ozet}` ya da hata fırlatır. */
    async oku(dosya){
      let yedek;
      try{ yedek = JSON.parse(await dosya.text()); }
      catch(e){ throw new Error("bu bir itucap yedeği değil (JSON okunamadı)"); }
      if(!yedek || yedek.tur !== "itucap-yedek" || yedek.surum !== 1 || !yedek.dosyalar)
        throw new Error("bu bir itucap yedeği değil");
      const bilinmeyen = Object.keys(yedek.dosyalar).filter(y => !KULLANICI_DOSYALARI.includes(y));
      if(bilinmeyen.length) throw new Error("yedekte beklenmeyen dosya var: " + bilinmeyen.join(", "));
      const db = yedek.dosyalar["/app/data/user.sqlite3"];
      if(!db || !db.b64) throw new Error("yedekte transkript veritabanı yok");
      const bayt = b64ten(db.b64);
      if(new TextDecoder().decode(bayt.subarray(0, 15)) !== "SQLite format 3")
        throw new Error("yedekteki veritabanı bozuk");
      py.FS.writeFile("/tmp/yedek-kontrol.sqlite3", bayt);
      const ayar = yedek.dosyalar["/app/config/settings.toml"];
      const ozet = JSON.parse(yedekOzet("/tmp/yedek-kontrol.sqlite3",
                                        (ayar && ayar.metin) || ""));
      if(ozet.hata) throw new Error(ozet.hata);
      return {yedek, ozet: {...ozet, tarih: yedek.tarih}};
    },
    /** Doğrulanmış yedeği depoya yaz ve sayfayı yeniden aç. */
    async uygula(yedek){
      /* ⚠️ Yedekte OLMAYAN dosya depodan SİLİNİYOR: yoksa yedeğin
         transkripti ile şimdiki denklik beyanları karışırdı. */
      for(const yol of KULLANICI_DOSYALARI){
        const d = yedek.dosyalar[yol];
        if(d) await idbYaz(yol, d.metin != null ? d.metin : b64ten(d.b64));
        else await idbSil(yol);
      }
      location.reload();
    },
    async kalici(){
      return navigator.storage && navigator.storage.persisted
        ? await navigator.storage.persisted() : null;
    },
    async kaliciIste(){
      return navigator.storage && navigator.storage.persist
        ? await navigator.storage.persist() : null;
    },
  };

  const durum = py.globals.get("_durum");
  const data = JSON.parse(durum());
  await kullaniciKaydet(py);             // ilk kurulumu da sakla

  await domHazir();
  const son = listeOgesi(IZ.asama);
  if(son){
    son.dataset.durum = "bitti";
    const s = son.querySelector(".sure");
    if(s) s.textContent = sn(performance.now() - IZ.asamaBas);
  }
  izlemeyiBitir();
  ciz();                                  // son kare: %100, ancak şimdi
  window.__ITUCAP_APPLY__(data);
  const yuk = el("yukleniyor");
  if(yuk) yuk.remove();
  cevrimdisiKatmanKur();                  // Faz 60 — ancak her şey açıldıktan sonra
  console.log(`[itucap] hazır ${((performance.now()-t0)/1000).toFixed(1)}s`,
              vardi ? "(kayıtlı veri geri yüklendi)" : "(ilk ziyaret)");
}

calistir().catch(err => {
  console.error(err);
  hataGoster(err);
});

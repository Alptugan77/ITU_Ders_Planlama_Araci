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

const CDN = "https://cdn.jsdelivr.net/pyodide/v0.28.3/full/";
const DB_ADI = "itucap", DEPO = "kullanici";
// Kullanıcıya ait, kalıcı olması gereken dosyalar. Katalog burada YOK:
// o herkese açık ve her açılışta yeniden indiriliyor.
const KULLANICI_DOSYALARI = [
  "/app/data/user.sqlite3",
  "/app/config/settings.toml",
  "/app/config/denklikler.toml",
];

const el = (id) => document.getElementById(id);
let adimNo = 0;
const ADIM_SAYISI = 6;
function adim(metin){
  adimNo++;
  const a = el("yukAdim"), c = el("yukCubuk");
  if(a) a.textContent = metin;
  if(c) c.style.width = Math.min(100, (adimNo / ADIM_SAYISI) * 100) + "%";
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

/* ------------------------------------------------------------------ boot */
async function calistir(){
  const t0 = performance.now();
  const manifest = await (await fetch("./manifest.json")).json();

  adim("Python çalışma ortamı yükleniyor (bir kez, sonra önbellekten)…");
  // Yerel kopya varsa onu kullan (çevrimdışı ve CDN'siz çalışsın).
  let indexURL = CDN;
  try{
    if((await fetch("./pyodide/pyodide.js", {method: "HEAD"})).ok)
      indexURL = "./pyodide/";
  }catch(e){ /* CDN'de kal */ }
  if(indexURL !== CDN){
    await new Promise((ok, hata) => {
      const s = document.createElement("script");
      s.src = "./pyodide/pyodide.js"; s.onload = ok; s.onerror = hata;
      document.head.appendChild(s);
    });
  }else{
    await new Promise((ok, hata) => {
      const s = document.createElement("script");
      s.src = CDN + "pyodide.js"; s.onload = ok; s.onerror = hata;
      document.head.appendChild(s);
    });
  }
  const py = await loadPyodide({ indexURL });

  adim("Motor yükleniyor…");
  py.FS.mkdirTree("/app/itucap");
  py.FS.mkdirTree("/app/config");
  py.FS.mkdirTree("/app/data");
  await Promise.all([
    ...manifest.engine.map(f => dosyaYaz(py, `/app/itucap/${f}.py`, `./itucap/${f}.py`)),
    ...manifest.schema.map(f => dosyaYaz(py, `/app/itucap/${f}`, `./itucap/${f}`)),
    ...manifest.config.map(f => dosyaYaz(py, `/app/config/${f}`, `./config/${f}`)),
  ]);

  adim(`Ders kataloğu indiriliyor (${(manifest.catalog.bytes/1e6).toFixed(1)} MB)…`);
  await katalogYukle(py, manifest);

  adim("Kayıtlı verin geri yükleniyor…");
  const vardi = await kullaniciGeriYukle(py);

  adim("Motor kuruluyor…");
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

  adim("Hesaplanıyor…");
  const durum = py.globals.get("_durum");
  const data = JSON.parse(durum());
  await kullaniciKaydet(py);             // ilk kurulumu da sakla

  window.__ITUCAP_APPLY__(data);
  const yuk = el("yukleniyor");
  if(yuk) yuk.remove();
  console.log(`[itucap] hazır ${((performance.now()-t0)/1000).toFixed(1)}s`,
              vardi ? "(kayıtlı veri geri yüklendi)" : "(ilk ziyaret)");
}

calistir().catch(err => {
  console.error(err);
  const a = el("yukAdim");
  if(a){
    a.innerHTML = `<b style="color:var(--danger)">Yüklenemedi:</b> ${
      String(err.message || err)}<br><br>
      Sayfayı yenilemeyi dene. Sorun sürerse tarayıcı konsolundaki hatayı
      GitHub'da bildir.`;
  }
});

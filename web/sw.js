/* itucap — çevrimdışı katman (Faz 60, fikirler Y.8).
 *
 * Kayıt günü bağlantı en kötü anında: OBS yavaş, yurt ağı dolu, telefon
 * çekmiyor. Site her açılışta motoru, kataloğu ve Pyodide'i ağdan
 * indiriyordu; bağlantı yoksa hiç açılmıyordu — planladığın program, CRN
 * listesi, yedek plan dahil.
 *
 * Kurallar:
 *   · YALNIZ kendi kökenimiz ve yalnız GET/HEAD. CDN'e ve başka hiçbir yere
 *     dokunmuyoruz (gizlilik: bu dosya hiçbir isteği değiştirmiyor, yalnız
 *     kendi dosyalarımızın kopyasını tutuyor).
 *   · Kabuk (sayfa, motor, katalog): AĞ ÖNCE. Bağlantı varsa her zaman taze
 *     veri; yoksa (ya da 8 sn'de cevap gelmezse) kayıtlı kopya.
 *   · Pyodide (~10 MB, sürümlü): ÖNBELLEK ÖNCE — sürüm değişince önbellek adı
 *     da değişiyor, eskisi siliniyor.
 *   · ★ Kopyadan gelen her cevap `X-Itucap-Onbellek: 1` taşıyor. Sayfa bunu
 *     görünce "çevrimdışı açıldı, kontenjanlar şu tarihteki hâliyle" diyor:
 *     eski kontenjanı canlıymış gibi göstermek, bu aracın yapmadığı şey.
 *
 * `__SURUM__`, `__PYODIDE__` ve `__DOSYALAR__` `tools/site_kur.py` yazıyor.
 */
"use strict";
const SURUM = "__SURUM__";
const KABUK = "itucap-kabuk-" + SURUM;
const PYODIDE = "itucap-pyodide-__PYODIDE__";
const DOSYALAR = __DOSYALAR__;
const ISARET = "X-Itucap-Onbellek";
const BEKLE_MS = 8000;

const pyodideYolu = (url) => new URL(url).pathname.includes("/pyodide/");

self.addEventListener("install", (e) => {
  /* Kayıt, site TAMAMEN açıldıktan sonra yapılıyor (app.js): dosyalar
     tarayıcının HTTP önbelleğinde, bu indirme çoğunlukla ağa çıkmıyor.
     Tek dosya alınamazsa kurulum düşmesin — elde olanı tut. */
  e.waitUntil((async () => {
    const kabuk = await caches.open(KABUK), py = await caches.open(PYODIDE);
    await Promise.all(DOSYALAR.map(async (yol) => {
      try{
        const url = new URL(yol, self.registration.scope).href;
        /* `no-cache` burada da: yeni sürüm kurulurken HTTP önbelleği ESKİ
           kataloğu verebiliyor (max-age) ve yeni sürümün adıyla saklanırdı —
           test bunu yakaladı. Yeniden doğrulama 304'le gövdeyi yeniden
           indirmiyor; ilk ziyarette çift indirme yok. */
        const res = await fetch(url, {cache: "no-cache"});
        if(res.ok) await (pyodideYolu(url) ? py : kabuk).put(url, res);
      }catch(err){ /* bağlantı koptu — bir sonraki açılışta tamamlanır */ }
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    for(const ad of await caches.keys())
      if(ad.startsWith("itucap-") && ad !== KABUK && ad !== PYODIDE) await caches.delete(ad);
    await self.clients.claim();
  })());
});

async function isaretli(res){
  const h = new Headers(res.headers);
  h.set(ISARET, "1");
  return new Response(await res.blob(), {status: res.status, statusText: res.statusText,
                                         headers: h});
}

async function agOnce(istek){
  const depo = await caches.open(KABUK);
  const eski = await depo.match(istek, {ignoreSearch: true});
  /* ⚠️ `no-cache`: ağ denemesi tarayıcının HTTP önbelleğine düşmesin.
     GitHub Pages `max-age=600` gönderiyor; o 10 dakikada çevrimdışı `fetch`
     HTTP önbelleğindeki kopyayı döndürür — katalog İŞARETSİZ gelir, sayfa
     canlı sanır. Test sunucusu aynı başlığı gönderiyor ve bunu ölçüyor.
     Yeniden doğrulama çevrimiçiyken ucuz (304). */
  const ag = fetch(istek.url, {cache: "no-cache", credentials: "same-origin"}).then(async (res) => {
    if(res.ok) await depo.put(istek, res.clone());
    return res;
  });
  if(!eski) return ag;
  /* Kopya varsa ağ BEKLE_MS içinde cevap vermezse kopya — işaretli. Ağ
     sonradan gelirse önbellek yine tazeleniyor (bir sonraki açılış için). */
  const zaman = new Promise((ok) => setTimeout(() => ok(null), BEKLE_MS));
  try{
    const res = await Promise.race([ag, zaman]);
    if(res) return res;
  }catch(err){ /* çevrimdışı */ }
  ag.catch(() => {});
  return isaretli(eski);
}

async function onbellekOnce(istek){
  const depo = await caches.open(PYODIDE);
  const eski = await depo.match(istek.url);
  if(eski){
    /* app.js paketlenmiş Pyodide var mı diye HEAD atıyor; çevrimdışıyken
       ağa giderse CDN'e düşer ve açılış hiç olmaz. */
    return istek.method === "HEAD"
      ? new Response(null, {status: 200, headers: {[ISARET]: "1"}}) : eski;
  }
  const res = await fetch(istek);
  if(res.ok && istek.method === "GET") await depo.put(istek, res.clone());
  return res;
}

self.addEventListener("fetch", (e) => {
  const r = e.request;
  if(r.method !== "GET" && r.method !== "HEAD") return;
  const url = new URL(r.url);
  if(url.origin !== self.location.origin) return;       // CDN'e ve başka yere dokunma
  if(pyodideYolu(r.url)) e.respondWith(onbellekOnce(r));
  else if(r.method === "GET") e.respondWith(agOnce(r));
});

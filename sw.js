/* VolleySpot — service worker : appli disponible hors ligne après la 1re visite. */
const VERSION = 'vs-2026-11-22d';
const SHELL = ['./', 'index.html', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png',
  'vendor/leaflet/leaflet.js', 'vendor/leaflet/leaflet.css', 'vendor/markercluster/leaflet.markercluster.js',
  'vendor/markercluster/MarkerCluster.css', 'vendor/markercluster/MarkerCluster.Default.css',
  'vendor/lucide.min.js', 'vendor/supabase.js'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  // Météo et géocodage : toujours en direct (pas de cache).
  if (/open-meteo|geopf|equipements\.sports\.gouv\.fr|supabase\.co/.test(url.hostname)) return;
  // Page : réseau d'abord (pour recevoir les mises à jour), cache en secours.
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).then(r => { const copy = r.clone(); caches.open(VERSION).then(c => c.put('index.html', copy)); return r; })
      .catch(() => caches.match('index.html')));
    return;
  }
  // Logos, icônes, bibliothèques, fonds de carte : cache d'abord.
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(r => {
    if (r.ok || r.type === 'opaque') { const copy = r.clone(); caches.open(VERSION).then(c => c.put(req, copy)); }
    return r;
  })));
});

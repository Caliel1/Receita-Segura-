// Service worker do PWA: deixa o site instalável e abrindo mesmo sem internet.
const VERSAO_CACHE = 'receita-segura-v2';
const ARQUIVOS_BASE = [
  '/',
  '/css/styles.css',
  '/js/script.js',
  '/assets/logo.jpeg',
  '/assets/icone-192.png',
  '/assets/icone-512.png',
  '/manifest.webmanifest'
];

self.addEventListener('install', (evento) => {
  evento.waitUntil(caches.open(VERSAO_CACHE).then(cache => cache.addAll(ARQUIVOS_BASE)));
  self.skipWaiting();
});

self.addEventListener('activate', (evento) => {
  evento.waitUntil(
    caches.keys().then(chaves => Promise.all(chaves.filter(c => c !== VERSAO_CACHE).map(c => caches.delete(c))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (evento) => {
  const url = new URL(evento.request.url);
  if (evento.request.method !== 'GET' || url.origin !== location.origin) return;

  // API: sempre da rede (dados médicos não ficam guardados no cache do navegador).
  if (url.pathname.startsWith('/api/')) return;

  // Site: tenta a rede primeiro (versão mais nova); sem internet, usa o cache.
  evento.respondWith(
    fetch(evento.request)
      .then(resposta => {
        const copia = resposta.clone();
        caches.open(VERSAO_CACHE).then(cache => cache.put(evento.request, copia));
        return resposta;
      })
      .catch(() => caches.match(evento.request, { ignoreSearch: true }).then(r => r || caches.match('/')))
  );
});

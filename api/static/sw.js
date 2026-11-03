// CardioPath AI — Service Worker (Oflayn PWA rejimi - Qishloq poliklinikalari barqarorligi)
const CACHE_NAME = 'cardiopath-pwa-v2';
const STATIC_ASSETS = [
  '/screening',
  '/guardian',
  '/static/manifest.webmanifest',
  '/static/app.html',
  '/static/screening.html',
  '/static/guardian.html',
  '/static/app.js',
  '/static/cardiopath.js',
  '/static/help.js',
  '/static/cardiopath.css',
  '/static/app-premium.css'
];

// O'rnatish: statik resurslarni oldindan keshlash
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('Ba\'zi statik fayllar oldindan keshlanmadi:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// Faollashtirish: eski kesh versiyalarini tozalash
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// So'rovlarni qayta ishlash: Stale-While-Revalidate yoki Cache-First
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Faqat GET so'rovlarini keshlaymiz
  if (event.request.method !== 'GET') {
    return;
  }

  // Statik fayllar (/static/ yoki html) uchun: Cache First, keyin Network
  if (url.pathname.startsWith('/static/') || url.pathname === '/screening' || url.pathname === '/guardian' || url.pathname === '/') {
    event.respondWith(
      caches.match(event.request).then((cachedResponse) => {
        if (cachedResponse) {
          // Fondan yangilash (Revalidate)
          fetch(event.request).then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              caches.open(CACHE_NAME).then((cache) => cache.put(event.request, networkResponse));
            }
          }).catch(() => {});
          return cachedResponse;
        }

        return fetch(event.request).then((networkResponse) => {
          if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
            return networkResponse;
          }
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
          return networkResponse;
        }).catch(() => {
          // Oflayn holatda asosiy sahifani qaytarish
          if (event.request.headers.get('accept')?.includes('text/html')) {
            return caches.match('/screening');
          }
        });
      })
    );
    return;
  }

  // API so'rovlari: Network First, oflayn bo'lsa JSON xabarnoma
  event.respondWith(
    fetch(event.request).catch(() => {
      return new Response(
        JSON.stringify({
          offline: true,
          error: "Internet aloqasi mavjud emas. Oflayn rejim faol.",
          status: "offline_cached"
        }),
        {
          headers: { 'Content-Type': 'application/json' },
          status: 503
        }
      );
    })
  );
});

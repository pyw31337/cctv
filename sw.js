/* eslint-env serviceworker */
/* global self, caches, fetch, URL */

// Service worker for "밖에 눈오나?" — provides offline-friendly shell caching
// and stale-while-revalidate behaviour for slow-changing data files.
//
// Cache buckets:
//   - SHELL_CACHE       precached HTML/CSS/JS skeleton (network-fall-back-to-cache)
//   - DATA_CACHE        large JSON blobs (stale-while-revalidate)
//   - IMG_CACHE         marker icons, favicon, app icons (cache-first)
//
// The CACHE_VERSION is hot-swapped by the deploy GHA so a new release purges
// all prior caches even when a long-lived tab still holds the old SW.

const CACHE_VERSION = 'v20260521-aaabe56b';

const SHELL_ASSETS = [
    './',
    'index.html',
    'css/style.css',
    'js/app.js',
    'site.webmanifest',
    'favicon.ico',
    'favicon-16x16.png',
    'favicon-32x32.png',
    'apple-touch-icon.png',
    'android-chrome-192x192.png',
    'pin.svg',
    'marker_gray.svg'
];

// Paths whose JSON answer we serve fast from cache but revalidate in the
// background. New body replaces the cache entry; next page load sees the
// fresh data without blocking the current request.
const STALE_WHILE_REVALIDATE_PATTERNS = [
    /\/data\/world_tour_cams\.json/,
    /\/data\/quality_summary\.json/,
    /\/data\/cache_status\.json/,
    /\/data\/world_tour_health\.json/,
    /\/cctv_data\.json/,
    /\/cctv_overrides\.json/
];

function isShellRequest(url) {
    return SHELL_ASSETS.some(asset => url.pathname.endsWith(asset.replace('./', '/'))
        || url.pathname.endsWith('/' + asset));
}

function isStaleWhileRevalidate(url) {
    return STALE_WHILE_REVALIDATE_PATTERNS.some(re => re.test(url.pathname));
}

function isImageAsset(url) {
    return /\.(png|jpg|jpeg|gif|svg|webp|ico)$/i.test(url.pathname);
}

self.addEventListener('install', event => {
    event.waitUntil((async () => {
        const cache = await caches.open(SHELL_CACHE);
        // addAll fails the whole install if any asset 404s. We tolerate
        // missing files by adding them individually.
        await Promise.all(SHELL_ASSETS.map(asset =>
            cache.add(new Request(asset, { cache: 'reload' })).catch(err => {
                console.warn('[sw] failed to precache', asset, err);
            })
        ));
        await self.skipWaiting();
    })());
});

self.addEventListener('activate', event => {
    event.waitUntil((async () => {
        const keep = new Set([SHELL_CACHE, DATA_CACHE, IMG_CACHE]);
        const keys = await caches.keys();
        await Promise.all(keys.filter(k => !keep.has(k)).map(k => caches.delete(k)));
        await self.clients.claim();
    })());
});

async function staleWhileRevalidate(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);
    const networkPromise = fetch(request).then(response => {
        if (response && response.status === 200 && response.type !== 'opaque') {
            cache.put(request, response.clone()).catch(() => {});
        }
        return response;
    }).catch(() => null);
    return cached || (await networkPromise) || Response.error();
}

async function networkFirst(request, cacheName) {
    try {
        const response = await fetch(request);
        if (response && response.status === 200) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone()).catch(() => {});
        }
        return response;
    } catch (err) {
        const cache = await caches.open(cacheName);
        const cached = await cache.match(request);
        if (cached) return cached;
        throw err;
    }
}

async function cacheFirst(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);
    if (cached) return cached;
    const response = await fetch(request);
    if (response && response.status === 200) {
        cache.put(request, response.clone()).catch(() => {});
    }
    return response;
}

self.addEventListener('fetch', event => {
    const { request } = event;
    if (request.method !== 'GET') return;
    const url = new URL(request.url);

    // Only handle same-origin traffic. Third-party (Kakao SDK, OpenStreetMap
    // tiles, video CDNs) goes straight to the network so we don't accidentally
    // cache opaque/credentialed responses.
    if (url.origin !== self.location.origin) return;

    // Don't touch CCTV stream/proxy traffic — caching live video bytes would
    // be a footgun.
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/stream/')) return;

    if (request.mode === 'navigate' || request.destination === 'document') {
        event.respondWith(networkFirst(request, SHELL_CACHE));
        return;
    }

    if (isStaleWhileRevalidate(url)) {
        event.respondWith(staleWhileRevalidate(request, DATA_CACHE));
        return;
    }

    if (isImageAsset(url)) {
        event.respondWith(cacheFirst(request, IMG_CACHE));
        return;
    }

    if (isShellRequest(url)) {
        event.respondWith(staleWhileRevalidate(request, SHELL_CACHE));
    }
});

self.addEventListener('message', event => {
    if (event.data === 'skipWaiting') self.skipWaiting();
});

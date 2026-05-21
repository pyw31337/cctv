/**
 * cctv-og-image
 *
 * Dynamic Open Graph image generator for "밖에 눈오나?".
 *
 * Usage:
 *   GET https://cctv-og.pyw31337.workers.dev/og?id=<cctv_id>&title=<urlencoded>&city=<urlencoded>&snap=<urlencoded>
 *
 * Returns: image/png, 1200×630.
 *
 * Caching: edge-cached for 6 hours (cf-cache key includes all query params).
 * Bust by appending a `_=timestamp` if the underlying snapshot changes.
 */
import satori, { type SatoriOptions } from 'satori';
import { Resvg, initWasm } from '@resvg/resvg-wasm';
// @ts-ignore – wasm binary import is handled by the worker bundler
import resvgWasm from '@resvg/resvg-wasm/index_bg.wasm';

let resvgReady: Promise<void> | null = null;
async function ensureResvg() {
    if (resvgReady) return resvgReady;
    resvgReady = initWasm(resvgWasm as unknown as ArrayBuffer);
    return resvgReady;
}

interface Env {
    SITE_BASE_URL: string;
    ATTRIBUTION: string;
}

async function loadFont(url: string): Promise<ArrayBuffer> {
    const res = await fetch(url, { cf: { cacheTtl: 86400 } as any });
    if (!res.ok) throw new Error(`font fetch failed: ${res.status}`);
    return res.arrayBuffer();
}

async function snapshotToDataUri(url: string): Promise<string | null> {
    try {
        const res = await fetch(url, { cf: { cacheTtl: 1800 } as any });
        if (!res.ok) return null;
        const ct = res.headers.get('content-type') || 'image/jpeg';
        const buf = await res.arrayBuffer();
        const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
        return `data:${ct};base64,${b64}`;
    } catch {
        return null;
    }
}

function corsHeaders() {
    return {
        'access-control-allow-origin': '*',
        'access-control-allow-methods': 'GET, OPTIONS',
        'access-control-allow-headers': 'Content-Type'
    };
}

export default {
    async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
        const url = new URL(request.url);
        if (request.method === 'OPTIONS') {
            return new Response(null, { status: 204, headers: corsHeaders() });
        }
        if (!url.pathname.startsWith('/og')) {
            return new Response('Not found', { status: 404, headers: corsHeaders() });
        }

        const params = url.searchParams;
        const title = (params.get('title') || 'CCTV 라이브').slice(0, 80);
        const city = (params.get('city') || '').slice(0, 40);
        const snap = params.get('snap');
        const attribution = env.ATTRIBUTION || '밖에 눈오나?';

        // Pretendard 폰트는 한글 표기에 적합한 무료 폰트 (jsdelivr CDN).
        const fontUrl = 'https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/packages/pretendard/dist/web/static/pretendard.woff2';
        const [fontData, snapDataUri] = await Promise.all([
            loadFont(fontUrl).catch(() => null),
            snap ? snapshotToDataUri(snap) : Promise.resolve(null)
        ]);

        const tree = {
            type: 'div',
            props: {
                style: {
                    width: '1200px',
                    height: '630px',
                    display: 'flex',
                    flexDirection: 'column',
                    background: '#0f172a',
                    color: '#f8fafc',
                    fontFamily: 'Pretendard, sans-serif',
                    position: 'relative'
                },
                children: [
                    snapDataUri ? {
                        type: 'img',
                        props: {
                            src: snapDataUri,
                            width: 1200,
                            height: 630,
                            style: {
                                position: 'absolute',
                                top: 0, left: 0,
                                width: '1200px',
                                height: '630px',
                                objectFit: 'cover',
                                opacity: 0.55
                            }
                        }
                    } : null,
                    {
                        type: 'div',
                        props: {
                            style: {
                                position: 'absolute',
                                inset: 0,
                                background: 'linear-gradient(180deg, rgba(15,23,42,0.5) 0%, rgba(15,23,42,0.92) 100%)'
                            }
                        }
                    },
                    {
                        type: 'div',
                        props: {
                            style: {
                                position: 'relative',
                                display: 'flex',
                                flexDirection: 'column',
                                justifyContent: 'space-between',
                                width: '100%',
                                height: '100%',
                                padding: '60px'
                            },
                            children: [
                                {
                                    type: 'div',
                                    props: {
                                        style: { display: 'flex', alignItems: 'center', gap: '14px', color: '#bbf7d0', fontSize: '24px', fontWeight: 700 },
                                        children: [
                                            { type: 'div', props: { style: { width: 16, height: 16, background: '#22c55e', borderRadius: 999 } } },
                                            attribution
                                        ]
                                    }
                                },
                                {
                                    type: 'div',
                                    props: {
                                        style: { display: 'flex', flexDirection: 'column', gap: '18px' },
                                        children: [
                                            city ? {
                                                type: 'div',
                                                props: { style: { fontSize: '32px', color: '#94a3b8', fontWeight: 600 }, children: city }
                                            } : null,
                                            {
                                                type: 'div',
                                                props: { style: { fontSize: '64px', lineHeight: 1.15, fontWeight: 800, maxWidth: '1080px' }, children: title }
                                            },
                                            {
                                                type: 'div',
                                                props: { style: { fontSize: '22px', color: '#cbd5e1', marginTop: '12px' }, children: '지금 이 시각 라이브 CCTV' }
                                            }
                                        ].filter(Boolean)
                                    }
                                }
                            ]
                        }
                    }
                ].filter(Boolean) as any
            }
        };

        const svg = await satori(tree as any, {
            width: 1200,
            height: 630,
            fonts: fontData ? [{ name: 'Pretendard', data: fontData, weight: 700, style: 'normal' }] : []
        } as SatoriOptions);

        await ensureResvg();
        const resvg = new Resvg(svg, { fitTo: { mode: 'width', value: 1200 } });
        const png = resvg.render().asPng();

        return new Response(png, {
            headers: {
                'content-type': 'image/png',
                'cache-control': 'public, max-age=21600, s-maxage=21600, stale-while-revalidate=86400',
                ...corsHeaders()
            }
        });
    }
};

(function () {
    // Keep lazy-loaded modules on the same release as the HTML shell. This
    // must change with every frontend release so a service worker cannot hand
    // an older World Tour module back to a newly deployed page.
    const buildVersion = '20261116-f683a79c';
    // The cctv-quality telemetry Worker (cctv-quality.pyw31337.workers.dev) is
    // not deployed (confirmed 2026-11-22: no such Worker in the Cloudflare
    // account). Until it is deployed again, telemetry stays off and the quality
    // views read the static snapshots (data/quality_summary.json,
    // data/quality_policy.json), so no page requests a host that cannot answer.
    // Set these two back to the Worker URLs once it is deployed.
    const quality = Object.freeze({
        telemetryEndpoint: '',
        summaryUrl: '',
        healthStatusUrl: 'https://158.179.194.163.sslip.io/health-status',
        canaryStatusUrl: 'https://158.179.194.163.sslip.io/canary-status',
        publicProxyBase: 'https://158.179.194.163.sslip.io',
        workerProxyBase: 'https://cctv-proxy.pyw213.workers.dev',
        gitsProxyBase: 'https://cctv-proxy-hoon-001.fly.dev',
        proxyBases: [
            'https://158.179.194.163.sslip.io',
            'https://cctv-proxy.pyw213.workers.dev'
        ]
    });

    const runtime = Object.freeze({
        buildVersion,
        quality,
        proxyBases: quality.proxyBases.slice(),
        publicProxyBase: quality.publicProxyBase,
        workerProxyBase: quality.workerProxyBase,
        gitsProxyBase: quality.gitsProxyBase,
        canaryStatusUrl: quality.canaryStatusUrl,
        healthStatusUrl: quality.healthStatusUrl,
        qualityTelemetryEndpoint: quality.telemetryEndpoint,
        qualitySummaryUrl: quality.summaryUrl,
        worldTourDataUrl: `data/world_tour_cams.json?v=${buildVersion}`,
        qualitySummaryFallbackUrl: 'data/quality_summary.json',
        canaryStatusFallbackUrl: 'data/canary_status.json'
    });

    window.CCTV_RUNTIME_CONFIG = runtime;
    window.CCTV_QUALITY_CONFIG = window.CCTV_QUALITY_CONFIG || quality;
    window.CCTV_QUALITY_SUMMARY_URL = window.CCTV_QUALITY_SUMMARY_URL || quality.summaryUrl;
    window.CCTV_QUALITY_TELEMETRY_ENDPOINT = window.CCTV_QUALITY_TELEMETRY_ENDPOINT || quality.telemetryEndpoint;
    window.CCTV_QUALITY_CANARY_STATUS_URL = window.CCTV_QUALITY_CANARY_STATUS_URL || quality.canaryStatusUrl;
})();

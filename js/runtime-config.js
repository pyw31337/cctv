(function () {
    const buildVersion = '20260901-playback1';
    const quality = Object.freeze({
        telemetryEndpoint: 'https://cctv-quality.pyw31337.workers.dev/v1/events',
        summaryUrl: 'https://cctv-quality.pyw31337.workers.dev/v1/summary',
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

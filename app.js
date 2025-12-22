// Initialize Leaflet Map
const map = L.map('map').setView([36.5, 127.5], 7); // Default center of Korea

// Add OpenStreetMap tile layer
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);

// Fetch CCTV Data
fetch('cctv_data.json')
    .then(response => response.json())
    .then(data => {
        console.log(`Loaded ${data.length} CCTVs`);

        // Count by status
        const statusCounts = data.reduce((acc, cctv) => {
            acc[cctv.status || 'unknown'] = (acc[cctv.status || 'unknown'] || 0) + 1;
            return acc;
        }, {});
        console.log('Status breakdown:', statusCounts);

        data.forEach(cctv => {
            if (cctv.lat && cctv.lng) {
                // Determine marker color based on status
                let markerColor = '#808080'; // gray (unknown)
                let statusText = '상태 불명';

                if (cctv.status === 'active') {
                    markerColor = '#28a745'; // green
                    statusText = '정상';
                } else if (cctv.status === 'error') {
                    markerColor = '#dc3545'; // red
                    statusText = '오류/점검중';
                }

                // Create custom marker
                const customIcon = L.divIcon({
                    className: 'custom-marker',
                    html: `<div style="background-color: ${markerColor}; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>`,
                    iconSize: [24, 24],
                    iconAnchor: [12, 12]
                });

                const marker = L.marker([cctv.lat, cctv.lng], { icon: customIcon }).addTo(map);

                const popupContent = `
                    <div class="cctv-popup">
                        <b>${cctv.name}</b>
                        <div style="margin: 8px 0; color: ${markerColor}; font-weight: bold;">
                            ● ${statusText}
                        </div>
                        ${cctv.status === 'active' ? `
                            <a href="${cctv.url}" target="_blank" onclick="window.open(this.href, 'cctv_view', 'width=400,height=350'); return false;">
                                CCTV 보기
                            </a>
                        ` : `
                            <div style="color: #999; font-size: 0.9em;">영상을 사용할 수 없습니다</div>
                        `}
                    </div>
                `;

                marker.bindPopup(popupContent);
            }
        });
    })
    .catch(error => console.error('Error loading CCTV data:', error));

// Get User Location
if ('geolocation' in navigator) {
    navigator.geolocation.getCurrentPosition(
        (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;

            console.log(`User location: ${lat}, ${lng}`);

            // Add marker for user
            L.marker([lat, lng], {
                icon: L.divIcon({
                    className: 'user-marker',
                    html: '<div style="background-color: blue; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white;"></div>',
                    iconSize: [16, 16]
                })
            }).addTo(map)
                .bindPopup("현재 위치")
                .openPopup();

            map.setView([lat, lng], 13);
        },
        (error) => {
            console.error('Geolocation error:', error);
            alert('위치 정보를 가져올 수 없습니다. 기본 위치를 사용합니다.');
        }
    );
} else {
    alert('이 브라우저는 위치 정보를 지원하지 않습니다.');
}

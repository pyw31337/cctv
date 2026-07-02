let VRTX_ARRAY = new Array();
let sVRTX_ARRAY = new Array();
let bVRTX_ARRAY = new Array();
let MARKER_ARRAY = {};
let ROUTE_MARKER_ARRAY = [];
let ROADNAME;
let SELECT_ROUTE_ID;

let oMap;
let oVrtxPoly0;
let oVrtxPoly1;
let oVrtxPoly2;
let oVrtxPoly3;
let oVrtxPoly4;
let oVrtxPoly5;
let oVrtxPoly6;

let searchKeyword;
let searchCnt = 0;

let BUS_TOGGLE = false;
let STATION_TOGGLE = false;

const MARKER = {
    CCTV: '/images/marker/map-marker-cctv.svg', //CCTV 일반
    CCTV_SEL: '/images/marker/map-marker-cctv-on.svg', //CCTV 선택

    VMS: '/images/marker/map-marker-vms.svg', //VMS 일반
    VMS_SEL: '/images/marker/map-marker-vms-on.svg', //VMS 선택

    INCD: '/images/marker/map-marker-acc.svg', //사고 일반
    INCD_SEL: '/images/marker/map-marker-acc-on.svg', //사고 선택

    SCHOOL: '/images/marker/map-marker-schoolzone.svg', //어린이보호구역 일반
    SCHOOL_SEL: '/images/marker/map-marker-schoolzone-on.svg', //어린이보호구역 선택

    BUSSTOP: '/images/marker/map-marker-bus-stop.svg', //정류장 일반
    BUSSTOP_SEL: '/images/marker/map-marker-bus-stop-on.svg', //정류장 선택

    SMART: '/images/marker/map-marker-corssroad.svg', //스마트교차로 일반
    SMART_SEL: '/images/marker/map-marker-corssroad-on.svg', //스마트교차로 선택

    PARKING: '/images/marker/map-marker-parking.svg', //주차장 일반
    PARKING_SEL: '/images/marker/map-marker-parking-on.svg', //주차장 선택

    CHARGER: '/images/marker/map-marker-electric.svg', //충전소 일반
    CHARGER_SEL: '/images/marker/map-marker-electric-on.svg', //충전소 선택

    SIGNAL : '/images/marker/map-marker-signal.svg',
    SIGNAL_SEL : '/images/marker/map-marker-signal-on.svg',

    BUS_BLUE: '/images/marker_bus_blue.png', //상행 blue
    BUS_RED: '/images/marker_bus_red.png', //하행 red
    BUS_GREEN: '/images/marker_bus_green.png', //순환 green

    UP_BUS: '/images/marker/map-marker-bus-up.svg', //기본 버스 마커
    UP_LOW_BUS: '/images/marker/map-marker-lowfloor-up.svg', //저상 버스 마커
    DOWN_BUS: '/images/marker/map-marker-bus-down.svg', //기본 버스 마커
    DOWN_LOW_BUS: '/images/marker/map-marker-lowfloor-down.svg', //저상 버스 마커

    S_SIZE: {
        W: 10, H: 10,
    },

    M_SIZE: {
        W: 30, H: 30,
    },

    L_SIZE: {
        W: 60, H: 60,
    },
}
let counter = 30;
let counterInterval;


$(document).ready(function () {
    init();
    screenFunc();
    $("#map > div:nth-child(6) > div").css('padding', '0');
});

function init() {
    // SDK 비동기 로드 대기: kakao가 아직 없으면 잠시 후 재시도
    if (typeof kakao === 'undefined') {
        setTimeout(init, 50);
        return;
    }
    // Kakao SDK가 autoload=false로 로드된 경우: kakao.maps.load() 콜백에서 초기화 (document.write 경고 방지)
    var runMapInit = function() {
        createMap();
        setCircleOnMap();
        currentCircle.setMap(null);
        initVrtxPoly();
        dataFunc();
        addEvent();
        preParamEvt(new URLSearchParams(window.location.search).get('preParam'));
    };
    if (kakao.maps && typeof kakao.maps.load === 'function') {
        kakao.maps.load(runMapInit);
    } else {
        runMapInit();
    }
    
    
    const styleElement = document.createElement('style');
    styleElement.textContent = `
        .parking-card {
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            padding: 5px;
            width: 100%;
            max-width: 400px;
        }

        .refresh-icon {
            width: 48px;
            height: 48px;
            border: 2px solid #333;
            border-radius: 50%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            flex-shrink: 0;
            position: relative;
        }

        .refresh-icon:hover {
            transform: scale(1.1);
        }

        @keyframes spin {
            from {
                transform: rotate(0deg);
            }
            to {
                transform: rotate(360deg);
            }
        }

        .refresh-icon svg {
            width: 20px;
            height: 20px;
            animation: spin 2s linear infinite;
        }

        .refresh-number {
            font-size: 18px;
            font-weight: bold;
            color: #333;
            margin-top: -2px;
            transition: all 0.3s ease;
        }

        @keyframes countUp {
            0% {
                transform: translateY(10px);
                opacity: 0;
            }
            50% {
                transform: translateY(-5px);
                opacity: 1;
            }
            100% {
                transform: translateY(0);
                opacity: 1;
            }
        }

        .refresh-number.updating {
            animation: countUp 0.4s ease;
        }

        @keyframes flash {
            0%, 100% {
                opacity: 1;
            }
            50% {
                opacity: 0.3;
            }
        }

        .parking-card.refreshing {
            animation: flash 0.5s ease;
        }

        .stats-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }

        .stat-box {
            padding: 16px;
            border-radius: 6px;
            text-align: center;
            transition: transform 0.3s ease;
        }

        .stat-box.available {
            background-color: #e91e63;
            color: white;
        }

        .stat-box.total {
            background-color: #2c3e50;
            color: white;
        }

        .stat-number {
            font-size: 28px;
            font-weight: bold;
        }

        /* 모바일에서 팝업 전체 화면으로 표시 */
        @media (max-width: 768px) {
            .popInfoWrap.parking-card {
                position: fixed !important;
                top: 0 !important;
                left: 0 !important;
                right: 0 !important;
                bottom: 0 !important;
                width: 100vw !important;
                height: 100vh !important;
                max-width: 100vw !important;
                max-height: 100vh !important;
                transform: none !important;
                margin: 0 !important;
                border-radius: 0 !important;
                z-index: 9999 !important;
            }
            
            .parking-card.gis-modal.parking-modal {
                width: 100% !important;
                height: 100% !important;
                max-width: 100% !important;
                max-height: 100vh !important;
                margin: 0 !important;
                border-radius: 0 !important;
                display: flex !important;
                flex-direction: column !important;
            }
            
            .gis-modal-header {
                flex-shrink: 0;
            }
            
            .gis-modal-body {
                flex: 1;
                overflow-y: auto;
                overflow-x: hidden;
                -webkit-overflow-scrolling: touch;
            }

            /* 기본정보 테이블 헤더 개행 방지 */
            .gis-modal-body table th {
                white-space: nowrap;
                min-width: 80px;
            }
        }
      
    `;
    // head에 style 태그 추가
    document.head.appendChild(styleElement);        
}

function preParamEvt(preParam) {
    switch (preParam) {
        case 'traffic':
            $('.gis-list-item')[0].click();
            break;
        case 'incd':
            $('.gis-list-item')[1].click();
            $('.map-quick-btn')[1].click();
            break;
        case 'cctv':
            $('.gis-list-item')[2].click();
            $('.map-quick-btn')[2].click();
            break;
        case 'bus':
            $('.gis-list-item')[3].click();
            break;
        case 'busstop':
            $('.gis-list-item')[4].click();
            $('.map-quick-btn')[3].click();
            break;
        case 'vms':
            $('.gis-list-item')[5].click();
            $('.map-quick-btn')[4].click();
            break;
        case 'parking':
            $('.gis-list-item')[6].click();
            $('.map-quick-btn')[5].click();
            break;
        case 'main-electric':
            $('.gis-list-item')[7].click();
            $('.map-quick-btn')[6].click();
            break;
        case 'main-crossroad':
            $('.gis-list-item')[8].click();
            $('.map-quick-btn')[7].click();
            break;
        case 'school':
            $('.gis-list-item')[9].click();
            $('.map-quick-btn')[8].click();
            break;
        case 'traffic-signal':
            $('.gis-list-item')[10].click();
            $('.map-quick-btn')[9].click();
            break;
    }
}

//버튼 이벤트 등 기본 이벤트 추가
function addEvent() {

    //이벤트 전파 방지
    $('.gis-downmenu-item').on('click', function (event) {
        event.stopPropagation();
    });

    $('.search-input').on('keydown', function (evt) {
        if (evt.key === "Enter") {
            $('#search-btn').click();
        }
    })

    //검색버튼 클릭 이벤트
    $('#search-btn').on('click', function () {
        searchBtnEvt();
    });

    //마커 on/off버튼 이벤트
    $('.map-marker-btn-list button').on('click', function () {
        markerBtnEvt($(this));
    });

    //마커 보이기 숨기기 이벤트
    $('.map-quick-btn').on('click', function () {
        let road = $(this).parent().attr('id') == 'roadOnMap';
        let bStop = $('#busStopOnMap').hasClass('active');
        let bool = $(this).parent().hasClass('active');


        if (road) {
            $.each(VRTX_ARRAY, function (idx, vrtx) {
                if (bool) {
                    vrtx.setMap(oMap);
                    $('.map-legend-box').show();
                } else {
                    vrtx.setMap(null);
                    $('.map-legend-box').hide();
                }

            });
        } else {
            $.each(MARKER_ARRAY[$(this).parent().attr('id')], function (idx, marker) {
                if (bool) {
                    marker.setMap(oMap);
                } else {
                    marker.setMap(null);
                }
            });
        }

        if (bStop) {
            $.each(MARKER_ARRAY.busStopOnMap, function (idx, marker) {
                let lat = oMap.getCenter().getLat();
                let lon = oMap.getCenter().getLng();
                var markerLatlng = marker.getPosition();
                var markerLat = markerLatlng.getLat(); // 위도
                var markerLng = markerLatlng.getLng(); // 경도
                let dist = getDistance(lat, lon, markerLat, markerLng);
                if (dist <= 1000) {
                    marker.setMap(oMap);
                } else {
                    marker.setMap(null);
                }
            });
            setCircleOnMap();
        } else {
            currentCircle.setMap(null);
        }
    });

    $('.gis-downmenu-item').not(':eq(0), :eq(1), :eq(2)').on('click', function () {
        if (matchMedia("screen and (max-width: 1024px)").matches) {
            $('.side-menu .teriary-btn').click();
        }
    });

    $('.gis-downmenu-item-wrap .gis-downmenu-item-02').on('click', function () {
        if (matchMedia("screen and (max-width: 1024px)").matches) {
            $('.side-menu .teriary-btn').click();
        }
    });

    $(window).resize(function () {
        screenFunc();
        setPositionPopup();
    });
};

//지도 생성
let VRTX_INTERVAL;

function createMap() {

    let container = document.querySelector('#map'); //지도를 담을 영역의 DOM 레퍼런스
    let options = { //지도를 생성할 때 필요한 기본 옵션
        center: new kakao.maps.LatLng(37.470564, 126.709545), //지도의 중심좌표.
        level: 6 //지도의 레벨(확대, 축소 정도)
    };

    oMap = new kakao.maps.Map(container, options); //지도 생성 및 객체 리턴
    oMap.setMinLevel(1);
    oMap.setMaxLevel(11);

    let visible = $('#roadOnMap').hasClass('active');
    let bStop = $('#busStopOnMap').hasClass('active');
    if (visible) {
        vrtxFunc();
        VRTX_INTERVAL = setInterval(vrtxFunc, 5000);
    }

    let mapTypeControl = new kakao.maps.MapTypeControl();
    let zoomControl = new kakao.maps.ZoomControl();
    if (!matchMedia("screen and (max-width: 1024px)").matches) {
        oMap.addControl(zoomControl, kakao.maps.ControlPosition.BOTTOMRIGHT);
        oMap.addControl(mapTypeControl, kakao.maps.ControlPosition.BOTTOMRIGHT);
    }else{
        oMap.addControl(mapTypeControl, kakao.maps.ControlPosition.BOTTOMLEFT);
    }



    kakao.maps.event.addListener(oMap, 'idle', function () {

        let zoom = oMap.getLevel();
        let bound = oMap.getBounds();
        let visible = $('#roadOnMap').hasClass('active');
        let bStop = $('#busStopOnMap').hasClass('active');

        if (visible) {
            vrtxFunc();
        }
        if (bStop) {
            setCircleOnMap();
            $.each(MARKER_ARRAY.busStopOnMap, function (idx, marker) {
                let lat = oMap.getCenter().getLat();
                let lon = oMap.getCenter().getLng();
                var markerLatlng = marker.getPosition();
                var markerLat = markerLatlng.getLat(); // 위도
                var markerLng = markerLatlng.getLng(); // 경도
                let dist = getDistance(lat, lon, markerLat, markerLng);
                if (dist <= 1000) {
                    marker.setMap(oMap);
                } else {
                    marker.setMap(null);
                }
            });
        }
    });

  /*  kakao.maps.event.addListener(oMap, 'zoom_changed', () => {
        resizeMarker();
    });*/
}

function resizeMarker() {
    let size;
    let zoomLv = oMap.getLevel();
    size = MARKER.M_SIZE;
   /* if (zoomLv > 8) {
        size = MARKER.S_SIZE;
    } else if (zoomLv > 4) {
        size = MARKER.M_SIZE;
    } else {
        size = MARKER.L_SIZE;
    }*/
    $.each(Object.keys(MARKER_ARRAY), function (idx, item) {
        $.each(MARKER_ARRAY[item], function (idx2, marker) {
            let originPath = marker.getImage().ok;
            let newImg
            if(originPath.includes('-on')){
                newImg = new kakao.maps.MarkerImage(originPath, new kakao.maps.Size(size.W * 1.5, size.H * 1.5));
            }
            else{
                newImg = new kakao.maps.MarkerImage(originPath, new kakao.maps.Size(size.W, size.H));
            }

            marker.setImage(newImg);
        })
    });
}

//데이터호출 이벤트
function dataFunc() {
    getListData('road');
    getListData('cctv');
    getListData('cctvOnMap');
    getListData('incd');
    getListData('incdOnMap');
    getListData('schoolZone');
    getListData('schoolZoneOnMap');
    getListData('vms');
    getListData('vmsOnMap');
    getListData('route');
    getListData('busStop');
    getListData('busStopOnMap');
    getListData('smartCross');
    getListData('smartCrossOnMap');
    getListData('parkingInfo');
    getListData('parkingInfoOnMap');
    getListData('chargerInfo');
    getListData('chargerInfoOnMap');
    getListData('openSignalInfo');
    getListData('openSignalOnMap');

    $.each($('.gis-downmenu-list'), function (idx, item) {
        if ($(item).children().length > 7) {
            $(item).css('height', '300px');
            $(item).css('overflow-y', 'scroll');
        } else {
            $(item).css('height', '');
            $(item).css('overflow-y', '');
        }
        ;
    });
};

//지도 마커 on / off 버튼 이벤트
function markerBtnEvt(ele) {
    let val = ele.val();
    let parentLi = ele.parent();

    let boolActive = parentLi.hasClass('active');

    //active 분기
    if (boolActive == true) {
        parentLi.removeClass('active');
    } else {
        parentLi.addClass('active');
    }
}

//검색버튼 이벤트
function searchBtnEvt() {
    $('.search-input').css('backgroundColor', 'gray');
    $('.search-input').attr('disabled', 'true');
    $('#search-btn').attr('disabled', 'true');
    setTimeout(function () {
        $.each(Object.keys(MARKER_ARRAY), function (idx, item) {
            $.each(MARKER_ARRAY[item], function (i, marker) {
                marker.setMap(null);
            });
        });

        let searchDiv = $('.gis-list-result');
        let searchCntDiv = $('#searchCnt');
        let keywordVisible = $('.keywordVisible');
        searchKeyword = $('.search-input').val();
        searchCnt = 0;
        //검색어 유무 분기
        if (searchKeyword != null && searchKeyword != '') {
            searchDiv.removeClass('hidden');
            keywordVisible.text(searchKeyword);
            dataFunc();
            searchCntDiv.text(searchCnt);
        } else {
            searchDiv.addClass('hidden');
            keywordVisible.text('');
            dataFunc();
            searchCntDiv.text(0);
        }
        $('.search-input').css('backgroundColor', '');
        $('.search-input').removeAttr('disabled');
        $('#search-btn').removeAttr('disabled');
    }, 100);

};

//데이터 호출 이벤트
function getListData(type) {

    let param = {type: type, keyword: searchKeyword,};

    if (type == 'busStopOnMap') {
        param.lat = oMap.getCenter().getLat();
        param.lon = oMap.getCenter().getLng();
        param.radius = 1000;
    }

    $.ajax({
        url: "/gis/selectListData.do", method: 'POST', async: false, data: param, success: (res) => {
            let data = JSON.parse(res).result;
            setListData(type, data);
        }, error: (jqXHR, textStatus, errorThrown) => {
            console.warn('[GIS] 목록 데이터 요청 실패:', textStatus, (jqXHR && jqXHR.status) || '');
        }
    });
};

//데이터 세팅 분기처리   
function setListData(type, data) {
    switch (type) {
        case 'road':
            setCommuRoadInfo(data);
            break;

        case 'cctv':
            data.sort((a, b) => a.CCTV_NM.localeCompare(b.CCTV_NM, 'ko'));
            setCctvInfo(data)
            break;

        case 'cctvOnMap':
            createMarker(data, type, MARKER.CCTV);
            break;

        case 'incd':
            setIncdInfo(data);
            break;

        case 'incdOnMap':
            createMarker(data, type, MARKER.INCD);
            break;

        case 'schoolZone':
            setSchoolZoneInfo(data);
            break;

        case 'schoolZoneOnMap':
            createMarker(data, type, MARKER.SCHOOL);
            break;

        case 'vms':
            data.sort((a, b) => a.VMS_NM.localeCompare(b.VMS_NM, 'ko'));
            setBusStopInfo(data);
            setVmsInfo(data);
            break;

        case 'vmsOnMap':
            createMarker(data, type, MARKER.VMS);
            break;

        case 'route':
            setRouteInfo(data);
            break;

        case 'busStop':
            data.sort((a, b) => a.BSTOPNM.localeCompare(b.BSTOPNM, 'ko'));
            setBusStopInfo(data);
            break;

        case 'busStopOnMap':
            createMarker(data, type, MARKER.BUSSTOP);
            break;

        case 'smartCross':
            setSmartCrossInfo(data);
            break;

        case 'smartCrossOnMap':
            createMarker(data, type, MARKER.SMART);
            break;

        case 'vrtx':
            setVrtxInfo(data);
            break;

        case 'parkingInfo':
            setParkingInfo(data);
            break;

        case 'parkingInfoOnMap':
            createMarker(data, type, MARKER.PARKING);
            break;

        case 'chargerInfo':
            setChargerInfo(data);
            break;

        case 'chargerInfoOnMap':
            createMarker(data, type, MARKER.CHARGER);
            break;

        case  'openSignalInfo':
            setOpenSignalInfo(data);
            break;
        case 'openSignalOnMap':
            createMarker(data, type, MARKER.SIGNAL);
            break;

    }
};

//상세 팝업 이벤트 데이터
function getDetailRoadName(type, value) {
    let url = '/gis/selectDetailRoadName.do';
    $.ajax({
        url: url,
        method: 'POST',
        data: {type: type, roadNm: value},
        dataType: 'json',
        async: false,
        beforeSend: initDetailRoadName(),
        success: (res) => {
            let data = JSON.parse(res);
            ROADNAME = value;
            setRoadDetail(data); //소통정보 상세 팝업 생성
            vrtxFunc(value);
        },
        error: (err) => {
            console.warn('[GIS] 요청 실패:', (err && err.status) || '', (err && err.statusText) || err);
        }
    });
};

//선택된 노선별 정류장 마커 표기
function createRouteBstopMarker(bStop) {

    if (ROUTE_MARKER_ARRAY.length != 0) {
        $.each(ROUTE_MARKER_ARRAY, (idx, item) => {
            item.setMap(null);
            ROUTE_MARKER_ARRAY = [];
        });
    }
    ;

    let zoomLvSize;
    let zoomLv = oMap.getLevel();
    zoomLvSize = MARKER.M_SIZE;
    // if (zoomLv > 8) {
    //     zoomLvSize = MARKER.S_SIZE;
    // } else if (zoomLv > 4) {
    //     zoomLvSize = MARKER.M_SIZE;
    // } else {
    //     zoomLvSize = MARKER.L_SIZE;
    // }

    let size = new kakao.maps.Size(zoomLvSize.W, zoomLvSize.H);
    let point = new kakao.maps.Point(zoomLvSize.W / 2, zoomLvSize.H);

    $.each(bStop, function (index, item) {
        let marker = new kakao.maps.Marker({
            position: new kakao.maps.LatLng(item.LAT, item.LNG),
            image: new kakao.maps.MarkerImage(MARKER.BUSSTOP, size, point),
            title: item.NODENM,
        });
        marker.data = {id:item.BSTOPID};
        marker.setMap(oMap);
        setRouteStopMarkerEvent(marker, item.BSTOPID, bStop);
        ROUTE_MARKER_ARRAY.push(marker);
    });
};

//선택된 노선 정류장 마커 이벤트
function setRouteStopMarkerEvent(mMarker, bStopId, data) {
    kakao.maps.event.addListener(mMarker, 'click', function (mouseEvent) {
        if (ROUTE_INTERVAL != null) {
            clearInterval(ROUTE_INTERVAL);
        }
        let bStop = data.find(item => item.BSTOPID == bStopId);
        getRealtimeBusData();
        changeMarkerImageAll(mMarker, MARKER.BUSSTOP, MARKER.BUSSTOP_SEL);
        getBstopDetail2(bStop);
    });
}


//마커 이미지 공통이벤트
function changeMarkerImageAll(thisMarker, beforeImg, afterImg) {

    let zoomLvSize;
    let zoomLv = oMap.getLevel();
    zoomLvSize = MARKER.M_SIZE;
  /*  if (zoomLv > 8) {
        zoomLvSize = MARKER.S_SIZE;
    } else if (zoomLv > 4) {
        zoomLvSize = MARKER.M_SIZE;
    } else {
        zoomLvSize = MARKER.L_SIZE;
    }*/

    var img = afterImg;
    var size = new kakao.maps.Size(zoomLvSize.W, zoomLvSize.H);
    var zoomSize = new kakao.maps.Size(zoomLvSize.W * 2, zoomLvSize.H * 2);
    var point = new kakao.maps.Point(zoomLvSize.W / 2, zoomLvSize.H);
    var zoomPoint = new kakao.maps.Point(zoomLvSize.W, zoomLvSize.H * 2);
    var markerImage = new kakao.maps.MarkerImage(img, zoomSize, zoomPoint);
    if (selectedMarker.marker != null) {
        //이전에 선택한 마커가 있으면 되돌리기
        var beforeMarkerImage = new kakao.maps.MarkerImage(selectedMarker.beforeImg, size, point);
        selectedMarker.marker.setImage(beforeMarkerImage);
        selectedMarker.marker.setZIndex(0);
    }
    //선택한 마커 이미지 변환
    thisMarker.setImage(markerImage);
    thisMarker.setZIndex(1);

    //선택한 마커 정보 기록
    selectedMarker.beforeImg = beforeImg;
    selectedMarker.marker = thisMarker;
}


//마커표기 이벤트
function createMarker(data, type, markerImg) {

    let zoomLvSize;
    let zoomLv = oMap.getLevel();
    zoomLvSize = MARKER.M_SIZE;
   /* if (zoomLv > 8) {
        zoomLvSize = MARKER.S_SIZE;
    } else if (zoomLv > 4) {
        zoomLvSize = MARKER.M_SIZE;
    } else {
        zoomLvSize = MARKER.L_SIZE;
    }*/


    let visible = $('#' + type).hasClass('active');
    let marker = null;
    let img = markerImg;
    let size = new kakao.maps.Size(zoomLvSize.W, zoomLvSize.H);
    let rbus_size = new kakao.maps.Size(zoomLvSize.W * 1.5, zoomLvSize.H * 1.5);
    let point = new kakao.maps.Point(zoomLvSize.W / 2, zoomLvSize.H);

    if (MARKER_ARRAY['realtimeBusOnMap'] != null) {
        $.each(MARKER_ARRAY['realtimeBusOnMap'], function (idx, marker) {
            marker.setMap(null);
        });
    }
    ;

    MARKER_ARRAY[type] = new Array();
    $.each(data, function (index, item) {
        if (item.Y_CRDN == null) {
            item.Y_CRDN = item.LAT;
            item.X_CRDN = item.LNG;
        }
        ;

        marker = new kakao.maps.Marker({
            position: new kakao.maps.LatLng(item.Y_CRDN, item.X_CRDN),
            image: new kakao.maps.MarkerImage(img, size, point),
        });

        switch (type) {
            case 'busStopOnMap':
                //추후에 원 내부에 있는 것만 표시하도록 수정
                let lat = oMap.getCenter().getLat();
                let lon = oMap.getCenter().getLng();
                var markerLatlng = marker.getPosition();
                var markerLat = markerLatlng.getLat(); // 위도
                var markerLng = markerLatlng.getLng(); // 경도
                let dist = getDistance(lat, lon, markerLat, markerLng);
                marker.data = {id: item.BSTOPID}
                if (visible) {
                    if (dist <= 1000) {
                        marker.setMap(oMap);
                    }
                }
                setStopMarkerEvent(marker, item.BSTOPID, data);
                break;
            case 'incdOnMap':
                marker.title = item.INCIDENTID;
                if (visible) {
                    marker.setMap(oMap);
                }
                setIncdEvent(marker, item.INCIDENTID, data);
                break;
            case 'cctvOnMap':
                marker.title = item.CCTV_NM
                if (visible) {
                    marker.setMap(oMap);
                }
                setCctvEvent(marker, item.CCTV_MNGM_NMBR, data);
                break;
            case 'schoolZoneOnMap':
                marker.title = item.SEQ
                if (visible) {
                    marker.setMap(oMap);
                }
                setSchoolZoneEvent(marker, item.SEQ, data);
                break;
            case 'vmsOnMap':
                marker.title = item.VMS_CTLR_ID;
                if (visible) {
                    marker.setMap(oMap);
                }
                setVmsEvent(marker, item.VMS_CTLR_ID, data);
                break;
            case 'realtimeBusOnMap':
                if (item.LOWPLATEYN == 1) {
                    if(item.DIRCD == 0){
                        img = MARKER.UP_LOW_BUS;
                    }else{
                        img = MARKER.DOWN_LOW_BUS;
                    }

                } else {
                    if(item.DIRCD == 0) {
                        img = MARKER.UP_BUS;
                    }else{
                        img = MARKER.DOWN_BUS;
                    }
                }
                marker = new kakao.maps.Marker({
                    position: new kakao.maps.LatLng(item.Y_CRDN, item.X_CRDN),
                    image: new kakao.maps.MarkerImage(img, rbus_size, point),
                });

                if (marker != null) {
                    marker.setMap(null);
                }
                marker.setMap(oMap);
                break;
            case 'busStopOnMap':
                if (visible) {
                    marker.setMap(oMap);
                }
                break;
            case 'parkingInfoOnMap':
                item.Y_CRDN = item.LAT;
                item.X_CRDN = item.LON;

                marker = new kakao.maps.Marker({
                    position: new kakao.maps.LatLng(item.Y_CRDN, item.X_CRDN),
                    image: new kakao.maps.MarkerImage(img, size, point),
                });
                marker.title = item.PK_ID;

                if (visible) {
                    marker.setMap(oMap);
                }
                setParkingInfoEvent(marker, item.PK_ID, data);
                break;
            case 'smartCrossOnMap':
                marker.title = item.SPOT_SRVR_NM;
                if (visible) {
                    marker.setMap(oMap);
                }
                setSmartCrossMarkerEvent(marker, item.SPOT_CAMR_ID, data);
                break;
            case 'chargerInfoOnMap':
                marker.title = item.STAT_ID;
                if (visible) {
                    marker.setMap(oMap);
                }
                setChargerInfoEvent(marker, item.STAT_ID, data);
                break;
            case 'openSignalOnMap':
                marker.title = item.NODE_ID;
                if (visible) {
                    marker.setMap(oMap);
                }
                setOpenSignalEvent(marker, item.NODE_ID, data);
                break;
            default:
                if (visible) {
                    marker.setMap(oMap);
                }
                break;
        }
        MARKER_ARRAY[type].push(marker);
    });
}

//지도 중심으로부터 1000미터 이내인지 확인
function getDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // 지구 반지름 (km)
    const dLat = deg2rad(lat2 - lat1);
    const dLon = deg2rad(lon2 - lon1);
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(deg2rad(lat1)) * Math.cos(deg2rad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const d = R * c * 1000; // 거리 (m)
    return d;
}

function deg2rad(deg) {
    return deg * (Math.PI / 180);
}

//소통정보 도로데이터 카테고리 표기
function setCommuRoadInfo(data) {
    searchCnt += data.length;
    $('#comCnt').text(data.length);
    let type1 = data.filter(item => item.ATRD_TYPE === 1);
    let type2 = data.filter(item => item.ATRD_TYPE === 2);
    let type3 = data.filter(item => item.ATRD_TYPE === 3);

    /*$('#highWayInfo').children().not('summary').remove();
    $('#mainRoadInfo').children().not('summary').remove();
    $('#subRoadInfo').children().not('summary').remove();*/

    type1.forEach((item) => {
        $('#highWayInfo').append('<li class="gis-downmenu-item-02">' + item.ROAD_NM + '</li>');
    });

    type2.forEach((item) => {
        $('#mainRoadInfo').append('<li class="gis-downmenu-item-02">' + item.ROAD_NM + '</li>');
    });

    type3.forEach((item) => {
        $('#subRoadInfo').append('<li class="gis-downmenu-item-02">' + item.ROAD_NM + '</li>');
    });

    //각 도로명 별로 이벤트 부여
    $('.gis-downmenu-item-02').on('click', function () {
        removeAllEvtPop();
        $('.map-marker-btn-item.active').children().not(':first').click();
        if (!$('#roadOnMap').hasClass('active')) {
            $('#roadOnMap').addClass('active');
        }
        ;getDetailRoadName('road', $(this).text());
    });
};

//돌발정보 카테고리 표기
function setIncdInfo(data) {
    searchCnt += data.length;
    $('#incdCnt').text(data.length);
    $('#incdList').empty();
    data.forEach((item) => {
        $('#incdList').append('<a class="gis-downmenu-item" id=' + item.INCIDENTID + '><h5>[' + item.CODE_NAME + ']</h3><br/>' + item.ACCIDENT_TEXT.substring(4) + '</a>')
    });
    $('#incdList .gis-downmenu-item').on('click', function () {
        removeAllEvtPop();
        if($('#roadOnMap').hasClass('active')){
            $('.map-marker-btn-item.active').children().not(':first').click();
            if (!$('#incdOnMap').hasClass('active')) {
                $('#incdOnMap .map-quick-btn').click();
            }
        }
        else{
            $('.map-marker-btn-item.active').children().click();
            if (!$('#incdOnMap').hasClass('active')) {
                $('#incdOnMap .map-quick-btn').click();
            }
        }
        let incd = data.find(item => item.INCIDENTID == $(this).attr('id'));
        let mMarker = MARKER_ARRAY.incdOnMap.find(marker => marker.title == incd.INCIDENTID);
        if (mMarker != null) {
            changeMarkerImageAll(mMarker, MARKER.INCD, MARKER.INCD_SEL);
        }
        setDetailIncd(incd);
    });
}

//돌발 마커 이벤트
function setIncdEvent(mMarker, incdId, data) {
    kakao.maps.event.addListener(mMarker, 'click', function (mouseEvent) {
        removeAllEvtPop();
        let incd = data.find(item => item.INCIDENTID == incdId);
        changeMarkerImageAll(mMarker, MARKER.INCD, MARKER.INCD_SEL);
        setDetailIncd(incd);
    });
}

//cctv 카테고리 표기
function setCctvInfo(data) {
    searchCnt += data.length;
    $('#cctvCnt').text(data.length);
    $('#cctvList').empty();
    data.forEach((item) => {
        $('#cctvList').append('<a class="gis-downmenu-item" id=' + item.CCTV_MNGM_NMBR + '>' + item.CCTV_NM + '</a>')
    });
    $('#cctvList .gis-downmenu-item').on('click', function () {
        removeAllEvtPop();
        if($('#roadOnMap').hasClass('active')) {
            $('.map-marker-btn-item.active').children().not(':first').click();
            if (!$('#cctvOnMap').hasClass('active')) {
                $('#cctvOnMap .map-quick-btn').click();
            }
        }
        else{
            $('.map-marker-btn-item.active').children().click();
            if (!$('#cctvOnMap').hasClass('active')) {
                $('#cctvOnMap .map-quick-btn').click();
            }
        }
        let cctv = data.find(item => item.CCTV_MNGM_NMBR == $(this).attr('id'));
        let cctvMarker = MARKER_ARRAY.cctvOnMap.find(item => item.title == $(this).text());
        if (cctvMarker != null) {
            changeMarkerImageAll(cctvMarker, MARKER.CCTV, MARKER.CCTV_SEL);
        }
        setDetailCctv(cctvMarker, cctv);
    });
};

//cctv 마커 이벤트
function setCctvEvent(mMarker, cctvNmbr, data) {
    kakao.maps.event.addListener(mMarker, 'click', function (mouseEvent) {
        removeAllEvtPop();
        let cctv = data.find(item => item.CCTV_MNGM_NMBR == cctvNmbr);
        changeMarkerImageAll(mMarker, MARKER.CCTV, MARKER.CCTV_SEL);
        setDetailCctv(mMarker, cctv);
    });
}

//어린이보호구역 카테고리 표기
function setSchoolZoneInfo(data) {
    searchCnt += data.length;
    $('#schoolZoneCnt').text(data.length);
    $('#schoolZoneList').empty();
    data.forEach((item) => {
        $('#schoolZoneList').append('<a class="gis-downmenu-item" id=' + item.SEQ + '>' + item.ZONE_NAME + '</a>')
    });
    $('#schoolZoneList .gis-downmenu-item').on('click', function () {
        removeAllEvtPop();
        if($('#roadOnMap').hasClass('active')) {
            $('.map-marker-btn-item.active').children().not(':first').click();
            if (!$('#schoolZoneOnMap').hasClass('active')) {
                $('#schoolZoneOnMap .map-quick-btn').click();
            }
        }
        else{
            $('.map-marker-btn-item.active').children().click();
            if (!$('#schoolZoneOnMap').hasClass('active')) {
                $('#schoolZoneOnMap .map-quick-btn').click();
            }
        }
        let schoolZone = data.find(item => item.SEQ == $(this).attr('id'));
        schoolZone.Y_CRDN = schoolZone.LATITUDE;
        schoolZone.X_CRDN = schoolZone.LONGITUDE;

        let mMarker = MARKER_ARRAY.schoolZoneOnMap.find(marker => marker.title == schoolZone.SEQ);
        if (mMarker != null) {
            changeMarkerImageAll(mMarker, MARKER.SCHOOL, MARKER.SCHOOL_SEL);
        }

        setDetailSchoolZone(schoolZone);
    });
};

//어린이보호구역 마커 이벤트
function setSchoolZoneEvent(mMarker, seq, data) {
    kakao.maps.event.addListener(mMarker, 'click', function (mouseEvent) {
        removeAllEvtPop();
        let schoolZone = data.find(item => item.SEQ == seq);
        changeMarkerImageAll(mMarker, MARKER.SCHOOL, MARKER.SCHOOL_SEL);
        setDetailSchoolZone(schoolZone);
    });
}

//vms 카테고리 표기
function setVmsInfo(data) {
    searchCnt += data.length;
    $('#vmsCnt').text(data.length);
    $('#vmsList').empty();
    data.forEach((item) => {
        $('#vmsList').append('<a class="gis-downmenu-item" id=' + item.VMS_CTLR_ID + '>' + item.VMS_NM + '</a>')
    });
    $('#vmsList .gis-downmenu-item').on('click', function () {
        removeAllEvtPop();
        if($('#roadOnMap').hasClass('active')) {
            $('.map-marker-btn-item.active').children().not(':first').click();
            if (!$('#vmsOnMap').hasClass('active')) {
                $('#vmsOnMap .map-quick-btn').click();
            }
        }
        else{
            $('.map-marker-btn-item.active').children().click();
            if (!$('#vmsOnMap').hasClass('active')) {
                $('#vmsOnMap .map-quick-btn').click();
            }
        }
        let vms = data.find(item => item.VMS_CTLR_ID == $(this).attr('id'));

        let mMarker = MARKER_ARRAY.vmsOnMap.find(marker => marker.title == vms.VMS_CTLR_ID);
        if (mMarker != null) {
            changeMarkerImageAll(mMarker, MARKER.VMS, MARKER.VMS_SEL);
        }

        getDetailVms(vms);
    });
};

//vms 마커 이벤트
function setVmsEvent(mMarker, vmsId, data) {
    kakao.maps.event.addListener(mMarker, 'click', function (mouseEvent) {
        removeAllEvtPop();
        let vms = data.find(item => item.VMS_CTLR_ID == vmsId);
        changeMarkerImageAll(mMarker, MARKER.VMS, MARKER.VMS_SEL);
        getDetailVms(vms);
    });
};

//노선 카테고리 표기
function setRouteInfo(originData) {
    let data = Array.from(new Map(originData.map(item => [item.ROUTEID, item])).values());
    data.sort((a, b) => {
        const regex = /^(\d+)(.*)$/;

        const aMatch = a.ROUTENO.match(regex);
        const bMatch = b.ROUTENO.match(regex);

        const aIsNumber = aMatch !== null;
        const bIsNumber = bMatch !== null;

        if (aIsNumber && !bIsNumber) return -1;
        if (!aIsNumber && bIsNumber) return 1;

        if (aIsNumber && bIsNumber) {
            const aNum = parseInt(aMatch[1], 10);
            const bNum = parseInt(bMatch[1], 10);

            if (aNum !== bNum) {
                return aNum - bNum;
            }

            const aStr = aMatch[2];
            const bStr = bMatch[2];
            return aStr.localeCompare(bStr);
        }

        return a.ROUTENO.localeCompare(b.route);
    });


    searchCnt += data.length;
    $('#routeCnt').text(data.length);
    $('#routeList').empty();
    data.forEach((item) => {
        $('#routeList').append('<a class="gis-downmenu-item" id=' + item.ROUTEID + '>' + item.ROUTENO + '</a>')
    });
    $('#routeList .gis-downmenu-item').on('click', function () {
        removeAllEvtPop();
        //$('.map-marker-btn-item.active').children().not(':first').click();
        let route = data.find(item => item.ROUTEID == $(this).attr('id'));
        getRouteDetail(route);
    });
};

//정류장 카테고리 표기
function setBusStopInfo(data) {
    searchCnt += data.length;
    $('#busStopCnt').text(data.length);
    $('#busStopList').empty();
    data.forEach((item) => {
        $('#busStopList').append('<a class="gis-downmenu-item" id=' + item.BSTOPID + ' short=' + item.SHORT_BSTOPID + '>' + item.BSTOPNM + '</a>')
    });
    $('#busStopList .gis-downmenu-item').on('click', function (eve, from) {
        removeAllEvtPop();
        if($('#roadOnMap').hasClass('active')) {
            $('.map-marker-btn-item.active').children().not(':first').click();
            if (!$('#busStopOnMap').hasClass('active')) {
                $('#busStopOnMap .map-quick-btn').click();
            }
        }
        else{
            $('.map-marker-btn-item.active').children().click();
            if (!$('#busStopOnMap').hasClass('active')) {
                $('#busStopOnMap .map-quick-btn').click();
            }
        }
        let mMarker = MARKER_ARRAY['busStopOnMap'].find(item => item.data.id == $(this).attr('id'));
        changeMarkerImageAll(mMarker, MARKER.BUSSTOP, MARKER.BUSSTOP_SEL);

        let bStop = data.find(item => item.BSTOPID == $(this).attr('id'));

        from === true ? getBstopDetail2(bStop) : getBstopDetail(bStop);

    });
};

//정류장 마커 이벤트
function setStopMarkerEvent(mMarker, bStopId, data) {
    kakao.maps.event.addListener(mMarker, 'click', function (mouseEvent) {
        if (ROUTE_INTERVAL != null) {
            clearInterval(ROUTE_INTERVAL);
        }
        let bStop = data.find(item => item.BSTOPID == bStopId);
        removeAllEvtPop();
        changeMarkerImageAll(mMarker, MARKER.BUSSTOP, MARKER.BUSSTOP_SEL);
        getBstopDetail(bStop);
    });
}

//스마트교차로 카테고리 표기
function setSmartCrossInfo(data) {
    searchCnt += data.length;
    $('#smartCrossCnt').text(data.length);
    $('#smartCrossList').empty();
    data.forEach((item) => {
        $('#smartCrossList').append('<a class="gis-downmenu-item" id=' + item.SPOT_CAMR_ID + '>' + item.SPOT_SRVR_NM + '</a>')
    });
    $('#smartCrossList .gis-downmenu-item').on('click', function () {
        removeAllEvtPop();
        if($('#roadOnMap').hasClass('active')) {
            $('.map-marker-btn-item.active').children().not(':first').click();
            if (!$('#smartCrossOnMap').hasClass('active')) {
                $('#smartCrossOnMap .map-quick-btn').click();
            }
        }
        else{
            $('.map-marker-btn-item.active').children().click();
            if (!$('#smartCrossOnMap').hasClass('active')) {
                $('#smartCrossOnMap .map-quick-btn').click();
            }
        }
        let smart = data.find(item => item.SPOT_CAMR_ID == $(this).attr('id'));
        let smartMarker = MARKER_ARRAY.smartCrossOnMap.find(item => item.title == $(this).text());

        if (smartMarker != null) {
            changeMarkerImageAll(smartMarker, MARKER.SMART, MARKER.SMART_SEL);
        }

        getSmartCrossDetail(smart, smartMarker);
    });
};


//스마트 교차로 마커 이벤트
function setSmartCrossMarkerEvent(mMarker, smartId, data) {
    kakao.maps.event.addListener(mMarker, 'click', function (mouseEvent) {
        removeAllEvtPop();
        let smart = data.find(item => item.SPOT_CAMR_ID == smartId);
        changeMarkerImageAll(mMarker, MARKER.SMART, MARKER.SMART_SEL);
        getSmartCrossDetail(smart, mMarker);
    });
}

//주차장 카테고리 표기
function setParkingInfo(data) {
    searchCnt += data.length;
    $('#parkingCnt').text(data.length);
    $('#parkingList').empty();
    data.forEach((item) => {
        $('#parkingList').append('<a class="gis-downmenu-item" id=' + item.PK_ID + '>' + item.PK_NAME + '</a>')
    });
    $('#parkingList .gis-downmenu-item').on('click', function () {
        removeAllEvtPop();
        if($('#roadOnMap').hasClass('active')) {
            $('.map-marker-btn-item.active').children().not(':first').click();
            if (!$('#parkingInfoOnMap').hasClass('active')) {
                $('#parkingInfoOnMap .map-quick-btn').click();
            }
        }
        else{
            $('.map-marker-btn-item.active').children().click();
            if (!$('#parkingInfoOnMap').hasClass('active')) {
                $('#parkingInfoOnMap .map-quick-btn').click();
            }
        }

        let parking = data.find(item => item.PK_ID == $(this).attr('id'));
        parking.Y_CRDN = parking.LAT;
        parking.X_CRDN = parking.LON;

        let mMarker = MARKER_ARRAY.parkingInfoOnMap.find(marker => marker.title == parking.PK_ID);
        if (mMarker != null) {
            changeMarkerImageAll(mMarker, MARKER.PARKING, MARKER.PARKING_SEL);
        }

        let param = {type: 'parkingDetail', parkId: parking.PK_ID}
        $.ajax({
            url: "/gis/selectListData.do",
            method: 'POST',
            async: false,
            data: param, success: (res) => {
                let data = JSON.parse(res).result;
                setDetailParkingInfo(data[0]);
            }, error: (err) => {
                console.warn('[GIS] 요청 실패:', (err && err.status) || '', (err && err.statusText) || err);
            }
        });


    });
};

//주차장 상세 팝업 표기
function setDetailParkingInfo(parking) {
    parking.Y_CRDN = parking.LAT;
    parking.X_CRDN = parking.LON;
    const $popup = $('.popInfoWrap');
    $popup.html("");
    if (parking == null || parking == undefined) {
        console.log('주차장 상세정보 데이터 없음');
        $popup.hide();
        return;
    }
    console.log("==================================>>parking.LOTS_FREE ::",parking.LOTS_FREE );
    if(parking.LOTS_FREE == null || parking.LOTS_FREE== undefined) {
        parking.LOTS_FREE = 0;
    }
    if(parking.ON_OFF == 'N') {
        parking.LOTS_FREE = '미제공';
    }
    if(parking.TEL == null || parking.TEL== undefined) {
        parking.TEL = '-';
    }

    $popup.empty();
    $popup.show();
    
    
    const popupHTML = `
   <div class="parking-card gis-modal parking-modal">
      <div class="gis-modal-header">
        <div class="d-flex space-between gap">
          <div>
            <div class="d-flex align-center gap-xs">
              <h2>${parking.PK_NAME}</h2>
              <p class="label label-xs label-success body-s">${parking.TYPE}</p>
              ${checkLand(parking.LAND)}
            </div>
            <h5 class="secondary-txt">관리기관 : ${parking.MANAGEMENT}</h5>
            <h5 class="secondary-txt">연락처 : ${parking.TEL}</h5>
            <h5 class="secondary-txt">제공시간 : ${parking.UPD_DATE}</h5>
          </div>
          <div class="refresh-icon" onclick="refreshData('${parking.PK_ID}')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
            </svg>
            <span class="refresh-number" id="counterNumber">30</span>
          </div>
          <button type="button" class="button img-btn gis-modal-close-btn">
            <img src="/images/icthome/icon-close.svg" class="invert" alt="닫기" onclick="closePopinfo()"/>
          </button>
        </div>
      </div>
      <div class="gis-modal-body">
        <div class="mb-1">
          <div class="d-flex align-center gap-xs mb-xs">
            ${parking.CONGESTION !== null ? '': `<p class="label label-xs label-secondary-light">실시간</p>`}
            <h4>주차정보</h4>
          </div>
          <div class="stats-container">
                <div class="stat-box available">
                    <div class="stat-label">여유 주차면</div>
                    <div class="stat-number">${parking.LOTS_FREE}</div>
                </div>
                <div class="stat-box total">
                    <div class="stat-label">전체 주차면</div>
                    <div class="stat-number">${parking.TOTAL_LOTS}</div>
                </div>
           </div>          
          </br>
          <table class="w-100 txt-center">
            <tbody><tr>
              <th rowspan="6">
                전체 면수<br>
                <h3 class="primary-txt">${parking.TOTAL_LOTS}</h3>
              </th>
              <th>구분</th>
              <th>사용면수</th>
              <th>혼잡도</th>
            </tr>
            <tr>
              <td class="thead">일반</td>
              <td>${parking.BASICS_LOTS}</td>
              ${checkCongestion(parking.CONGESTION)}
            </tr>
            <tr>
              <td class="thead">장애인</td>
              <td>${parking.HANDICAP_LOTS}</td>
            </tr>
            <tr>
              <td class="thead">경차</td>
              <td>${parking.COMPACT_LOTS}</td>
            </tr>
            <tr>
              <td class="thead">전기</td>
              <td>${parking.ELECTRIC_LOTS}</td>
            </tr>
            <tr>
              <td class="thead">특수차량</td>
              <td> - </td>
            </tr>
          </tbody></table>
        </div>
        <div class="mb-1">
          <h4 class="mb-xs">기본정보</h4>
          <table class="w-100 txt-center">
            <tbody><tr>
              <th style="white-space: nowrap;">주소</th>
              <td colspan="2">${parking.ADDR1}</td>
            </tr>
            <tr>
              <th rowspan="3" style="white-space: nowrap;">운영시간</th>
              <td class="thead">평일</td>
              <td>${parking.WEEK_HOURS}</td>
            </tr>
            <tr>
              <td class="thead">토요일</td>
              <td>${parking.SATUR_HOURS}</td>
            </tr>
            <tr>
              <td class="thead">일요일</td>
              <td>${parking.HOLI_HOURS}</td>
            </tr>
            <tr>
              <th rowspan="2" style="white-space: nowrap;">주차요금</th>
              <td class="thead">기본</td>
              <td>${parking.FEE}</td>
            </tr>
            <tr>
              <td class="thead">추가</td>
              <td>${parking.ADD_FEE}</td>
            </tr>
          </tbody></table>
        </div>
        <div>
          ${parking.ETC == null ? '' : `<h4 class="mb-xs">안내사항</h4><p>${parking.ETC}</p>`}
        </div>
      </div>
    </div>
    `;
    $popup.html(popupHTML);
    centerRelayout(parking.Y_CRDN, parking.X_CRDN);  // 지도 위치 재조정
    
    // 카운터 시작 (기존 카운터가 있으면 정리)
    if (counterInterval) {
        clearInterval(counterInterval);
    }
    startCounter(parking.PK_ID,parking.ON_OFF);
}

function startCounter(parkId,onOff) {
    console.log("==============================startCounter>>:",parkId+":"+onOff);
    if(onOff == 'N'){
        $(".refresh-icon").css("display", "none");
        return;
    }
    
    // 1초마다 카운터 감소 (30에서 1까지)
    counterInterval = setInterval(() => {
        counter--;
        // 카운터가 0이 되면 자동 새로고침 후 30으로 리셋
        if (counter < 1) {
            counter = 30;
            updateCounterDisplay();
            // 자동 새로고침 실행
            updateParkingInfo(parkId);
            return;
        }
        updateCounterDisplay();
    }, 1000);
}
function updateCounterDisplay() {
    const counterElement = document.getElementById('counterNumber');
    
    // 애니메이션 클래스 추가
    counterElement.classList.add('updating');
    
    // 숫자 업데이트
    counterElement.textContent = counter;
    
    // 애니메이션 종료 후 클래스 제거
    setTimeout(() => {
        counterElement.classList.remove('updating');
    }, 400);
}
function refreshData(parkId) {
    console.log("==============================refreshData>>:",parkId);
    // 새로고침 로직 구현
    const counterElement = document.getElementById('counterNumber');
    
    // 카운터를 30으로 리셋
    counter = 30;
    updateCounterDisplay();
    
    // 주차 정보도 랜덤하게 업데이트
    updateParkingInfo(parkId);
}

function updateParkingInfo(parkId) {
    console.log("==============================updateParkingInfo>>:",parkId);
    // 카드 전체 플래시 효과
    const parkingCard = document.querySelector('.parking-card');
    parkingCard.classList.add('refreshing');
    
    setTimeout(() => {
        parkingCard.classList.remove('refreshing');
    }, 500);
    
    // 여유 공간 랜덤 업데이트 (700-900 사이)
    const availableSpace = Math.floor(Math.random() * 201) + 700;
    //document.querySelector('.stat-box.available .stat-number').textContent = availableSpace;
    
    // 애니메이션 효과
    const statBoxes = document.querySelectorAll('.stat-box');
    statBoxes.forEach(box => {
        box.style.transform = 'scale(1.05)';
        setTimeout(() => {
            box.style.transform = 'scale(1)';
        }, 200);
    });
   let param = {type: 'parkingDetail', parkId: parkId}
    $.ajax({
        url: "/gis/selectListData.do",
        method: 'POST',
        async: false,
        data: param, success: (res) => {
            let data = JSON.parse(res).result;
            setDetailParkingInfo(data[0]);
        }, error: (err) => {
            console.warn('[GIS] 요청 실패:', (err && err.status) || '', (err && err.statusText) || err);
        }
    });    
}






function checkPublic(type){
    if(type != null){
        return `<p class="label label-xs label-success body-s">공영</p>`
    }
}
function checkLand(land) {
console.log("=========================checkLand>>>:",land);
    switch (land) {
        case '무료':
            return `<p class="label label-xs label-info body-s">무료</p>`;
        case '1급지':
            return `<p class="label label-xs label-caution body-s">1급지</p>`;
        case '2급지':
            return `<p class="label label-xs label-warning body-s">2급지</p>`;
        case '3급지':
            return `<p class="label label-xs label-danger body-s">3급지</p>`;
        default:
            return ``;
    }
}


function roadName(parking) {
    var arr = [parking.ADDR1, parking.ADDR2];
    var arr2 = '';
    for (var i = 0; i < arr.length; i++) {
        if (arr[i] == undefined) {
            break;
        } else {
            arr2 += arr[i] + ' ';
        }
    }
    return arr2.trim();
}

function checkCongestion(con) {
    if(con == '원활'){
        return `<td rowSpan="5" className="h5 parking-status-info">원활</td>`
    }else if(con == '혼잡'){
        return `<td rowSpan="5" className="h5 parking-status-danger">혼잡</td>`
    }else if(con == '만차'){
        return `<td rowSpan="5" className="h5 parking-status-danger">만차</td>`
    }else{//2025-12-31 이전로직
        if(con == '3'){
           return `<td rowSpan="5" className="h5 parking-status-danger">혼잡</td>`
        }
        else if(con == '2'){
            return `<td rowSpan="5" className="h5 parking-status-caution">보통</td>`
        }
        else if(con == '1') {
            return `<td rowSpan="5" className="h5 parking-status-info">원활</td>`
        }
        else{
            return `<td rowSpan="5" className="h5">미제공</td>`
        }
    }    
}

function udCheck(value, defaultValue = '-') {
    return (value == undefined || value == null || value == '') ? defaultValue : value;
}


//주차장 마커 이벤트
function setParkingInfoEvent(mMarker, parkingId, data) {
    kakao.maps.event.addListener(mMarker, 'click', function (mouseEvent) {
        removeAllEvtPop();
        let parking = data.find(item => item.PK_ID == parkingId);
        changeMarkerImageAll(mMarker, MARKER.PARKING, MARKER.PARKING_SEL);
        setDetailParkingInfo(parking);
    });
};

//충전소 마커 이벤트
function setChargerInfoEvent(mMarker, statId, data) {
    kakao.maps.event.addListener(mMarker, 'click', function (mouseEvent) {
        removeAllEvtPop();
        let charger = data.find(item => item.STAT_ID == statId);
        changeMarkerImageAll(mMarker, MARKER.CHARGER, MARKER.CHARGER_SEL);
        setChargerDetail(charger);
    });
};

//신호개방 마커 이벤트
function setOpenSignalEvent(mMarker, signalId, data) {
    kakao.maps.event.addListener(mMarker, 'click', function (mouseEvent) {
        removeAllEvtPop();
        let signal = data.find(item => item.NODE_ID == signalId);
        changeMarkerImageAll(mMarker, MARKER.SIGNAL, MARKER.SIGNAL_SEL);
        setOpenSignalDetail(signal);
    });
};

//충전소 카테고리 표기
function setChargerInfo(data) {
    searchCnt += data.length;
    $('#chargerCnt').text(data.length);
    $('#chargerList').empty();
    data.forEach((item) => {
        $('#chargerList').append('<a class="gis-downmenu-item" id=' + item.STAT_ID + '>' + item.STAT_NM + '</a>')
    });
    $('#chargerList .gis-downmenu-item').on('click', function () {
        removeAllEvtPop();
        if($('#roadOnMap').hasClass('active')) {
            $('.map-marker-btn-item.active').children().not(':first').click();
            if (!$('#chargerInfoOnMap').hasClass('active')) {
                $('#chargerInfoOnMap .map-quick-btn').click();
            }
        }
        else{
            $('.map-marker-btn-item.active').children().click();
            if (!$('#chargerInfoOnMap').hasClass('active')) {
                $('#chargerInfoOnMap .map-quick-btn').click();
            }
        }
        let charger = data.find(item => item.STAT_ID == $(this).attr('id'));
        let chargerMarker = MARKER_ARRAY.chargerInfoOnMap.find(marker => marker.title == $(this).attr('id'));
        if (chargerMarker != null) {
            changeMarkerImageAll(chargerMarker, MARKER.CHARGER, MARKER.CHARGER_SEL);
        }
        setChargerDetail(charger);
    });
};

//충전소 상세정보 호출
function setChargerDetail(charger) {

    let data = null;

    $.ajax({
        type: "POST",
        dataType: "json",
        data: {stat_id: charger.STAT_ID},
        async: false,
        url: '/gis/selectChargerDetail.do',
        success: function (res) {
            data = JSON.parse(res).result;
        }
    });

    const $popup = $('.popInfoWrap');

    if (data == null) {
        alert('충전기 상세정보 데이터가 없습니다.');
        return;
    }

    $popup.empty(); // 기존 내용 비우기
    $popup.show();

    const popupHTML = `

      <div class="gis-modal bus-modal">
      <div class="gis-modal-header">
        <div class="d-flex space-between gap">
          <h1>${data.STAT_NM}</h1>
           <button type="button" class="button img-btn gis-modal-close-btn" onclick="closePopinfo()">
            <img src="/images/icthome/icon-close.svg" class="invert" alt="닫기" />
          </button>
        </div>
        <h5 class="secondary-txt">정보제공 : <span class="">${data.BNM}</span></h5>
        <h5 class="secondary-txt">대표번호 : <span class="">${data.BUSI_CALL}</span></h5>
        <h5 class="secondary-txt">주차장정보 : <span class="">${chargerKindInfo(data.KIND)} / ${chargerKindInfo(data.KIND_DETAIL)}</span></h5>
      </div>
      <div class="gis-modal-body">
        <table class="table body-s txt-center">
          <tbody><tr>
            <th>주소</th>
            <td class="secondary-txt">${data.ADDR}</td>
          </tr>
          <tr>
            <th>이용시간</th>
            <td class="secondary-txt">${data.USE_TIME}</td>
          </tr>
        </tbody></table>
        <table class="table txt-center">
          <thead>
            <tr class="h5">
              <th>충전타입</th>
              <th>가용 면수</th>
              <th>총 면수</th>
            </tr>
          </thead>
          <tbody>
            ${chargerType('01', data)}
            ${chargerType('02', data)}
            ${chargerType('03', data)}
            ${chargerType('04', data)}
            ${chargerType('05', data)}
            ${chargerType('06', data)}
            ${chargerType('07', data)}
            ${chargerType('08', data)}
            ${chargerType('09', data)}
            ${chargerType('10', data)}
          </tbody>
        </table>
      </div>
    </div>
    </div>
`;
    $popup.html(popupHTML);
    centerRelayout(charger.Y_CRDN, charger.X_CRDN);
}

function chargerKindInfo(key) {
    const dataMap = {
        "A001": "관공서",
        "A002": "주민센터",
        "A003": "공공기관",
        "A004": "지자체시설",
        "B001": "공영주차장",
        "B002": "공원주차장",
        "B003": "환승주차장",
        "B004": "일반주차장",
        "C001": "고속도로 휴게소",
        "C002": "지방도로 휴게소",
        "C003": "쉼터",
        "D001": "공원",
        "D002": "전시관",
        "D003": "민속마을",
        "D004": "생태공원",
        "D005": "홍보관",
        "D006": "관광안내소",
        "D007": "관광지",
        "D008": "박물관",
        "D009": "유적지",
        "E001": "마트(쇼핑몰)",
        "E002": "백화점",
        "E003": "숙박시설",
        "E004": "골프장(CC)",
        "E005": "카페",
        "E006": "음식점",
        "E007": "주유소",
        "E008": "영화관",
        "F001": "서비스센터",
        "F002": "정비소",
        "G001": "군부대",
        "G002": "야영장",
        "G003": "공중전화부스",
        "G004": "기타",
        "G005": "오피스텔",
        "G006": "단독주택",
        "H001": "아파트",
        "H002": "빌라",
        "H003": "사업장(사옥)",
        "H004": "기숙사",
        "H005": "연립주택",
        "I001": "병원",
        "I002": "종교시설",
        "I003": "보건소",
        "I004": "경찰서",
        "I005": "도서관",
        "I006": "복지관",
        "I007": "수련원",
        "I008": "금융기관",
        "J001": "학교",
        "J002": "교육원",
        "J003": "학원",
        "J004": "공연장",
        "J005": "관람장",
        "J006": "동식물원",
        "J007": "경기장",
        "A0": "공공시설",
        "B0": "주차시설",
        "C0": "휴게시설",
        "D0": "관광시설",
        "E0": "상업시설",
        "F0": "차량정비시설",
        "G0": "기타시설",
        "H0": "공동주택시설",
        "I0": "근린생활시설",
        "J0": "교육문화시설"
    };

    return dataMap[key] || "정보없음";
}


function chargerType(str, data) {
    const typeMap = {
        '01': 'DC차데모',
        '02': 'AC완속',
        '03': 'DC차데모+AC3상',
        '04': 'DC콤보',
        '05': 'DC차데모+DC콤보',
        '06': 'DC차데모+AC3상+DC콤보',
        '07': 'AC3상',
        '08': 'DC콤보(완속)',
        '09': 'NACS',
        '10': 'DC콤보+NACS'
    };

    const label = typeMap[str];
    if (!label) {
        return '';
    }

    const totalKey = `TYPE_${str}`;
    const openKey = `TYPE_${str}_OPEN`;

    const openVal = data[openKey] ?? '정보없음';
    const totalVal = data[totalKey] ?? '정보없음';

    // totalVal이 0이거나 falsy면 빈 문자열 리턴
    if (!totalVal || totalVal === 0) {
        return '';
    }

    return `
    <tr class="body">
      <td>${label}</td>
      <td class="h4">${openVal}</td>
      <td class="h4 primary-txt bg-light">${totalVal}</td>
    </tr>
  `;
}





function parkingFree(str) {
    if (str === 'Y') {
        return '무료주차';
    } else if (str === 'N') {
        return '유료주차';
    } else {
        return '알 수 없음';
    }
}


//신호개방교차로 카테고리 표기
function setOpenSignalInfo(data) {
    searchCnt += data.length;
    $('#openSignalCnt').text(data.length);
    $('#openSignalList').empty();
    data.forEach((item) => {
        $('#openSignalList').append('<a class="gis-downmenu-item" id=' + item.NODE_ID + '>' + item.SPOT_INTS_NAME + '</a>')
    });
    $('#openSignalList .gis-downmenu-item').on('click', function () {
        removeAllEvtPop();
        if($('#roadOnMap').hasClass('active')) {
            $('.map-marker-btn-item.active').children().not(':first').click();
            if (!$('#openSignalOnMap').hasClass('active')) {
                $('#openSignalOnMap .map-quick-btn').click();
            }
        }
        else{
            $('.map-marker-btn-item.active').children().click();
            if (!$('#openSignalOnMap').hasClass('active')) {
                $('#openSignalOnMap .map-quick-btn').click();
            }
        }
        let signal = data.find(item => item.NODE_ID == $(this).attr('id'));
        let signalMarker = MARKER_ARRAY.openSignalOnMap.find(marker => marker.title == $(this).attr('id'));
        if (signalMarker != null) {
            changeMarkerImageAll(signalMarker, MARKER.SIGNAL, MARKER.SIGNAL_SEL);
        }
        setOpenSignalDetail(signal);
    });
};

function setOpenSignalDetail(signal){

        let data = null;

        $.ajax({
            type: "POST",
            dataType: "json",
            data: {node_id: signal.NODE_ID},
            async: false,
            url: '/gis/selectOpenSignalDetail.do',
            success: function (res) {
                data = JSON.parse(res).result;
            }
        });

        const $popup = $('.popInfoWrap');

        if (data == null) {
            alert('신호개방 교차로 상세정보 데이터가 없습니다.');
            return;
        }

        $popup.empty(); // 기존 내용 비우기
        $popup.show();

        const popupHTML = `

      <div class="gis-modal bus-modal">
          <div class="gis-modal-header">
            <div class="d-flex space-between gap">
              <h1>${data.SPOT_INTS_NAME}</h1>
               <button type="button" class="button img-btn gis-modal-close-btn" onclick="closePopinfo()">
                <img src="/images/icthome/icon-close.svg" class="invert" alt="닫기" />
              </button>
            </div>
          <div class="gis-modal-body">
           </div>
        </div>
    </div>
`;
        $popup.html(popupHTML);
        centerRelayout(signal.Y_CRDN, signal.X_CRDN);
}

//마커 클릭시 이미지 변경 이벤트
var selectedMarker = {
    beforeImg: '', marker: null,
};

//지도에 원 표시
let currentCircle;

function setCircleOnMap() {

    let center = oMap.getCenter();
    let circle = new kakao.maps.Circle({
        center: center, // 원의 중심좌표
        radius: 1000, // 미터 단위 반경
        strokeWeight: 5, // 선의 두께
        strokeColor: '#FF0000', // 선의 색깔
        strokeOpacity: 1, // 선의 불투명도
        strokeStyle: 'dashed', // 선의 스타일
        fillColor: '#CFE7FF', fillOpacity: 0 // 채우기 불투명도
    });

    if (currentCircle) {
        currentCircle.setMap(null);
    }

    // 지도에 원 추가
    circle.setMap(oMap);
    currentCircle = circle;
    return circle;
}

//버텍스 생성
function vrtxFunc(roadNm) {
    let visible = $('#roadOnMap').hasClass('active');
    $.ajax({
        url: "/gis/selectVrtxData.do", method: 'POST', data: getVrtxLevel(oMap.getLevel(), roadNm), success: (res) => {
            let data = JSON.parse(res).result;
            if (roadNm != undefined && roadNm != null && roadNm != '') {
                drawPickVrtxPolyline(data);
            } else {
                if (visible) {
                    drawVrtxPolyLine(data); //전체 폴리라인 생성
                }
            }
        }, error: (jqXHR, textStatus, errorThrown) => {
            console.warn('[소통정보] 버텍스 데이터 요청 실패:', textStatus, (jqXHR && jqXHR.status) || '');
        }
    });
};


//버텍스 레벨 분기
function getVrtxLevel(zoomLevel, roadNm) {
    let obj = new Object();
    obj.link_lv = 1;
    if (zoomLevel <= 3) {
        obj.levl = 1;
    } else if (zoomLevel == 4) {
        obj.link_lv = 2;
        obj.levl = 5;
    } else if (zoomLevel == 5) {
        obj.link_lv = 2;
        obj.levl = 4;
    } else if (zoomLevel == 6) {
        obj.link_lv = 2;
        obj.levl = 3;
    } else if (zoomLevel == 7) {
        obj.link_lv = 3;
        obj.levl = 2;
    } else if (zoomLevel >= 8) {
        obj.link_lv = 3;
        obj.levl = 1;
    }
    ;

    obj.minlat = oMap.getBounds().getSouthWest().getLat();
    obj.maxlat = oMap.getBounds().getNorthEast().getLat();
    obj.minlng = oMap.getBounds().getSouthWest().getLng();
    obj.maxlng = oMap.getBounds().getNorthEast().getLng();

    if (roadNm != null && roadNm != '') {
        obj.roadName = roadNm;
    }

    return obj;
};

//교통 폴리라인 그리기
/*function drawVrtxPolyLine(data) {
    removeVrtxPolyLine(); // 기존 폴리라인 삭제

    $('.map-quick-btn').parent().hasClass('active');

    let path = [];
    let polyline;
    $.each(data, function (idx, item) {
        polyline = new kakao.maps.Polyline({
            strokeWeight: 3, strokeOpacity: 0.9, strokeStyle: 'solid'
        });
        let color;
        switch (item.GRADE) {
            case '1':
                color = '#0ebe39'; // Green
                break;
            case '2':
                color = '#ffc600'; // Yellow
                break;
            case '3':
                color = '#f90000'; // Red
                break;
            default:
                color = '#9d9d9d'; // Gray
        }
        path.push(new kakao.maps.LatLng(item.Y_CRDN, item.X_CRDN));
        polyline.setOptions({strokeColor: color});

        setPolyLineEvent(polyline, item.ROAD_NAME);
    });
    polyline.setPath(path);
    polyline.setMap(oMap);
    VRTX_ARRAY.push(polyline);
}*/


function drawVrtxPolyLine(data) {
    removeVrtxPolyLine(); // 기존 폴리라인 삭제

    $('.map-quick-btn').parent().hasClass('active');

    let path = [];
    let polyline;
    var pathArray0 = new Array(); //정보없음
    var pathArray1 = new Array();
    var pathArray2 = new Array();
    var pathArray3 = new Array();

    $.each(data, function (index, value) {
        if (value.GRADE == 1) {
            pathArray1.push(new kakao.maps.LatLng(value.Y_CRDN, value.X_CRDN));
        } else if (value.GRADE == 2) {
            pathArray2.push(new kakao.maps.LatLng(value.Y_CRDN, value.X_CRDN));
        } else if (value.GRADE == 3) {
            pathArray3.push(new kakao.maps.LatLng(value.Y_CRDN, value.X_CRDN));
        } else {
            pathArray0.push(new kakao.maps.LatLng(value.Y_CRDN, value.X_CRDN));
        }
        if (index + 1 == data.length || value.ID != data[index + 1].ID) {
            if (pathArray1 != null) {
                oVrtxPoly1.setPath(pathArray1);
                oVrtxPoly1.setMap(oMap);
                // khjo
                //setPolyLineEvent(oVrtxPoly1, value.ROAD_NAME, value.LINKLV, value.LV);
                VRTX_ARRAY.push(oVrtxPoly1);
            }
            if (pathArray2 != null) {
                oVrtxPoly2.setPath(pathArray2);
                oVrtxPoly2.setMap(oMap);

                //setPolyLineEvent(oVrtxPoly2, value.ROAD_NAME, value.LINKLV, value.LV);
                VRTX_ARRAY.push(oVrtxPoly2);
            }
            if (pathArray3 != null) {
                oVrtxPoly3.setPath(pathArray3);
                oVrtxPoly3.setMap(oMap);

                //setPolyLineEvent(oVrtxPoly3, value.ROAD_NAME, value.LINKLV, value.LV);
                VRTX_ARRAY.push(oVrtxPoly3);
            }
            if (pathArray0 != null) {
                oVrtxPoly0.setPath(pathArray0);
                oVrtxPoly0.setMap(oMap);

                //setPolyLineEvent(oVrtxPoly0, value.ROAD_NAME, value.LINKLV, value.LV);
                VRTX_ARRAY.push(oVrtxPoly0);
            }
            pathArray0 = new Array();
            pathArray1 = new Array();
            pathArray2 = new Array();
            pathArray3 = new Array();
            initVrtxPoly();
        }
    });
}


//폴리라인 배열 초기화
function removeVrtxPolyLine() {
    $.each(VRTX_ARRAY, function (i, v) {
        v.setMap(null);
    });

    VRTX_ARRAY = [];
}

//폴리라인 이벤트
function setPolyLineEvent(polyline, roadNm) {
    kakao.maps.event.addListener(polyline, 'click', function (event) {
        //vertexline 클릭 시 팝업 제외 처리
        getDetailRoadName('road', roadNm);
        vrtxFunc(roadNm);
    });
}

//폴리라인 세팅 초기화
function initVrtxPoly() {
    //  회색: #9d9d9d
    //  초록: #0ebe39
    //  노랑: #ffc600
    //  빨강: #f90000
    // 파랑: #354beb
    //#FF0000 red
    //#FFB500 orange
    //#101010 black

    oVrtxPoly0 = new kakao.maps.Polyline({
        strokeWeight: 3, strokeColor: '#9d9d9d', strokeOpacity: 0.9, strokeStyle: 'solid',
    });

    oVrtxPoly1 = new kakao.maps.Polyline({
        strokeWeight: 3, strokeColor: '#0ebe39', strokeOpacity: 0.9, strokeStyle: 'solid',
    });

    oVrtxPoly2 = new kakao.maps.Polyline({
        strokeWeight: 3, strokeColor: '#fae41c', strokeOpacity: 0.9, strokeStyle: 'solid',
    });

    oVrtxPoly3 = new kakao.maps.Polyline({
        strokeWeight: 3, strokeColor: '#f90000', strokeOpacity: 0.9, strokeStyle: 'solid',
    });

    oVrtxPoly4 = new kakao.maps.Polyline({
        strokeWeight: 3, strokeColor: '#354beb', strokeOpacity: 0.9, strokeStyle: 'solid', zIndex: 9999999,
    });

    // red
    oVrtxPoly5 = new kakao.maps.Polyline({
        strokeWeight: 3, strokeColor: '#FF0000', strokeOpacity: 0.9, strokeStyle: 'dashed', zIndex: 9999999,
    });

    // orange
    oVrtxPoly6 = new kakao.maps.Polyline({
        strokeWeight: 3, strokeColor: '#FFB500', strokeOpacity: 0.9, strokeStyle: 'solid', zIndex: 9999999,
    });
}


//도로 상세정보 html 생성
function initDetailRoadName() {
    $('.popInfoWrap.road .tit .title').text('');
    $('.popInfoWrap.road .tit .startEnd').text('');
    $('.popInfoWrap.road .pop_cnt .dist').text('');
    $('.popInfoWrap.road .pop_cnt .start').empty();
    $('.popInfoWrap.road .pop_cnt .end').empty();
    $('.popInfoWrap.road .trafficBox_wrap .trafficBox').empty();
}

//소통정보 상세
function setRoadDetail(data) {
    const resultList = data.result;
    const $popup = $('.popInfoWrap');

    if (!resultList || resultList.length === 0) {
        console.log('도로 상세정보 데이터 없음');
        $popup.hide();
        return;
    }
    // $popup.className = 'gis-modal';
    // $popup.addClass('gis-modal traffic-modal')
    $popup.empty(); // 기존 내용 비우기
    $popup.show();

    let distance1 = 0, distance2 = 0, time1 = 0, time2 = 0;
    for (const item of resultList) {
        distance1 += item.SECT_LNGT;
        distance2 += item.SECT_LNGT2;
        time1 += calcTime(item.SPED, item.SECT_LNGT);
        time2 += calcTime(item.SPED2, item.SECT_LNGT2);
    }

    const sped1 = distance1 / 1000 / (time1 / 60);
    const sped2 = distance2 / 1000 / (time2 / 60);

    function calcTime(speed, distance) {
        if (distance == null) {
            return 0;
        }
        return Math.round(((distance * 0.06) / speed) * 10) / 10;
    }

    function clsfTrafColor(trafficClass) {
        return trafficClass === 'SRT8' ? 'yellow' : 'green'; // 예시
    }

    function getTrfClass(grade, speed) {
        return speed > 60 ? 'SRT8' : 'default'; // 예시
    }

    function getArrowImageLeft(clsfTrafColor) {
        switch (clsfTrafColor) {
            case 'green':
                return `<img src="/images/icthome/arrow-grade-01.svg" />`;
                break;
            case 'yellow':
                return `<img src="/images/icthome/arrow-grade-02.svg" />`;
                break;
            case 'red':
                return `<img src="/images/icthome/arrow-grade-03.svg" />`;
                break;
            default:
                return `<img src="/images/icthome/arrow-grade-04.svg" />`;
        }
        ;
    }

    function getArrowImageRight(clsfTrafColor) {
        switch (clsfTrafColor) {
            case 'green':
                return `<img src="/images/icthome/arrow-down-grade-01.svg" />`;
                break;

            case 'yellow':
                return `<img src="/images/icthome/arrow-down-grade-02.svg" />`;
                break;

            case 'red':
                return `<img src="/images/icthome/arrow-down-grade-03.svg" />`;
                break;

            default:
                return `<img src="/images/icthome/arrow-down-grade-04.svg" />`;
        }
        ;
    }

    let trafficBoxHTML = "";
    resultList.forEach((item, i) => {
        trafficBoxHTML += `


         <div class="traffic-road-name">
            <h5>${item.SRTNODENM}</h5>
          </div>
          <div class="d-flex space-between">
            <div class="d-flex align-center gap-xs t-success body-s left ${clsfTrafColor(getTrfClass(item.GRAD, item.SPED))}">
              ${item.SPED}km/h(${calcTime(item.SPED, item.SECT_LNGT)}분)
              ${getArrowImageLeft(clsfTrafColor(getTrfClass(item.GRAD, item.SPED)))}
              <!--<img src="/images/icthome/arrow-grade-01.svg" />-->
            </div>
            <div class="d-flex align-center gap-xs t-success body-s right ${clsfTrafColor(getTrfClass(item.GRAD2, item.SPED2))}">
              <!--<img src="/images/icthome/arrow-down-grade-01.svg" />-->
              ${getArrowImageRight(clsfTrafColor(getTrfClass(item.GRAD2, item.SPED2)))}
              ${item.SPED2}km/h(${calcTime(item.SPED2, item.SECT_LNGT2)}분)
            </div>
          </div>
        `;
        if (i === resultList.length) {
            trafficBoxHTML += `<div><h5 class='name'>${resultList.at(-1).ENDNODENM}</h5></div>`;
        }
    });
    const popupHTML = `
            <div class="gis-modal traffic-modal">
                  <div class="gis-modal-header">
                    <div class="d-flex space-between gap">
                      <h1>${ROADNAME}</h1>
                      <button type="button" class="button img-btn gis-modal-close-btn" onclick="closePopinfo()">
                        <img src="/images/icthome/icon-close.svg" class="invert" alt="닫기" />
                      </button>
                    </div>
                         <h5 class="secondary-txt">
                      <span>${resultList[0].SRTNODENM}</span> ~ <span>${resultList.at(-1).ENDNODENM}</span>
                    </h5>
                  </div>
                <div class="gis-modal-body">
                    <div class="d-flex gap-1">
                      <h5>도로길이</h5>
                      <p class="body-s">${(distance1 / 1000).toFixed(2)}km</p>
                    </div>
                    <div class="d-flex gap-1">
                      <h5>평균속도</h5>
                      <div class="avg-speed">
                        <div class="d-flex gap-1 space-between">
                          <p class="body-s">${resultList[0].SRTNODENM}</p>
                          <span class="t-success body-s right ${clsfTrafColor(getTrfClass('SRT8', sped1))}">▲ ${!Number.isNaN(sped1) ? Math.round(sped1) : 0}km/h</span>
                        </div>
                        <div class="d-flex gap-1 space-between">
                          <p class="body-s">${resultList.at(-1).ENDNODENM}</p>
                          <span class="t-success body-s right ${clsfTrafColor(getTrfClass('SRT8', sped2))}">▼  ${!Number.isNaN(sped2) ? Math.round(sped2) : 0}km/h</span>
                        </div>
                      </div>
                    </div>
                     <div class="traffic-realtime">
                        ${trafficBoxHTML}
                    </div>
                </div>
         </div>
    `;

    $popup.html(popupHTML);
    ROADNAME = '';
}

//돌발정보 상세 팝업 표기
function setDetailIncd(incd) {
    const $popup = $('.popInfoWrap');

    if (incd == null && incd == undefined) {
        console.log('돌발 상세정보 데이터 없음');
        $roadPopup.hide();
        return;
    }

    $popup.empty(); // 기존 내용 비우기
    $popup.show();

    const popupHTML = `


 <div class="gis-modal schoolzone-modal">
      <div class="gis-modal-header">
        <div class="d-flex space-between gap">
          <h1>[${incd.CODE_NAME}]</h1>
          <button type="button" class="button img-btn gis-modal-close-btn">
            <img src="/images/icthome/icon-close.svg" class="invert" alt="닫기" onclick="closePopinfo()"/>
          </button>
        </div>
      </div>
      <div class="gis-modal-body">
        <ul class="schoolzone-list">
          <li class="d-flex gap-1">
            <h5>사고정보</h5>
            <p class="body-s">${incd.CODE_NAME}</p>
          </li>
          <li class="d-flex gap-1">
            <h5>발생지점</h5>
            <p class="body-s">${incd.SECTION_NAME}</p>
          </li>
          <li class="d-flex gap-1">
            <h5>발생일시</h5>
            <p class="body-s">${incd.GEN_TIME}</p>
          </li>
          <li class="d-flex gap-1">
            <h5>내용</h5>
            <p class="body-s">${incd.ACCIDENT_TEXT}</p>
          </li>
          
        </ul>
      </div>
    </div>
`;
    $popup.html(popupHTML);
    centerRelayout(incd.Y_CRDN, incd.X_CRDN);
}

//교통 CCTV 상세팝업 표기
let cctvOverlay;
let cctvVideo;
let timerPop; // 전역 변수로 선언

/**
 * 브라우저 감지 함수
 * @returns {Object} 브라우저 정보 {name: 'chrome'|'firefox'|'edge'|'safari'|'other', isChromium: boolean, isWindows: boolean}
 */
function detectBrowser() {
    const ua = navigator.userAgent.toLowerCase();
    const isChromium = ua.includes('chrome') || ua.includes('chromium') || ua.includes('edg');
    const isFirefox = ua.includes('firefox');
    const isSafari = ua.includes('safari') && !ua.includes('chrome');
    const isEdge = ua.includes('edg');
    const isWindows = ua.includes('windows') || ua.includes('win32') || ua.includes('win64');
    
    let name = 'other';
    if (isEdge) name = 'edge';
    else if (isFirefox) name = 'firefox';
    else if (isSafari) name = 'safari';
    else if (isChromium) name = 'chrome';
    
    return {
        name: name,
        isChromium: isChromium,
        isFirefox: isFirefox,
        isWindows: isWindows
    };
}

/**
 * HLS/VHS 플레이어 이벤트 핸들러 설정 유틸리티 함수
 * Video.js 8에서는 VHS 사용, Video.js 7에서는 hls 사용
 * @param {Object} player - Video.js 플레이어 인스턴스
 * @param {String} prefix - 로그 프리픽스 (예: 'CCTV', 'Smart')
 * @param {String} streamUrl - 스트림 URL (재시도 시 사용)
 * @param {Object} [preResolvedHls] - ready 콜백에서 미리 조회한 VHS/HLS 인스턴스 (tech() 경고 방지용)
 */
function setupHlsEventHandlers(player, prefix, streamUrl, preResolvedHls) {
    if (!player) {
        return;
    }
    
    const logPrefix = `[${prefix} HLS/VHS]`;
    
    // preResolvedHls가 있으면 사용, 없으면 tech_로만 접근 (player.tech() 사용 시 Video.js 경고 발생)
    let hls = preResolvedHls || null;
    if (!hls) {
        const tech = player.tech_;
        if (tech) {
            hls = tech.vhs || tech.hls;
        }
    }
    
    if (hls && hls.on) {
        // 세그먼트 로딩 시작 이벤트
        hls.on('segment-load-start', function() {
            console.log(logPrefix + ' 세그먼트 로딩 시작');
        });
        
        // 세그먼트 로딩 완료 이벤트
        hls.on('segment-loaded', function() {
            console.log(logPrefix + ' 세그먼트 로딩 완료');
        });
        
        // 네트워크 오류 처리
        hls.on('network-error', function(event) {
            console.warn(logPrefix + ' 네트워크 오류:', event);
            // 자동 재시도는 VHS/HLS 플러그인이 처리
        });
    } else {
        console.warn(logPrefix + ' VHS/HLS 기술을 찾을 수 없습니다.');
    }
    
    // 버퍼링 이벤트 모니터링
    player.on('waiting', function() {
        console.log(logPrefix + ' 버퍼링 중...');
    });
    
    player.on('canplay', function() {
        console.log(logPrefix + ' 재생 가능');
    });
    
    // 에러 발생 시 재시도 (setDetailCctv에서 이미 처리하므로 여기서는 로깅만)
    if (streamUrl) {
        player.on('error', function() {
            const error = player.error();
            if (error) {
                // 에러 코드별 로깅
                // 1: MEDIA_ERR_ABORTED, 2: MEDIA_ERR_NETWORK, 3: MEDIA_ERR_DECODE, 4: MEDIA_ERR_SRC_NOT_SUPPORTED
                if (error.code === 3) {
                    console.warn(logPrefix + ' 디코딩 오류 발생:', error.message);
                } else if (error.code === 4) {
                    console.warn(logPrefix + ' 스트림 미지원:', error.message);
                } else if (error.code === 2) {
                    console.warn(logPrefix + ' 네트워크 오류:', error.message);
                }
            }
        });
    }
}

function setDetailCctv(marker, cctv) {
    removeAllEvtPop();

    if (cctvOverlay != null) {
        cctvOverlay.close();
    }

    if (cctvVideo != null) {
        cctvVideo.dispose();
        cctvVideo = null;
    }

    let iwContent = `
        <div class="gis-modal schoolzone-modal">
            <div class="gis-modal-header">
                <div class="d-flex space-between gap">
                    <h1>[${cctv.CCTV_NM}]</h1>
                    <button type="button" class="button img-btn gis-modal-close-btn">
                        <img src="/images/icthome/icon-close.svg" class="invert" alt="닫기" onclick="closeCctvOverlay()"/>
                    </button>
                </div>
            </div>
            <video id="cctvPlay" preload="auto" controls class="video-js vjs-default-skin" 
                   style="transform: none !important; will-change: auto !important; backface-visibility: visible !important;" 
                   disablePictureInPicture disableRemotePlayback></video>
            <style>
                #cctvPlay .vjs-error-display,
                #cctvPlay .vjs-error-display-wrapper,
                #cctvPlay .vjs-modal-dialog,
                #cctvPlay .vjs-modal-dialog-content {
                    display: none !important;
                    visibility: hidden !important;
                    opacity: 0 !important;
                }
            </style>
        </div>
    `;
    let iwPosition = new kakao.maps.LatLng(cctv.Y_CRDN, cctv.X_CRDN);
    cctvOverlay = new kakao.maps.InfoWindow({
        position: iwPosition,
        content: iwContent,
        controls: true,
        controlBar: { playToggle: false, fullscreenToggle: true},
    });

    cctvOverlay.open(oMap, marker);
    cctvOverlay.setZIndex(999);

    let httpAddr = (document.location.protocol === 'https:')
        ? cctv.HTTPADDR.replace('http://61.40.94.13:1935', 'https://cctv.fitic.go.kr')
        : cctv.HTTPADDR;

    let cctvWidth = 540;

    if (matchMedia("screen and (max-width: 1024px)").matches) {
        cctvWidth = 300;
    }

    // 브라우저 감지
    const browser = detectBrowser();
    
    // 재시도 횟수 추적 변수 (무한 재시도)
    let retryCount = 0;
    let isRetrying = false; // 재시도 중 플래그
    let stalledTimer = null; // 재생 멈춤 감지 타이머
    let lastFrameCanvas = null; // 마지막 프레임 캡처용 캔버스
    
    // Chrome에서만 발생하는 디코딩 오류 해결을 위한 강화된 설정
    // Firefox 등에서는 techOrder를 넣지 않음(undefined 전달 시 기본 옵션 덮어써서 에러 발생)
    let options = {
        crossorigin: 'anonymous',
        cors: 'anonymous',
        fullScreen: false,
        controls: true,
        controlBar: { playToggle: false, fullscreenToggle: true},
        autoplay: true,
        width: cctvWidth,
        sources: [{src: httpAddr, type: 'application/x-mpegURL'}],
        html5: {
            // Chrome에서 네이티브 HLS 완전 차단 및 VHS 강제 사용
            vhs: {
                overrideNative: browser.isChromium,  // Chrome에서 네이티브 HLS 비활성화 (필수)
                // 디코딩 오류 방지를 위한 추가 설정
                smoothQualityChange: true,
                useBandwidthFromLocalStorage: false,
                // Chrome 디코딩 문제 해결을 위한 추가 옵션
                limitRenditionByPlayerDimensions: false,
                enableLowInitialPlaylist: true,
                // 세그먼트 로딩 재시도 설정 (간헐적 오류 대응: 타임아웃 증가)
                maxPlaylistRetries: 5,  // 3 → 5로 증가
                playlistRequestTimeout: 15000,  // 10초 → 15초로 증가 (Wowza 서버 지연 대응)
                // Chrome 디코딩 안정성 향상
                handleManifestRedirects: true,
                experimentalBufferBasedABR: false
            },
            // Chrome에서 하드웨어 가속 관련 설정 (디코딩 문제 방지)
            nativeVideoTracks: false,
            nativeAudioTracks: false,
            nativeTextTracks: false,
            // 고사양 노트북 하드웨어 가속 충돌 방지
            // 하드웨어 디코딩 비활성화 (소프트웨어 디코딩 강제)
            // Windows에서 발생하는 GPU 디코딩 오류 방지를 위해 Windows도 포함
            preferSoftwareDecoder: browser.isChromium || browser.isWindows  // Chrome 및 Windows에서 소프트웨어 디코딩 강제
        },
        // 플레이어 안정성을 위한 추가 설정
        playbackRates: [0.5, 1, 1.5, 2],
        fluid: false,
        responsive: false,
        // Chrome 디코딩 안정성을 위한 설정
        preload: 'auto',
        playsinline: true
    };
    // Chrome/Edge에서만 techOrder 지정 (Firefox 등에서는 미지정 시 Video.js 기본값 사용, undefined 전달 시 에러)
    if (browser.isChromium) {
        options.techOrder = ['html5'];
    }

    // Chrome/Edge 또는 Windows인 경우 추가 설정 적용
    if (browser.isChromium || browser.isWindows) {
        const platformInfo = browser.isWindows ? 'Windows' : 'Chrome';
        console.log(`[CCTV] ${platformInfo} 감지: 네이티브 HLS 비활성화 및 VHS 강제 사용`);
        
        // Chrome/Windows에서 네이티브 HLS 지원을 차단하기 위한 추가 조치
        // Video.js가 초기화되기 전에 video element에 직접 설정
        const videoElement = document.getElementById('cctvPlay');
        if (videoElement) {
            // playsinline 속성 추가 (모바일 Chrome 호환성)
            videoElement.setAttribute('playsinline', 'true');
            videoElement.setAttribute('webkit-playsinline', 'true');
            
            // Windows/고사양 노트북의 하드웨어 가속 충돌 방지를 위한 설정
            // 하드웨어 가속 비활성화 (GPU 디코딩 문제 해결)
            videoElement.setAttribute('disablePictureInPicture', 'true');
            videoElement.setAttribute('disableRemotePlayback', 'true');
            
            // CSS로 하드웨어 가속 비활성화
            videoElement.style.transform = 'none';  // GPU 가속 비활성화
            videoElement.style.willChange = 'auto';  // will-change 비활성화
            videoElement.style.backfaceVisibility = 'visible';  // 백페이스 비가시성 비활성화
            
            // 하드웨어 가속 완전 비활성화를 위한 추가 CSS
            videoElement.style.webkitTransform = 'none';
            videoElement.style.mozTransform = 'none';
            videoElement.style.msTransform = 'none';
            videoElement.style.oTransform = 'none';
            
            // Windows에서 하드웨어 가속 강제 비활성화를 위한 추가 속성
            if (browser.isWindows) {
                // Windows Media Foundation 하드웨어 가속 비활성화 시도
                videoElement.setAttribute('preload', 'auto');
                // GPU 가속 완전 차단
                videoElement.style.perspective = 'none';
                videoElement.style.transformStyle = 'flat';
            }
            
            console.log(`[CCTV] 하드웨어 가속 비활성화 완료 (${platformInfo} 호환성)`);
        }
    }

    cctvVideo = videojs('cctvPlay', options);
    
    // 오류 메시지 숨기기 함수 (전역으로 정의하여 모든 곳에서 사용 가능)
    let hideErrorElements = function() {
        if (!cctvVideo || cctvVideo.isDisposed()) return;
        
        const playerEl = cctvVideo.el();
        if (playerEl) {
            // Video.js 오류 표시 요소들 숨기기
            const errorDisplay = playerEl.querySelector('.vjs-error-display');
            const errorWrapper = playerEl.querySelector('.vjs-error-display-wrapper');
            const modalDialog = playerEl.querySelector('.vjs-modal-dialog');
            const errorMessage = playerEl.querySelector('.vjs-error-display .vjs-modal-dialog-content');
            
            [errorDisplay, errorWrapper, modalDialog, errorMessage].forEach(function(el) {
                if (el) {
                    el.style.display = 'none';
                    el.style.visibility = 'hidden';
                    el.style.opacity = '0';
                    el.style.pointerEvents = 'none';
                }
            });
            
            // 비디오 요소 내부의 모든 오류 관련 요소 숨기기
            const allErrorElements = playerEl.querySelectorAll('[class*="error"], [class*="Error"]');
            allErrorElements.forEach(function(el) {
                if (el.textContent && (el.textContent.includes('corruption') || el.textContent.includes('not support') || el.textContent.includes('재생'))) {
                    el.style.display = 'none';
                    el.style.visibility = 'hidden';
                    el.style.opacity = '0';
                }
            });
        }
        
        // 비디오 요소 직접 확인
        const videoElement = document.getElementById('cctvPlay');
        if (videoElement) {
            const errorDisplay = videoElement.querySelector('.vjs-error-display');
            const errorWrapper = videoElement.querySelector('.vjs-error-display-wrapper');
            const modalDialog = videoElement.querySelector('.vjs-modal-dialog');
            if (errorDisplay) errorDisplay.style.display = 'none';
            if (errorWrapper) errorWrapper.style.display = 'none';
            if (modalDialog) modalDialog.style.display = 'none';
        }
    };
    
    // 오류 메시지 숨기기 (CSS로 즉시 적용)
    const videoElement = document.getElementById('cctvPlay');
    if (videoElement) {
        // MutationObserver로 동적으로 추가되는 오류 요소 감지하여 숨기기
        const observer = new MutationObserver(function(mutations) {
            hideErrorElements();
        });
        observer.observe(videoElement, { childList: true, subtree: true });
        
        // 주기적으로 확인하여 숨기기
        const hideErrorInterval = setInterval(hideErrorElements, 100);
        
        // 플레이어가 dispose될 때 정리
        setTimeout(function() {
            if (cctvVideo && !cctvVideo.isDisposed()) {
                cctvVideo.one('dispose', function() {
                    observer.disconnect();
                    clearInterval(hideErrorInterval);
                });
            }
        }, 1000);
    }
    
    // 플레이어 초기화 확인 및 에러 핸들링 (tech_ 사용으로 'Using the tech directly' 경고 방지)
    cctvVideo.ready(function() {
        console.log('[CCTV] Video.js 플레이어 초기화 완료');
        
        // 초기화 시 즉시 숨기기
        hideErrorElements();
        
        // 주기적으로 확인하여 숨기기 (더 자주 체크)
        const errorCheckInterval = setInterval(hideErrorElements, 150);
        
        // 플레이어 dispose 시 정리
        cctvVideo.one('dispose', function() {
            clearInterval(errorCheckInterval);
        });
        const tech = cctvVideo.tech_;
        let resolvedVhs = null;
        if (tech) {
            resolvedVhs = tech.vhs || tech.hls;
            console.log('[CCTV] Tech:', tech.name_ || 'unknown');
            
            // Chrome에서 VHS 사용 확인 및 강제 설정
            if (browser.isChromium) {
                try {
                    let vhs = resolvedVhs || tech.vhsHandler_ && (tech.vhsHandler_.vhs || tech.vhsHandler_) || (tech.sourceHandler_ && tech.sourceHandler_.vhs);
                    
                    if (vhs) {
                        console.log('[CCTV] VHS 사용 확인됨');
                        if (vhs.options) {
                            vhs.options.overrideNative = true;
                            console.log('[CCTV] VHS overrideNative 설정 완료');
                        }
                    } else {
                        const videoEl = tech.el && tech.el();
                        if (videoEl && videoEl.src) {
                            console.warn('[CCTV] 네이티브 HLS가 사용 중일 수 있습니다. VHS로 전환 시도...');
                            cctvVideo.src({src: httpAddr, type: 'application/x-mpegURL'});
                            cctvVideo.load();
                        }
                    }
                    
                    const videoEl = tech.el && tech.el();
                    if (videoEl) {
                        videoEl.style.transform = 'none';
                        videoEl.style.willChange = 'auto';
                        videoEl.style.backfaceVisibility = 'visible';
                        videoEl.style.webkitTransform = 'none';
                        videoEl.style.mozTransform = 'none';
                        videoEl.setAttribute('disablePictureInPicture', 'true');
                        videoEl.setAttribute('disableRemotePlayback', 'true');
                        
                        // Windows에서 추가 하드웨어 가속 비활성화
                        if (browser.isWindows) {
                            videoEl.style.perspective = 'none';
                            videoEl.style.transformStyle = 'flat';
                        }
                        
                        if (videoEl.requestVideoFrameCallback) {
                            console.log('[CCTV] 하드웨어 가속 비활성화 적용 완료');
                        }
                    }
                } catch (e) {
                    console.warn('[CCTV] VHS 확인 중 오류:', e);
                }
            }
        }
        
        // HLS/VHS 이벤트 핸들러는 tech 준비 후, 조회한 VHS 전달 (경고 및 'VHS를 찾을 수 없습니다' 방지)
        setupHlsEventHandlers(cctvVideo, 'CCTV', httpAddr, resolvedVhs);
        
        // 마지막 프레임 캡처 함수
        const captureLastFrame = function() {
            if (!cctvVideo || cctvVideo.isDisposed()) return null;
            
            try {
                const tech = cctvVideo.tech_;
                if (!tech) return null;
                
                const videoEl = tech.el && tech.el();
                if (!videoEl || videoEl.readyState < 2) return null; // HAVE_CURRENT_DATA 이상이어야 함
                
                // 캔버스 생성 및 현재 프레임 캡처
                const canvas = document.createElement('canvas');
                canvas.width = videoEl.videoWidth || cctvWidth;
                canvas.height = videoEl.videoHeight || (cctvWidth * 9 / 16);
                const ctx = canvas.getContext('2d');
                
                try {
                    ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
                    return canvas.toDataURL('image/jpeg', 0.8);
                } catch (e) {
                    console.warn('[CCTV] 프레임 캡처 실패:', e);
                    return null;
                }
            } catch (e) {
                console.warn('[CCTV] 프레임 캡처 중 오류:', e);
                return null;
            }
        };
        
        // 마지막 프레임을 배경으로 표시
        const showLastFrameAsBackground = function(imageData) {
            if (!imageData) return;
            
            const playerEl = cctvVideo.el();
            if (!playerEl) return;
            
            // 기존 배경 제거
            const existingBg = playerEl.querySelector('.cctv-last-frame-bg');
            if (existingBg) {
                existingBg.remove();
            }
            
            // 배경 이미지 요소 생성
            const bgDiv = document.createElement('div');
            bgDiv.className = 'cctv-last-frame-bg';
            bgDiv.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-image: url(${imageData});
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
                z-index: 1;
                pointer-events: none;
            `;
            
            playerEl.style.position = 'relative';
            playerEl.appendChild(bgDiv);
        };
        
        // 배경 프레임 제거
        const removeLastFrameBackground = function() {
            const playerEl = cctvVideo.el();
            if (playerEl) {
                const bgDiv = playerEl.querySelector('.cctv-last-frame-bg');
                if (bgDiv) {
                    bgDiv.remove();
                }
            }
        };
        
        // 재시도 함수 (무한 재시도, 메시지 표시 없음, 검은 화면 방지)
        const retryStream = function(delay) {
            // 이미 재시도 중이면 중복 실행 방지
            if (isRetrying) {
                return;
            }
            
            isRetrying = true;
            retryCount++;
            // 점진적 재시도 간격: 2초 → 4초 → 8초 → 최대 10초 (간헐적 네트워크/Wowza 서버 문제 대응)
            const retryDelay = delay ? delay * Math.pow(2, retryCount - 1) : Math.min(2000 * Math.pow(2, retryCount - 1), 10000);
            console.log(`[CCTV] 스트림 재시도 중... (${retryCount}회, ${retryDelay/1000}초 후, 스트림: ${cctv.CCTV_NM || '알 수 없음'})`);
            
            // 재시도 전 마지막 프레임 캡처
            const lastFrame = captureLastFrame();
            if (lastFrame) {
                showLastFrameAsBackground(lastFrame);
            }
            
            setTimeout(function() {
                // 재시도 전 오류 메시지 숨기기
                hideErrorElements();
                
                if (cctvVideo && !cctvVideo.isDisposed()) {
                    // reset() 대신 소스만 변경하여 검은 화면 방지
                    // Chrome/Edge 또는 Windows인 경우 VHS 설정 유지하며 재시도
                    if (browser.isChromium || browser.isWindows) {
                        // reset() 호출하지 않고 소스만 변경
                        const tech = cctvVideo.tech_;
                        if (tech) {
                            let vhs = tech.vhs || tech.vhsHandler_ || (tech.sourceHandler_ && tech.sourceHandler_.vhs);
                            if (vhs && vhs.options) {
                                vhs.options.overrideNative = true;
                                console.log('[CCTV] 재시도: VHS overrideNative 설정 완료');
                            } else {
                                console.warn('[CCTV] 재시도: VHS를 찾을 수 없습니다. 네이티브 HLS가 사용될 수 있습니다.');
                            }
                            
                            // 재시도 시에도 하드웨어 가속 비활성화 (Windows/고사양 노트북 호환성)
                            const videoEl = tech.el();
                            if (videoEl) {
                                videoEl.style.transform = 'none';
                                videoEl.style.willChange = 'auto';
                                videoEl.style.backfaceVisibility = 'visible';
                                videoEl.style.webkitTransform = 'none';
                                videoEl.setAttribute('disablePictureInPicture', 'true');
                                videoEl.setAttribute('disableRemotePlayback', 'true');
                                
                                // Windows에서 추가 하드웨어 가속 비활성화
                                if (browser.isWindows) {
                                    videoEl.style.perspective = 'none';
                                    videoEl.style.transformStyle = 'flat';
                                }
                                
                                console.log('[CCTV] 재시도: 하드웨어 가속 비활성화 적용');
                            }
                        }
                    }
                    
                    // 소스만 재설정 (reset() 호출하지 않음으로 검은 화면 방지)
                    cctvVideo.src({
                        src: httpAddr, 
                        type: 'application/x-mpegURL'
                    });
                    cctvVideo.load();
                    
                    // 재시도 후 오류 메시지 계속 숨기기
                    setTimeout(hideErrorElements, 100);
                    setTimeout(hideErrorElements, 500);
                    setTimeout(hideErrorElements, 1000);
                    
                    // 재생 시작 시 배경 프레임 제거 (canplay 이벤트에서 처리되지만 여기서도 확인)
                    cctvVideo.one('canplay', function() {
                        setTimeout(removeLastFrameBackground, 100);
                    });
                    cctvVideo.one('playing', function() {
                        removeLastFrameBackground();
                    });
                    
                    // 재시도 완료 후 플래그 리셋 (재생 성공 시 또는 다음 재시도 준비)
                    setTimeout(function() {
                        isRetrying = false;
                        hideErrorElements(); // 한 번 더 확인
                    }, retryDelay + 1000);
                } else {
                    isRetrying = false;
                }
            }, retryDelay);
        };
        
        // 에러 핸들러 추가 (간헐적 오류 대응 강화)
        cctvVideo.on('error', function() {
            // 오류 메시지 즉시 숨기기
            hideErrorElements();
            
            // 오류 발생 시 마지막 프레임 캡처하여 배경으로 표시
            const lastFrame = captureLastFrame();
            if (lastFrame) {
                showLastFrameAsBackground(lastFrame);
            }
            
            const error = cctvVideo.error();
            if (error) {
                const cctvInfo = `[CCTV: ${cctv.CCTV_NM || '알 수 없음'}, URL: ${httpAddr}]`;
                console.error(`[CCTV] 플레이어 오류 ${cctvInfo}:`, error.code, error.message, error.status ? `HTTP ${error.status}` : '');
                
                // 오류 메시지 숨기기 (지연 후 다시 확인)
                setTimeout(hideErrorElements, 100);
                setTimeout(hideErrorElements, 500);
                setTimeout(hideErrorElements, 1000);
                
                // 404/403 등 스트림 미제공: 재시도 (서버 일시적 문제일 수 있음)
                const status = error.status || (error.metadata && error.metadata.response && error.metadata.response.status);
                const isNotFoundOrForbidden = status === 404 || status === 403 || (error.message && (error.message.indexOf('404') !== -1 || error.message.indexOf('403') !== -1));
                if (isNotFoundOrForbidden) {
                    console.warn(`[CCTV] 스트림을 찾을 수 없거나 접근이 제한됩니다. 재시도합니다. ${cctvInfo} (HTTP ${status || 'N/A'})`);
                    retryStream(3000); // 404/403은 재시도 간격을 조금 더 길게
                    return;
                }
                
                // 타임아웃 감지 (간헐적 네트워크/Wowza 서버 지연 대응)
                const isTimeout = error.message && (error.message.toLowerCase().indexOf('timeout') !== -1 || error.message.indexOf('타임아웃') !== -1);
                if (isTimeout) {
                    console.warn(`[CCTV] 네트워크/Wowza 서버 타임아웃 감지. 재시도합니다. ${cctvInfo}`);
                }
                
                // Chrome에서 디코딩 오류 발생 시 상세 정보 로깅 (tech_ 사용으로 경고 방지)
                if (browser.isChromium && error.code === 3) {
                    const tech = cctvVideo.tech_;
                    if (tech) {
                        const videoEl = tech.el && tech.el();
                        console.error('[CCTV] Chrome 디코딩 오류 상세:', {
                            errorCode: error.code,
                            errorMessage: error.message,
                            techName: tech.name_ || 'unknown',
                            videoSrc: videoEl ? videoEl.src : 'unknown',
                            usingNativeHLS: videoEl && videoEl.src && videoEl.src.includes('m3u8') && !tech.vhs
                        });
                    }
                }
                
                // 에러 코드별 처리
                // 1: MEDIA_ERR_ABORTED, 2: MEDIA_ERR_NETWORK, 3: MEDIA_ERR_DECODE, 4: MEDIA_ERR_SRC_NOT_SUPPORTED
                if (error.code === 3) {
                    // MEDIA_ERR_DECODE: 디코딩 오류 - 재시도
                    console.warn('[CCTV] 디코딩 오류 발생. 재시도합니다.');
                    
                    // Chrome/Edge 또는 Windows인 경우 VHS 사용 확인 및 강제 설정 (tech_ 사용으로 경고 방지)
                    if (browser.isChromium || browser.isWindows) {
                        const tech = cctvVideo.tech_;
                        if (tech) {
                            if (!tech.vhs && !tech.vhsHandler_) {
                                console.warn('[CCTV] 네이티브 HLS가 사용 중입니다. 재시도 시 VHS로 전환 시도합니다.');
                            }
                        }
                    }
                    
                    retryStream(2000);
                } else if (error.code === 4 || error.code === 2) {
                    // MEDIA_ERR_SRC_NOT_SUPPORTED 또는 MEDIA_ERR_NETWORK: 재시도 (간헐적 네트워크 오류 대응)
                    console.warn(`[CCTV] 네트워크/소스 오류 발생. 재시도합니다. ${cctvInfo}`);
                    retryStream(2000);
                } else if (error.code === 1) {
                    // MEDIA_ERR_ABORTED: 사용자 중단이 아닌 경우에만 재시도
                    console.log('[CCTV] 재생 중단됨');
                }
            }
        });
        
        // 성공적으로 재생 시작 시 재시도 카운터 리셋
        cctvVideo.on('playing', function() {
            // 재생 성공 시 오류 메시지 숨기기
            hideErrorElements();
            
            // 재생 성공 시 배경 프레임 제거
            removeLastFrameBackground();
            
            if (retryCount > 0) {
                console.log('[CCTV] 재생 성공. 재시도 카운터 리셋');
                retryCount = 0;
                isRetrying = false;
            }
            // 재생 멈춤 감지 타이머 초기화
            if (stalledTimer) {
                clearTimeout(stalledTimer);
                stalledTimer = null;
            }
        });
        
        // 재생이 멈추는 경우 감지하여 자동 재시도
        cctvVideo.on('waiting', function() {
            console.log('[CCTV] 재생 대기 중...');
            // 오류 메시지 숨기기
            hideErrorElements();
            
            // 마지막 프레임 캡처하여 배경으로 표시
            const lastFrame = captureLastFrame();
            if (lastFrame) {
                showLastFrameAsBackground(lastFrame);
            }
            
            // 5초 이상 멈춰있으면 재시도
            if (stalledTimer) {
                clearTimeout(stalledTimer);
            }
            stalledTimer = setTimeout(function() {
                if (cctvVideo && !cctvVideo.isDisposed() && cctvVideo.paused()) {
                    console.warn('[CCTV] 재생이 5초 이상 멈춰있습니다. 자동 재시도합니다.');
                    hideErrorElements();
                    retryStream(2000);
                }
            }, 5000);
        });
        
        // 재생 중단 감지
        cctvVideo.on('stalled', function() {
            console.warn('[CCTV] 재생이 멈췄습니다. 자동 재시도합니다.');
            // 오류 메시지 숨기기
            hideErrorElements();
            
            // 마지막 프레임 캡처하여 배경으로 표시
            const lastFrame = captureLastFrame();
            if (lastFrame) {
                showLastFrameAsBackground(lastFrame);
            }
            
            if (stalledTimer) {
                clearTimeout(stalledTimer);
            }
            stalledTimer = setTimeout(function() {
                if (cctvVideo && !cctvVideo.isDisposed()) {
                    hideErrorElements();
                    retryStream(2000);
                }
            }, 3000);
        });
        
        // 재생 재개 시 타이머 초기화
        cctvVideo.on('canplay', function() {
            // 재생 가능 시 오류 메시지 숨기기
            hideErrorElements();
            
            // 재생 가능 시 배경 프레임 제거 (재생 직전)
            setTimeout(removeLastFrameBackground, 100);
            
            if (stalledTimer) {
                clearTimeout(stalledTimer);
                stalledTimer = null;
            }
        });
        
        // loadstart 이벤트에서도 오류 메시지 숨기기
        cctvVideo.on('loadstart', function() {
            hideErrorElements();
        });
        
        // loadeddata 이벤트에서 배경 프레임 제거 (데이터 로드 완료 시)
        cctvVideo.on('loadeddata', function() {
            setTimeout(removeLastFrameBackground, 200);
        });
    });

    // 기존 타이머가 있다면 제거
    if (timerPop) {
        clearTimeout(timerPop);
    }

    // 30초 후 자동 닫힘
    timerPop = setTimeout(() => {
        closeCctvOverlay();
    }, 30000);

    centerRelayout(cctv.Y_CRDN, cctv.X_CRDN);
}

function closeCctvOverlay() {
    if (cctvVideo != null) {
        cctvVideo.dispose();
        cctvVideo = null;
    }
    if (cctvOverlay != null) {
        cctvOverlay.close();
        cctvOverlay = null;
    }

    // 타이머 해제
    if (timerPop) {
        clearTimeout(timerPop);
        timerPop = null;
    }
}


//어린이보호구역 상세 팝업 표기
function setDetailSchoolZone(schoolZone) {
    const $popup = $('.popInfoWrap');

    if (schoolZone == null && schoolZone == undefined) {
        console.log('어린이보호구역 상세정보 데이터 없음');
        $roadPopup.hide();
        return;
    }

    $popup.empty(); // 기존 내용 비우기
    $popup.show();

    const popupHTML = `
    <div class="gis-modal schoolzone-modal">
      <div class="gis-modal-header">
        <div class="d-flex space-between gap">
          <h1>${schoolZone.ZONE_NAME}</h1>
          <button type="button" class="button img-btn gis-modal-close-btn" onclick="closePopinfo()">
            <img src="/images/icthome/icon-close.svg" class="invert" alt="닫기" />
          </button>
        </div>
      </div>
      <div class="gis-modal-body">
        <ul class="schoolzone-list">
          <li class="d-flex gap-1">
            <h5>시설종류</h5>
            <p class="body-s">${schoolZone.ZONE_TYPE}</p>
          </li>
          <li class="d-flex gap-1">
            <h5>소재지 도로명주소</h5>
            <p class="body-s">${schoolZone.ZONE_ADDR}</p>
          </li>
          <li class="d-flex gap-1">
            <h5>소재지 지번주소</h5>
            <p class="body-s">${schoolZone.ZONE_ROAD_ADDR}</p>
          </li>
          <li class="d-flex gap-1">
            <h5>관리기관명</h5>
            <p class="body-s">${schoolZone.ZONE_AGENCY}</p>
          </li>
          <li class="d-flex gap-1">
            <h5>관할 경찰서명</h5>
            <p class="body-s">${schoolZone.ZONE_POL_AGENCY}</p>
          </li>
          <li class="d-flex gap-1">
            <h5>보호구역 도로폭</h5>
            <p class="body-s">${schoolZone.ZONE_ROAD_SIZE}m</p>
          </li>
        </ul>
      </div>
    </div>
    `;
    $popup.html(popupHTML);
    centerRelayout(schoolZone.Y_CRDN, schoolZone.X_CRDN);
}

//vms 클릭시 상세정보 데이터 호출
function getDetailVms(vms) {
    let vmsId = vms.VMS_CTLR_NMBR;
    $.ajax({
        url: "/gis/selectVmsImageList.do",
        method: 'POST',
        async: false,
        data: {vms_ctlr_nmbr: vmsId},
        success: (res) => {
            let imgs = JSON.parse(res).result;
            setVmsDetail(vms);
            centerRelayout(vms.Y_CRDN, vms.X_CRDN);
            setVmsImg(imgs);
        },
        error: (err) => {
            console.warn('[GIS] 요청 실패:', (err && err.status) || '', (err && err.statusText) || err);
        }
    });

}

//vms 팝업창 열기
function setVmsDetail(vms) {
    const $popup = $('.popInfoWrap');

    if (vms == null && vms == undefined) {
        console.log('VMS 상세정보 데이터 없음');
        $roadPopup.hide();
        return;
    }

    $popup.empty(); // 기존 내용 비우기
    $popup.show();

    const popupHTML = `
        <div class="gis-modal schoolzone-modal">
              <div class="gis-modal-header">
                <div class="d-flex space-between gap">
                  <h1>[${vms.VMS_NM}]</h1>
                  <button type="button" class="button img-btn gis-modal-close-btn">
                    <img src="/images/icthome/icon-close.svg" class="invert" alt="닫기" onclick="closePopinfo()"/>
                  </button>
                </div>
              </div>
            <img src="data:image/png;base64," id="dsplImg" width="100%" alt="VMS이미지">
        </div>
                `;
    $popup.html(popupHTML);
}

//vms이미지 인터벌 함수
let idx = 0;
let VMS_INTERVAL;

function setVmsImg(imgs) {
    idx = 0;
    if (VMS_INTERVAL != null) {
        clearInterval(VMS_INTERVAL);
    }

    $('#dsplImg').attr('src', 'data:image/png;base64,' + imgs[idx].base64StrImg);
    VMS_INTERVAL = setInterval(function () {
        idx++;
        if (idx >= imgs.length) {
            idx = 0;
        }
        $('#dsplImg').attr('src', 'data:image/png;base64,' + imgs[idx].base64StrImg);
    }, 2000);
}

//노선 클릭시 상세정보 데이터 호출
let ROUTE_INTERVAL;
let ROUTE_REALTIME_INTERVAL;
let ROUTE_REATIME_MARKER_INTERVAL;

function getRouteDetail(route) {
    let cnt = 0;

    if (ROUTE_INTERVAL != null) {
        clearInterval(ROUTE_INTERVAL);
    }

    SELECT_ROUTE_ID = route.ROUTEID;
    MOVE_FROM_ROUTE = SELECT_ROUTE_ID;
    let routeId = route.ROUTEID;

    // 최초 실행 함수
    function fetchRouteDetail() {
        $.ajax({
            url: "/gis/selectRouteDetail.do", method: 'POST', async: false,
            data: {routeId: routeId}, success: (res) => {
                let vrtx = JSON.parse(res).vrtx;
                let bStop = JSON.parse(res).bStop; //정류장
                PATH_ARR = bStop.map(item => item.PATHSEQ);
                let detail = JSON.parse(res).detail;
                if (vrtx.length != 0) {
                    setSelectRouteVrtx(vrtx);
                }
                if (detail.length != 0) {
                    setSelectRouteDetail(detail, bStop);
                }
                ;

                let minLat = 9999;
                let minLng = 9999;
                let maxLat = 0;
                let maxLng = 0;
                $.each(vrtx, function (i, value) {
                    if (minLat > value.LAT) minLat = value.LAT;
                    if (minLng > value.LNG) minLng = value.LNG;
                    if (maxLat < value.LAT) maxLat = value.LAT;
                    if (maxLng < value.LNG) maxLng = value.LNG;
                });
                if (cnt == 0) {
                    centerRelayout((minLat + maxLat) / 2, ((minLng + maxLng) / 2) - 0.05);
                    cnt++;
                }
                oMap.setLevel(7);
            }, error: (err) => {
                console.warn('[GIS] 요청 실패:', (err && err.status) || '', (err && err.statusText) || err);
            }
        });
    }

    // 최초 실행
    fetchRouteDetail();

    getRealtimeBusData();
    if (ROUTE_REALTIME_INTERVAL != null) {
        clearInterval(ROUTE_REALTIME_INTERVAL);
    }
    if (ROUTE_REATIME_MARKER_INTERVAL != null) {
        clearInterval(ROUTE_REATIME_MARKER_INTERVAL);
    }
    ROUTE_REALTIME_INTERVAL = setInterval(getRealtimeBusData, 10000);
}

function setSelectRouteVrtx(data) {
    removeRouteVrtxPolyLine(); // 기존 선들 제거
    bVRTX_ARRAY = []; // 전역 배열 초기화

    let path = [];
    let currentDircd = null;
    let polyline = null;

    $.each(data, function (idx, item) {
        let Y_CRDN = item.LAT;
        let X_CRDN = item.LNG;
        let newPoint = new kakao.maps.LatLng(Y_CRDN, X_CRDN);

        if (item.DIRCD !== currentDircd) {
            if (polyline) {
                polyline.setPath(path);
                polyline.setMap(oMap);
                bVRTX_ARRAY.push(polyline);
            }

            path = [];
            currentDircd = item.DIRCD;
            let strokeColor = (currentDircd == '0') ? '#EB5757' : '#2F80ED';

            polyline = new kakao.maps.Polyline({
                strokeWeight: 2.5,
                strokeOpacity: 0.9,
                strokeStyle: 'solid',
                strokeColor: strokeColor
            });
        }

        path.push(newPoint);
    });

    if (polyline) {
        polyline.setPath(path);
        polyline.setMap(oMap);
        bVRTX_ARRAY.push(polyline);
    }
}


//버스 노선 폴리라인 배열 초기화
function removeRouteVrtxPolyLine() {
    $.each(bVRTX_ARRAY, function (i, v) {
        v.setMap(null);
    });

    bVRTX_ARRAY = [];
}

function setSelectRouteDetail(detail, bStop) {
    let detailInfo = detail[0];

    const $popup = $('.popInfoWrap');

    if (detail == null && detail == undefined) {
        console.log('노선 상세정보 데이터 없음');
        $roadPopup.hide();
        return;
    }

    let maxSeqItem0 = null;
    let maxSeqItem1 = null;


    $.each(bStop, function (idx, item) { // $.each 사용
        if (item.DIRCD == '0') {
            if (maxSeqItem0 === null || item.PATHSEQ > maxSeqItem0.PATHSEQ) {
                maxSeqItem0 = item;
            }
        }
        // DIRCD가 '1' 또는 1인 경우
        else if (item.DIRCD == '1') {
            if (maxSeqItem1 === null || item.PATHSEQ > maxSeqItem1.PATHSEQ) {
                maxSeqItem1 = item;
            }
        }
    });

    $popup.empty(); // 기존 내용 비우기
    $popup.show();
    const popupHTML = `
    
    <div class="gis-modal bus-modal">
      <div class="gis-modal-header">
        <div class="d-flex space-between gap">
          <h1>${detailInfo.ROUTENO}</h1>
          <div class="d-flex align-center gap-xs">
            <button type="button" id="busBtn" class="btn h5 modal-btn" onclick="toggleBusMarker(this)">버스위치 보기</button>
            <button type="button" id="stationBtn" class="btn h5 modal-btn" onclick="toggleBstopMarker(this)">정류장 보기</button>
            <button type="button" class="button img-btn gis-modal-close-btn">
              <img src="/images/icthome/icon-close.svg" class="invert" alt="닫기" onclick="closePopinfo()"/>
            </button>
          </div>
        </div>
        <h5 class="secondary-txt">
          <span>${detailInfo.ORIGINBSTOPKR}</span> ↔
          <span>${detailInfo.DESTBSTOPKR}</span>
        </h5>
      </div>
      <div class="gis-modal-body">
        <div class="d-flex gap-1">
          <h5>배차간격</h5>
          <p class="body-s">평일 ${detailInfo.DAY_BUSDISPT}분 / 주말 ${detailInfo.SATDAY_BUSDISPT}분</p>
        </div>
        <div class="d-flex gap-1">
          <h5>본사     </h5>
          <p class="body-s">${detailInfo.COMPNM}(${detailInfo.TELNO})</p>
        </div>
        <div class="d-flex gap-1">
          <h5>운행대수</h5>
          <p class="body-s">
            현재 <span id="routRunCnt" class="prm-dark-txt">-</span>대 운행중
          </p>
        </div>
        <table class="table body-s txt-center">
          <thead>
            <tr>
              <th rowspan="2">구분</th>
              <th colspan="2">주중</th>
              <th colspan="2">주말</th>
            </tr>
            <tr>
                <th>첫차</th>
                <th>막차</th>
                <th>첫차</th>
                <th>막차</th>
            </tr>
            <tr class="start">
                <td>기점</td>
                <td class="day first">${detailInfo.FIRST_TM}</td>
                <td class="day last">${detailInfo.LAST_TM}</td>
                <td class="sat first">${detailInfo.FIRST_TM_SAT}</td>
                <td class="sat last">${detailInfo.LAST_TM_SAT}</td>
            </tr>
            <tr class="end">
                <td>종점</td>
                <td class="day first">${detailInfo.TURN_FIRST_TM}</td>
                <td class="day last">${detailInfo.TURN_LAST_TM}</td>
                <td class="sat first">${detailInfo.TURN_FIRST_TM_SAT}</td>
                <td class="sat last">${detailInfo.TURN_LAST_TM_SAT}</td>
            </tr>
          </tbody>
        </table>
        <div class="tab">
          <ul class="tab-list">
            <li class="tab-item h5 bg-danger active" dir="상행">${maxSeqItem0.NODENM} 방면</li>
            <li class="tab-item h5 bg-info" dir="하행">${maxSeqItem1.NODENM} 방면</li>
          </ul>
        </div>
        <ul class="bus-realtime-list">
          ${bstopList(bStop)}
        </ul>
      </div>
    </div>
    `
    $popup.html(popupHTML);

    if(STATION_TOGGLE == true){
        $('#stationBtn').click();
    }

    if(BUS_TOGGLE == true){
        $('#busBtn').click();
    }

    $('.tab .tab-item').on('click', function () {
        $('.tab-list .tab-item.active').removeClass('active');
        $(this).addClass('active');
        bStopTabBtn($(this).attr("dir"));
    });

    $('.bus-realtime-list li').on('click', function () {
        if(STATION_TOGGLE !== true){
            $('#stationBtn').click();
        }
        MOVE_FROM_ROUTE = SELECT_ROUTE_ID;
        $.ajax({
            url: "/gis/selectBstopDetail.do",
            method: 'POST',
            async: false,
            data: {stopId:$(this).find('.hidden_id').val(),
            }, success: (res) => {
                let data = JSON.parse(res).result;
                let bStopId = data[0].BSTOPID
                let mMarker = ROUTE_MARKER_ARRAY.find(item => item.data && item.data.id == bStopId);
                changeMarkerImageAll(mMarker, MARKER.BUSSTOP, MARKER.BUSSTOP_SEL);
                getBstopDetail2(data[0]);
            }, error: (err) => {
                console.warn('[GIS] 요청 실패:', (err && err.status) || '', (err && err.statusText) || err);
            }
        });

    });
}

function toggleBusMarker(buttonElement) {
    $(buttonElement).toggleClass('active');

    if ($(buttonElement).hasClass('active')) {
        BUS_TOGGLE = true;
        getRealtimeBusMarker();
        if (ROUTE_REATIME_MARKER_INTERVAL != null) {
            clearInterval(ROUTE_REATIME_MARKER_INTERVAL);
        }
        ROUTE_REATIME_MARKER_INTERVAL = setInterval(getRealtimeBusMarker, 10000);
    } else {
        BUS_TOGGLE = false;
        if (ROUTE_REATIME_MARKER_INTERVAL != null) {
            clearInterval(ROUTE_REATIME_MARKER_INTERVAL);
        }
        if (MARKER_ARRAY['realtimeBusOnMap'] != null) {
            $.each(MARKER_ARRAY['realtimeBusOnMap'], function (idx, marker) {
                marker.setMap(null);
            });
        }
    }
}

function toggleBstopMarker(buttonElement) {
    $(buttonElement).toggleClass('active');

    if ($(buttonElement).hasClass('active')) {
        STATION_TOGGLE = true;
        $.ajax({
            url: "/gis/selectRouteDetail.do", method: 'POST', async: false,
            data: {routeId: SELECT_ROUTE_ID},
            success: (res) => {
                let bStop = JSON.parse(res).bStop; //정류장
                if (bStop.length != 0) {
                    createRouteBstopMarker(bStop);
                }
            }, error: (err) => {
                console.warn('[GIS] 요청 실패:', (err && err.status) || '', (err && err.statusText) || err);
            }
        });
    } else {
        STATION_TOGGLE = false;
        if (ROUTE_MARKER_ARRAY.length != 0) {
            $.each(ROUTE_MARKER_ARRAY, (idx, item) => {
                item.setMap(null);
            });
        }
    }
}

//버스 노선 탭 클릭시 변경 이벤트
function bStopTabBtn(str) {
    $('.tab_cnt.busTab').css('display', 'none');
    switch (str) {
        case '상행':
            $('#busTab1').css('display', 'block');
            break;
        case '하행':
            $('#busTab2').css('display', 'block');
            break;
    }
}

//상행 하행 순환 별 탭내용 표기
function bstopList(bStop) {

    let btGroups = {
        '0': [], '1': []
    };

    $.each(bStop, function (idx, item) { // $.each 사용
        const itemHTML = createBusStopItemHTML(item);
        btGroups[item.DIRCD.toString()].push(itemHTML);
    });

    let tabDivs = []; // jQuery로 DOM 객체 배열을 다루기 위해 빈 배열 선언
    $.each(Object.keys(btGroups), function (index, key) { // $.each로 객체 순회
        const tabId = `busTab${parseInt(key) + 1}`;
        const displayStyle = key === '0' ? '' : 'style="display: none;"';

        const tabDiv = $(`<div id="${tabId}" class="tab_cnt busTab" ${displayStyle}></div>`); // jQuery 객체 생성
        tabDiv.html(btGroups[key].join('')); // jQuery 객체에 HTML 내용 설정
        tabDiv.css('height', '30vh')
        tabDivs.push(tabDiv); // jQuery 객체를 배열에 추가
    });

    let str = '';
    $.each(tabDivs, function (index, tabDiv) { // jQuery 객체 배열 순회
        str += tabDiv[0].outerHTML; // jQuery 객체에서 HTML 문자열 추출
    });

    return str;
}

function getRealtimeBusData() {
    $.ajax({
        type: "POST",
        dataType: "json",
        data: {routeId: SELECT_ROUTE_ID},
        url: "/gis/selectRealtimeBusLocList.do",
        success: function (res) {
            let data = JSON.parse(res).result;
            $('#routRunCnt').text(data.length.toString());
            setRealtimeBusPopup(data);
        }
    });
}


function getRealtimeBusMarker() {
    $.ajax({
        type: "POST",
        dataType: "json",
        data: {routeId: SELECT_ROUTE_ID},
        url: "/gis/selectRealtimeBusLocList.do",
        success: function (res) {
            let data = JSON.parse(res).result;
            setRealtimeBusMarker(data);
        }
    });
}


//팝업창 실시간 버스 위치
function setRealtimeBusPopup(data) {
    $('.bus-realtime-item .busPointer').remove();
    $.each(data, function (idx, item) {
        let busSeq = getApproximateValue(item.PATHSEQ);
        $.each($('.tab_cnt .bus-realtime-item'), function (idx, item2) {
            if ($(item2).attr('seq') == busSeq) {
                $(item2).children('.busPointer').remove();
                $(item2).append(`
                      <div class="busPointer bus-run-info">
                          <div class="bus-num-info">
                            <p class="caption-s secondary-txt num">${item.CARREGNO.substr(5, 4)}</p>
                            <p class="h6 t-info seat seat1">${aaa(item.REMAIND_SEAT, item.CONGESTION)}</p>
                            <p class="caption-s secondary-txt">${lowplantcheck(item.LOWPLATEYN)}</p>
                          </div>
                          <img src="${lowplantcheckimg(item.LOWPLATEYN)}" alt="버스 현재위치" />
                      </div>
                    `)
            }
            ;
        });
    });
}

function getApproximateValue(val) {
    var nearData = 0;                       // 가까운 값을 저장할 변수
    var min = 100;

    for (var i = 0; i < PATH_ARR.length; i++) {
        var compVal = Math.abs(PATH_ARR[i] - val);  // 절대값을 취한다.
        if (compVal == 0) {
            nearData = val;
            break;
        }
        if (min > compVal) {
            min = compVal;
            nearData = PATH_ARR[i];
        }
    }
    return nearData;
}


function lowplantcheck(str) {
    if (str == '1') {
        return '저상';
    } else {
        return '';
    }
}

function lowplantcheckimg(str) {
    if (str == '1') {
        return '/images/icthome/icon-lowfloor-bus.svg';
    } else {
        return '/images/icthome/icon-bus-realtime.svg';
    }
}

function aaa(remaind_seat, congestion) {
    var strTemp = '';
    if (remaind_seat != '' && remaind_seat != '255') {
        strTemp += "<span class='seat seat1'>" + remaind_seat + '석</span>';
    } else if (congestion != '' && congestion != '255') {
        if (congestion == '1') {
            strTemp += "<span class='seat seat1'>여유</span>";
        } else if (congestion == '2') {
            strTemp += "<span class='seat seat2'>보통</span>";
        } else if (congestion == '3') {
            strTemp += "<span class='seat seat3'>혼잡</span>";
        }
    }
    return strTemp;
}

function bbb(remaind_seat, congestion) {
    var str = "";
    if (remaind_seat != "" && remaind_seat != "255" && remaind_seat != undefined) {
        str = "(" + remaind_seat + "석)";
    } else if (congestion != "" && congestion != "255" && congestion != undefined) {
        if (congestion == "1") {
            str += "(여유)";
        } else if (congestion == "2") {
            str += "(보통)";
        } else if (congestion == "3") {
            str += "(혼잡)";
        }
    }
    return str;
}

function ccc(remaind_seat, congestion) {
    var str = "";
    if (remaind_seat != "" && remaind_seat != "255" && remaind_seat != undefined) {
        str = remaind_seat + "석";
    } else if (congestion != "" && congestion != "255" && congestion != undefined) {
        if (congestion == "1") {
            str += "여유";
        } else if (congestion == "2") {
            str += "보통";
        } else if (congestion == "3") {
            str += "혼잡";
        }
    }
    return str;
}

function setRealtimeBusMarker(data) {
    createMarker(data, 'realtimeBusOnMap', MARKER.BUS);
}

//정류소 별 버스 위치 표기
function createBusStopItemHTML(item) {
    return `
    <li class="bus-realtime-item" seq="${item.PATHSEQ}" style="cursor: pointer;">
         <div class="busstop-info item">
              <p class="body-s">${item.NODENM}</p>
              <p class="caption sub-txt">${item.SHORT_BSTOPID}</p>
              <input class="hidden_id" type="hidden" value="${item.BSTOPID}"/>
        </div>
    </li>
    `;
}


//정류장 클릭시 상세정보 데이터 호출
let POPUP_INTERVAL;

function getBstopDetail(bStop) {
    closePopinfo(1, true);

    if (POPUP_INTERVAL != null) {
        clearInterval(POPUP_INTERVAL);
    }
    if (bVRTX_ARRAY.length == 0 && !$('#busStopOnMap').hasClass('active')) {
        setCircleOnMap();
    }
    let yVal = bStop.LAT == null ? bStop.Y_CRDN : bStop.LAT;
    let xVal = bStop.LAT == null ? bStop.X_CRDN : bStop.LNG;
    centerRelayout(yVal, xVal);
    let bStopId = bStop.BSTOPID;

    if(bStop.BSTOPNM == null){
        bStop.BSTOPNM = bStop.NODENM;
    };


    $('.popInfoWrap').html(`
    <div class="gis-modal busstop-modal">
      <div class="gis-modal-header">
        <div class="d-flex space-between gap">
             <h1>${bStop.BSTOPNM}</h1>
             
          <button type="button" class="button img-btn gis-modal-close-btn">
            <img src="/images/icthome/icon-close.svg" class="invert" alt="닫기" onclick="closePopinfo()"/>
          </button>
        </div>
        <h5>ID : ${bStop.SHORT_BSTOPID}</h5>
      </div>
      <div class="gis-modal-body">
        <div class="arr-bus d-flex gap-1 align-center"></div>
        <ul class="bus-info-list"></ul>
      </div>
    </div>
    `);


    // 최초 실행
    fetchBstopDetail();

    // 이후 10초 간격으로 반복 실행
    POPUP_INTERVAL = setInterval(fetchBstopDetail, 10000);



    // 최초 실행 함수
    function fetchBstopDetail() {
        $.ajax({
            url: "/gis/selectBstopDetail.do",
            method: 'POST',
            async: false,
            data: {stopId: bStopId}, success: (res) => {
                let data = JSON.parse(res).result;
                let arrivals = JSON.parse(res).arrivalResult;
                setBstopDetail(data, arrivals);
            }, error: (err) => {
                console.warn('[GIS] 요청 실패:', (err && err.status) || '', (err && err.statusText) || err);
            }
        });
    }

    $('.popInfoWrap').show();
}

function getBstopDetail2(bStop) {
    closePopinfo(1, true);

    if (POPUP_INTERVAL != null) {
        clearInterval(POPUP_INTERVAL);
    }
    if (bVRTX_ARRAY.length == 0 && !$('#busStopOnMap').hasClass('active')) {
        setCircleOnMap();
    }
    let yVal = bStop.LAT == null ? bStop.Y_CRDN : bStop.LAT;
    let xVal = bStop.LAT == null ? bStop.X_CRDN : bStop.LNG;
    centerRelayout(yVal, xVal);
    let bStopId = bStop.BSTOPID;

    if(bStop.BSTOPNM == null){
        bStop.BSTOPNM = bStop.NODENM;
    };


    $('.popInfoWrap').html(`
    <div class="gis-modal busstop-modal">
      <div class="gis-modal-header">
        <div class="d-flex space-between gap">
            <div class="d-flex gap-xs align-center">
            ${MOVE_FROM_ROUTE != null ? `
                <button type="button" class="button img-btn" value="${MOVE_FROM_ROUTE}" onclick="returnRoutePop(this)">
                  <img src="/images/icthome/icon-arrow-prev.svg" class="invert" alt="뒤로">
                </button>` :''}
                <div>
                  <h1>${bStop.BSTOPNM}</h1>
                </div>
            </div>
          <button type="button" class="button img-btn gis-modal-close-btn">
            <img src="/images/icthome/icon-close.svg" class="invert" alt="닫기" onclick="closePopinfo()"/>
          </button>
        </div>
        <h5>ID : ${bStop.SHORT_BSTOPID}</h5>
      </div>
      <div class="gis-modal-body">
        <div class="arr-bus d-flex gap-1 align-center"></div>
        <ul class="bus-info-list"></ul>
      </div>
    </div>
    `);


    // 최초 실행
    fetchBstopDetail();

    // 이후 10초 간격으로 반복 실행
    POPUP_INTERVAL = setInterval(fetchBstopDetail, 10000);



    // 최초 실행 함수
    function fetchBstopDetail() {
        $.ajax({
            url: "/gis/selectBstopDetail.do",
            method: 'POST',
            async: false,
            data: {stopId: bStopId}, success: (res) => {
                let data = JSON.parse(res).result;
                let arrivals = JSON.parse(res).arrivalResult;
                setBstopDetail(data, arrivals);
            }, error: (err) => {
                console.warn('[GIS] 요청 실패:', (err && err.status) || '', (err && err.statusText) || err);
            }
        });
    }

    $('.popInfoWrap').show();
}

let MOVE_FROM_ROUTE = null;
//정류장 상세정보 팝업
function setBstopDetail(bStop, arrivals) {


    if (bStop == null || bStop == undefined) {
        console.log('정류장 상세정보 데이터 없음');
        $roadPopup.hide();
        return;
    }

    const resultList = bStop;
    const arrivalInfo = arrivals;



    if (resultList.length === 0) {
        console.log('정류소 정보 없음');
        alert('정류소 정보가  없습니다');
        return;
    }



    const targetDOM = $('.bus-info-list');
    let aFew = '';
    let aFewCnt = 0;

    // ROUTENO 기준으로 그룹화
    const grouped = {};

    $.each(arrivalInfo, function (i, item) {
        if (!grouped[item.ROUTENO]) {
            grouped[item.ROUTENO] = [];
        }
        grouped[item.ROUTENO].push(item);
    });

    targetDOM.empty();
    // 각 그룹 처리
    $.each(grouped, function (routeNo, items) {
        // 중복 제거: ROUTEID + DIRCD + ARRPLANTM 기준
        const filteredItems = [];
        const seenKeys = new Set();

        items.forEach((item) => {
            const key = `${item.ROUTEID}_${item.DIRCD}_${item.ARRPLANTM}`;
            if (!seenKeys.has(key)) {
                seenKeys.add(key);
                filteredItems.push(item);
            }
        });

        const sortedItems = filteredItems.sort((a, b) => a.ARRPLANTM - b.ARRPLANTM).slice(0, 2);

        // sortedItems가 비어있는 경우를 대비
        if (sortedItems.length === 0) {
            return;
        }

        let arrivalSoon = false;

        const arrivalInfoList = sortedItems.map((item, index) => {
            if (item.ARRPLANTM <= 2) {
                arrivalSoon = true;
            }

            const pClass = index === 0 ? 'body-s arrive' : 'body-s';
            const seatInfo = ccc(item.REMAIND_SEAT, item.CONGESTION);

            return `
            <p class="${pClass}">
              <span class="h5">${item.ARRPLANTM}분</span> (${item.REST_BSTOPCNT}정류장) ${seatInfo}
            </p>
        `;
        }).join('');

        if (arrivalSoon && aFewCnt < 8 && aFew.indexOf(routeNo) === -1) {
            aFew += ` <p class="body-s">${routeNo}</p>`;
            aFewCnt++;
        }

        const addDOM = `
    <li class="bus-info-item">
      <div class="d-flex space-between">
        <div>
          <div class="d-flex align-center bus-num">
            ${routeType(sortedItems[0].ROUTETPCD)}
            <h3>${routeNo}</h3>
            <h5 class="t-danger">${arrivalJudge(arrivalSoon)}</h5>
          </div>
          <p class="caption sub-txt">${sortedItems[0].DIRCD} 방면</p>
        </div>
        <div class="bus-arrive-time">
          ${arrivalInfoList}
        </div>
      </div>
    </li>
    `;

        targetDOM.append(addDOM);
    });

    function arrivalJudge(bool) {
        return bool ? '<h6 class="t-danger">곧 도착</h6>' : '';
    }

    $('.arr-bus').html(`<h6 class="t-danger">곧 도착</h6>` + aFew);
}

function returnRoutePop(ele){
    console.log(ele)
    let clickId = $(ele).val();
    $('#routeList a').each(function (idx, item) {
        let targetId = $(item).attr('id');
        if (targetId === clickId) {
            $(this).trigger('click');
            return false;  // 일치하는 항목 하나만 클릭하고 종료
        }
    });
}

//노선유형코드 [1:지선형, 2:간선형, 3:좌석형, 4:광역형, 5:리무진, 6:마을버스, 7:순환형, 8:급행간선, 9:지선(순환)
function routeType(data) {
    if (data == 1) {
        return `<p class="label label-xs label-info body-s">지선</p>`;
    } else if (data == 2) {
        return `<p class="label label-xs label-success body-s">간선</p>`;
    } else if (data == 3 || data == 10) {
        return `<p class="label label-xs label-secondary-light body-s">좌석</p>`;
    } else if (data == 4) {
        return `<p class="label label-xs label-danger body-s">광역</p>`;
    } else if (data == 5) {
        return `<p class="label label-xs label-danger body-s">리무진</p>`;
    } else if (data == 6) {
        return `<p class="label label-xs label-success body-s">마을</p>`;
    } else if (data == 7) {
        return `<p class="label label-xs label-purple body-s">순환</p>`;
    } else if (data == 8) {
        return `<p class="label label-xs label-pink body-s">급행간선</p>`;
    } else if (data == 9) {
        return `<p class="label label-xs label-purple body-s">지선(순환)</p>`;
    }
}


//스마트교차로 클릭시 상세정보 데이터 호출
function getSmartCrossDetail(smart, smartMarker) {
    let smartId = smart.SPOT_CAMR_ID;
    $.ajax({
        url: "/gis/selectSmartDetail.do", method: 'POST', async: false, data: {smartId: smartId}, success: (res) => {
            let data = JSON.parse(res).result;
            setSmartCrossDetail(data, smartMarker, smartId);
        }, error: (err) => {
            console.warn('[GIS] 요청 실패:', (err && err.status) || '', (err && err.statusText) || err);
        }
    });

}

//스마트교차로 상세정보
let smartOverlay;
let smartVideo;

function setSmartCrossDetail(smartLi, marker, smartId) {
    let smart = smartLi[0];
    removeAllEvtPop();
    if (smartOverlay != null) {
        smartOverlay.close();
    }
    ;

    if (smartVideo != null) {
        if (smartVideo.paused()) {
            smartVideo.pause();
        }
        smartVideo.dispose();
        smartVideo = null;
    }
    ;

    let iwContent = `
    <div class="gis-modal road-info-modal">
      <div class="gis-modal-header">
        <div class="d-flex space-between gap">
          <h1>${smart.SPOT_SRVR_NM}</h1>
          <button type="button" class="img-btn gis-modal-close-btn" onclick="closeSmartOverlay()">
            <img src="/images/icthome/icon-close.svg" class="invert" alt="닫기" />
          </button>
        </div>
        <h5 class="secondary-txt">최근 1시간 교통량</h5>
        <!--<button type="button" class="smartVideoCallBtn">영상보기</button>--> 
      </div>
      <div class="gis-modal-body">
        <ul class="road-info-list">
          <li class="d-flex gap-1">
            <div class="d-flex">
              <h5 class="">승용차</h5>
              <p class="body-s">${smart.CAR}</p>
            </div>
            <div class="d-flex">
              <h5 class="">이륜차</h5>
              <p class="body-s">${smart.MOTOR}</p>
            </div>
          </li>
          <li class="d-flex gap-1">
            <div class="d-flex">
              <h5 class="">소형버스</h5>
              <p class="body-s">${smart.S_BUS}</p>
            </div>
            <div class="d-flex">
              <h5 class="">대형버스</h5>
              <p class="body-s">${smart.L_BUS}</p>
            </div>
          </li>
          <li class="d-flex gap-1">
            <div class="d-flex">
              <h5 class="">소형트럭</h5>
              <p class="body-s">${smart.S_TRUCK}</p>
            </div>
            <div class="d-flex">
              <h5 class="">대형트럭</h5>
              <p class="body-s">${smart.L_TRUCK}</p>
            </div>
          </li>
          <li class="d-flex gap-1">
            <div class="d-flex">
              <h5 class="">합계</h5>
              <p class="body-s">${smart.TOTAL}</p>
            </div>
          </li>
        </ul>
      </div>
    </div>
    `;
    let iwPosition = new kakao.maps.LatLng(marker.Y_CRDN, marker.X_CRDN);
    smartOverlay = new kakao.maps.InfoWindow({
        position: iwPosition, content: iwContent
    });

    smartOverlay.setZIndex(999);
    smartOverlay.open(oMap, marker);


    var markerLatlng = marker.getPosition();
    centerRelayout(markerLatlng.getLat(), markerLatlng.getLng());

    $('.smartVideoCallBtn').on('click', function () {
        smartVideoCallBtn(smartId);
    })

    function smartVideoCallBtn(smartId) {
        $.ajax({
            url: '/gis/selectSmartVideoList.do',
            method: 'POST',
            data: {smartId: smartId.substring(0, 4)},
            dataType: 'json',
            async: false,
            success: (res) => {
                let data = JSON.parse(res).result;
                setSmartVideo(data);
            },
            error: (err) => {
                console.warn('[GIS] 요청 실패:', (err && err.status) || '', (err && err.statusText) || err);
            },
        });
    }
}


window.SMART_VIDEO_LI = [];

function setSmartVideo(data) {

    window.SMART_VIDEO_LI.forEach(instance => {
        if (instance) {
            instance.pause();
            instance.dispose();
        }
    });
    window.SMART_VIDEO_LI = []; // 배열 초기화

    const $popup = $('.popInfoWrap');

    if (!data || data.length === 0) {
        console.log('영상 상세정보 데이터 없음');
        $popup.hide();
        return;
    }

    $popup.empty(); // 기존 내용 비우기
    $popup.show();

    // 팝업 HTML 생성
    const popupHTML = `
        <div class="gis-modal smart-modal" style="width: fit-content; height:530px; overflow-y:auto;">
          <div class="gis-modal-header">
            <div class="d-flex space-between gap">
              <h1>[${data[0].SPOT_SRVR_NM.split('-')[0]}]</h1>
              <button type="button" class="button img-btn gis-modal-close-btn">
                <img src="/images/icthome/icon-close.svg" class="invert" alt="닫기" onclick="closePopinfo()"/>
              </button>
            </div>
          </div>
          <div id="video-modal-body" class="gis-modal-body">
            <div class="video-list"></div>
          </div>
        </div>
    `;

    $popup.html(popupHTML);

    const $videoList = $('.video-list');
    let $rowGroup = null;

    $.each(data, function (idx, item) {
        if (idx % 2 === 0) {
            $rowGroup = $('<div style="display:flex;"></div>');
            $videoList.append($rowGroup);
        }

        const $li = $(`
            <span class="video-item" style="padding:1px;">
                <div><h3>${item.SPOT_SRVR_NM}</h3></div>
                <p class="body-s">
                    <video id="smartPlay${idx}" preload="auto" class="video-js vjs-default-skin smartPlay${idx}"></video>
                </p>
            </span>
        `);

        $rowGroup.append($li);

        // 브라우저 감지
        const browser = detectBrowser();
        
        const options = {
            crossorigin: 'anonymous',
            cors: 'anonymous',
            fullScreen: false,
            autoplay: true,
            width: 300,
            height: 180,
            sources: [
                {
                    /* 추후에 주석 해제 컬럼명 변경 후 아래 두줄 제거
                    src: item.컬럼명,
                    type: 'application/x-mpegURL',*/
                    src: 'https://vjs.zencdn.net/v/oceans.mp4', // 테스트용 URL
                    type: 'video/mp4',
                },
            ],
            // Video.js 8: VHS는 기본적으로 자동 사용됨
            // 크롬/엣지에서만 네이티브 HLS 비활성화하여 VHS 강제 사용
            html5: {
                vhs: {
                    overrideNative: browser.isChromium  // 크롬/엣지에서만 VHS 강제
                }
            }
        };

        // 새 video.js 인스턴스를 생성
        let smartVideo = videojs('smartPlay' + idx, options);
        window.SMART_VIDEO_LI.push(smartVideo); // 🔥 전역 배열에 저장
        
        // 플레이어 초기화 확인
        smartVideo.ready(function() {
            console.log(`[Smart Video ${idx}] Video.js 플레이어 초기화 완료`);
        });
        
        // HLS/VHS 이벤트 핸들러 (HLS 사용 시)
        // 주석: 실제 HLS 스트림 URL이 활성화되면 아래 주석 해제
        // setupHlsEventHandlers(smartVideo, 'Smart', item.컬럼명);

        // 모바일 고려 30초 재생 제한
        let timerPop = setTimeout(function () {
            clearTimeout(timerPop);
            if (smartVideo && !smartVideo.paused()) {
                smartVideo.pause();
            }
            closePopinfo(1);
        }, 30000);
    });
}


function closeSmartOverlay() {
    smartOverlay.close();

    smartOverlay = null;
    window.SMART_VIDEO_LI.forEach(instance => {
        if (instance) {
            instance.pause();
            instance.dispose();
        }
    });
    window.SMART_VIDEO_LI = []; // 배열 초기화
    closePopinfo(1);
}

//교통정보 클래스
function getTrfClass(grad_cd, speed) {
    var clss;
    switch (grad_cd) {
        case 'SRT1':
            if (speed == null || speed == 0) clss = 'lc04'; else if (speed >= 1 && speed <= 40) clss = 'lc03'; else if (speed >= 41 && speed <= 80) clss = 'lc02'; else clss = 'lc01';
            break;

        case 'SRT2':
            if (speed == null || speed == 0) clss = 'lc04'; else if (speed >= 1 && speed <= 30) clss = 'lc03'; else if (speed >= 31 && speed <= 50) clss = 'lc02'; else clss = 'lc01';
            break;

        case 'SRT3':
            if (speed == null || speed == 0) clss = 'lc04'; else if (speed >= 1 && speed <= 20) clss = 'lc03'; else if (speed >= 21 && speed <= 40) clss = 'lc02'; else clss = 'lc01';
            break;

        case 'SRT4':
            if (speed == null || speed == 0) clss = 'lc04'; else if (speed >= 1 && speed <= 10) clss = 'lc03'; else if (speed >= 11 && speed <= 30) clss = 'lc02'; else clss = 'lc01';
            break;

        case 'SRT5':
        case 'SRT6':
        case 'SRT7':
        case 'SRT8':
            if (speed == null || speed == 0) clss = 'lc04'; else if (speed >= 1 && speed <= 14) clss = 'lc03'; else if (speed >= 15 && speed <= 24) clss = 'lc02'; else clss = 'lc01';
            break;
    }
    return clss;
}

function clsfTrafColor(status) {
    if (status == 'lc01') return 'green'; else if (status == 'lc02') return 'yellow'; else if (status == 'lc03') return 'red'; else return 'gray';
}


//선택 된 내역 경로 그리기, 기존 그린 경로 제외 처리
function drawPickVrtxPolyline(list) {
    selectDelVrtxPolyline();
    let resultList = list;
    if (resultList.length == 0) return;
    let pathArray4 = new Array(); //선택된 도로 그리기

    let minLat = 9999;
    let minLng = 9999;
    let maxLat = 0;
    let maxLng = 0;
    $.each(resultList, function (index, value) {
        pathArray4.push(new kakao.maps.LatLng(value.Y_CRDN, value.X_CRDN));

        if (minLat > value.Y_CRDN) minLat = value.Y_CRDN;
        if (minLng > value.X_CRDN) minLng = value.X_CRDN;
        if (maxLat < value.Y_CRDN) maxLat = value.Y_CRDN;
        if (maxLng < value.X_CRDN) maxLng = value.X_CRDN;
        if (index + 1 == resultList.length || value.ID != resultList[index + 1].ID) {

            if (pathArray4 != null) {
                oVrtxPoly4.setPath(pathArray4);
                oVrtxPoly4.setMap(oMap);
                // khjo
                sVRTX_ARRAY.push(oVrtxPoly4);
            }
            pathArray4 = new Array();
            initVrtxPoly();
        }
    });

    roadCenterFlag = true;
    kakao.maps.event.trigger(oMap, 'idle', function () {
        let zoom = oMap.getLevel();
        let bounds = oMap.getBounds();
        if (eventTimer) clearTimeout(eventTimer);
        if (callback) {
            eventTimer = setTimeout(function () {
                callback(zoom, bounds);
            }, 50);
        }
    });
    if (roadCenterFlag) {
        centerRelayout((minLat + maxLat) / 2, (minLng + maxLng) / 2);
        roadCenterFlag = false;
    }
}

//선택 폴리선 초기화
function selectDelVrtxPolyline() {
    deselectRoad();
    $.each(sVRTX_ARRAY, function (i, v) {
        v.setMap(null);
    });
    sVRTX_ARRAY = [];

}

let selectedRoadName = '';

function deselectRoad() {
    selectedRoadName = '';
    ROADNAME = '';
    kakao.maps.event.trigger(oMap, 'idle', function () {
        let zoom = map.getLevel();
        let bounds = map.getBounds();
        if (eventTimer) clearTimeout(eventTimer);
        if (callback) {
            eventTimer = setTimeout(function () {
                callback(zoom, bounds);
            }, 50);
        }
    });
}


let roadCenterFlag = false;

function selectRoad(name) {
    selectedRoadName = name;
    ROADNAME = name;
    roadCenterFlag = true;
    kakao.maps.event.trigger(oMap, 'idle', function () {
        let zoom = map.getLevel();
        let bounds = map.getBounds();
        if (eventTimer) clearTimeout(eventTimer);
        if (callback) {
            eventTimer = setTimeout(function () {
                callback(zoom, bounds);
            }, 50);
        }
    });
}

//팝업닫기
function closePopinfo(flag, isRoute) {
    $('.popInfoWrap').css('display', 'none');
    if (!isRoute) {
        clearInterval(POPUP_INTERVAL);
        clearInterval(ROUTE_REALTIME_INTERVAL);
        clearInterval(ROUTE_REATIME_MARKER_INTERVAL);
    }
    clearInterval(ROUTE_INTERVAL);
    clearInterval(VMS_INTERVAL);
    
    // 주차장 카운터 정리
    if (counterInterval) {
        clearInterval(counterInterval);
        counterInterval = null;
    }


    if (flag != 1) { //1이 아닌경우는 맵에서 노선 지움
        $.each(sVRTX_ARRAY, function (i, v) {
            v.setMap(null);
        });
        $.each(bVRTX_ARRAY, function (i, v) {
            v.setMap(null);
        });
        $.each(ROUTE_MARKER_ARRAY, function (i, v) {
            v.setMap(null);
        });
        $.each(MARKER_ARRAY.realtimeBusOnMap, function (i, v) {
            v.setMap(null);
        });
        bVRTX_ARRAY = [];
        //clearInterval(realtimeBusMap);
        //removeRouteOnMap();
    }
}

//팝업 위치 조정
function setPositionPopup() {
    const sideMenuWidth = $('.side-menu').width();
    const windowWidth = window.innerWidth;

    const isMobile375 = windowWidth <= 430;
    const isMobile768 = windowWidth <= 768;

    // 모바일에서는 전체 화면으로 표시
    if (isMobile768) {
        $('.popInfoWrap').css({
            'position': 'fixed',
            'left': '0',
            'top': '0',
            'right': '0',
            'bottom': '0',
            'width': '100vw',
            'height': '100vh',
            'transform': 'none',
            'z-index': '9999'
        });
    } else if (sideMenuWidth === 0) {
        let translateX = '-50%';
        let translateY = '-50%';

        if (isMobile375) {
            translateX = '-60%';
            translateY = '-38%';
        }

        $('.popInfoWrap').css({
            'left': '50%',
            'top': '50%',
            'transform': `translate(${translateX}, ${translateY})`
        });
    } else {
        $('.popInfoWrap').css({
            'left': sideMenuWidth + 48 + 'px',
            'top': '',
            'transform': ''
        });
    }
}

//지도 중앙 이동
function centerRelayout(lat, lng) {
    oMap.setLevel(5);
    oMap.setCenter(new kakao.maps.LatLng(lat, lng));
}

function removeAllEvtPop() {
    closePopinfo(1);
    if (cctvOverlay != null) {
        closeCctvOverlay();
    }
    if (smartOverlay != null) {
        closeSmartOverlay();
    }
    selectDelVrtxPolyline();
    removeRouteVrtxPolyLine();
    if (MARKER_ARRAY['realtimeBusOnMap'] != null) {
        $.each(MARKER_ARRAY['realtimeBusOnMap'], function (idx, marker) {
            marker.setMap(null);
        });
    }
    if (ROUTE_MARKER_ARRAY.length != 0) {
        $.each(ROUTE_MARKER_ARRAY, (idx, item) => {
            item.setMap(null);
        });
    }
    if (ROUTE_REALTIME_INTERVAL != null) {
        clearInterval(ROUTE_REALTIME_INTERVAL);
    }
    if (ROUTE_REATIME_MARKER_INTERVAL != null) {
        clearInterval(ROUTE_REATIME_MARKER_INTERVAL);
    }
    if (VMS_INTERVAL != null) {
        clearInterval(VMS_INTERVAL);
    }
    if (ROUTE_INTERVAL != null) {
        clearInterval(ROUTE_INTERVAL);
    }
    if (POPUP_INTERVAL != null) {
        clearInterval(POPUP_INTERVAL);
    }
    if (counterInterval) {
        clearInterval(counterInterval);
        counterInterval = null;
    }
    window.SMART_VIDEO_LI.forEach(instance => {
        if (instance) {
            instance.pause();
            instance.dispose();
        }
    });
    window.SMART_VIDEO_LI = []; // 배열 초기화

};


//화면 비율에 따른 변경   
function screenFunc() {

    setPositionPopup();

    if (matchMedia("screen and (max-width: 767px)").matches) {
        $('#schoolZoneOnMap').hide();
        $('#openSignalOnMap').hide();
    }

    if (matchMedia("screen and (max-width: 1024px)").matches) {
        // 1024px 미만에서 사용할 스크립트
        // 지도 메뉴 열기
        $(".m-side-menu-btn").off('click').on('click', function () {
            $('.m-side-menu-btn').css('display', 'none');
            $(".side-menu-wrap").css("display", "block");
            $(".side-menu-wrap").animate({left: "0"}, 400);
            $("#footer").css('display', 'none');
        });
        // 지도 메뉴 닫기
        $(".side-menu .teriary-btn").off('click').on('click', function () {
            $('.m-side-menu-btn').css('display', 'block');
            $(".side-menu-wrap").css("display", "none");
            $(".side-menu-wrap").animate({left: "-23.5rem"}, 400);
            $("#footer").css('display', 'block');
        });

    } else {
        //1024px 이상에서 사용할 스크립트
        //지도 메뉴 닫기
        $(".menu-fold-btn").off('click').on('click', function () {
            if ($(this).hasClass("hide")) {
                $(this).removeClass("hide");
                $(".side-menu-wrap").animate({left: "0"}, 400);
            } else {
                // 지도 메뉴 열기
                $(this).addClass("hide");
                $(".side-menu-wrap").animate({left: "-23.5rem"}, 400);
            }
        });
    } // if...else 블록 끝

    $("details").off('click').on('click', function (e) {
        e.stopPropagation();
    });

    // 지도 범례 펼치기, 접기 (화면 크기에 관계없이)
    $(".map-legend-s").off('click').on('click', function () {
        $(this).hide();
        $(this).next(".map-legend-l").show();
    });

    $(".map-legend-l .close-btn").off('click').on('click', function () {
        $(".map-legend-l").hide();
        $(".map-legend-s").show();
    });
}

// 화면 크기에 관계없이 항상 실행되는 코드 (이벤트 위임)
// 지도 메뉴 하위메뉴 열기
$(document).on('click', '.gis-list-item', function () {
    $(".gis-downmenu-list").slideUp();
    if ($(this).children(".gis-downmenu-list").is(":hidden")) {
        $(this).children(".gis-downmenu-list").slideDown();
    } else {
        $(this).children(".gis-downmenu-list").slideUp();
    }
});

$('.gis-downmenu-item-wrap .gis-downmenu-item').on('click', function () {
    $('.gis-downmenu-list-02').slideUp();
    $(this).next().slideUp();
    if ($(this).next().is(":hidden")) {
        $(this).next().slideDown();
    } else {
        $(this).next().slideUp();
    }
})


// 이벤트 전파 차단 및 아코디언 확장/축소
$(document).on('click', '.gis-downmenu-item .gis-downmenu-item-02', function (e) {
    e.stopPropagation();
});

$(document).on('click', '.gis-downmenu-item', function (e) {
    e.stopPropagation();
});

$(document).on('click', '.gis-downmenu-item-02', function (e) {
    e.stopPropagation();
});
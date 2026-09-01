// Configuration & Constants
const KAKAO_API_KEY = "0236cfffa7cfef34abacd91a6d7c73c0"; // JavaScript Key
const ITS_API_KEY = ""; // legacy backup snapshot only

// Global State
let currentLat = 37.566826;
let currentLng = 126.9786567;
let map;
let markers = [];
let clusterer;
let allCCTVData = [];
let currentCctvList = []; // List of CCTVs in current view
let currentKeyword = "";
let mapInitialized = false;
let centerMarker = null;

// Intersection Observer for performance (Stop video when out of view)
let videoObserver;

// Default location (Seoul City Hall)
const DEFAULT_LAT = 37.566826;
const DEFAULT_LNG = 126.9786567;

# Service Analysis & Proposal

An in-depth review of the National CCTV Integrated Center service from Planning, Design, and Development perspectives.

## 1. Current Status Analysis
### **Plan & Architecture**
- **Strengths**: Low server cost architecture using public API & Client-side Rendering (CSR). HLS.js integration allows playing native streams without backend transcoding.
- **Weaknesses**: Heavy reliance on the client's browser performance. Initial data loading (20k CCTVs) can be heavy.
- **Data Integrity**: "Gu-ri" issue highlighted the fragility of relying on external JSP pages. The move to direct HLS (m3u8) extraction significantly improves robustness.

### **UI / UX (Design)**
- **Strengths**: Clean, dark-mode layout suitable for monitoring. Map cluster integration handles high density well.
- **Weaknesses**:
    - **Mobile**: Previously lacked Safe Area support (Fixed). Touch targets on map popups can be small.
    - **Discovery**: "Search" is the only way to find specific regions if one doesn't know the geography. A "Category" or "Highway" list selector would aid discovery.

### **Development (Code)**
- **Strengths**: Single `index.html` simplicity. Tailwind CSS for rapid styling.
- **Weaknesses**: `app.js` is becoming monolithic. No formal build process (Webpack/Vite) makes tree-shaking impossible.

## 2. Proposals for Improvement

### **Phase 1: Immediate Enhancements (Included in current work)**
- [x] **Direct HLS Playback**: Bypass Iframe issues (Mixed Content, X-Frame) by extracting `.m3u8`.
- [x] **Mobile Optimization**: Apply `safe-area-inset` and responsive sizing.
- [x] **Validation Pipeline**: Partial weekly validation script to monitor stream health without server overload.

### **Phase 2: User Experience (Next Steps)**
1.  **"Nearby CCTVs" Feature**: When viewing a stream, show a list of 5 closest CCTVs below the player for quick navigation along a road.
2.  **Traffic Conditions Overlay**: Integrate ITS Traffic data (Green/Red lines) onto the Kakao Map to correlate video with traffic flow.
3.  **Picture-in-Picture (PiP)**: Enable native browser PiP mode to let users watch CCTV while using other apps.

### **Phase 3: Technical Maturity**
1.  **Migration to Vite/React**: As complexity grows, moving from vanilla JS to React/Vue will help manage state (e.g., "Recently Viewed", "Favorites").
2.  **Server-Side Proxy (Optional)**: If certain streams enforce strict CORS/Referer that frontend cannot bypass, a lightweight proxy (Cloudflare Worker) may be needed.

## 3. Conclusion
The service is transitioning from a simple prototype to a robust utility. The focus on direct HLS extraction is the correct technical direction. UI improvements should focus on "Context" (where is this camera relative to my route?) rather than just "Viewing".

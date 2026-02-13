var $Class = function(oClassMember){
	function ClassOrigin(){
		if(this.$init) this.$init.apply(this, arguments);
	}
	ClassOrigin.prototype = oClassMember;
	ClassOrigin.prototype.constructor = ClassOrigin;
	return ClassOrigin;
};
const cctv = new ($Class({
	searchInterval : null,
	searchIntervalTime : 1000 * 10,
	routeInterval : null,
	nodeObj : {},
	interObj : {},
	curTab : "roadType",
	curLi : 989898,
	dataset : {},
	
	$init:function(){
		let that = this;
		AF.onload(function(){
			that.searchAc();
			that.getTotInciCount();
			that.setEvent();
			that.init();
			mainPg.getCctvList();
		});
	},
	/** 초기화*/
	init : function(){
		/* 도로별 검색 */
		let searchCondition = document.querySelector('#searchCondition li');
		searchCondition.click();
		
		setTimeout(function(){
			document.getElementById('cctvToggle').childNodes[0].click();
		}, 1000*2);
	},
	/** 이벤트 추가*/
	setEvent : function(){
		let that = this;
		
		/* 도로별 교차로별 목록 조회 */
		let searchBtn = document.querySelector('#searchBtn');
		if(searchBtn){
			let searchKeyword = document.querySelector('#searchKeyword');
			searchKeyword.addEventListener('keypress', function(e){
				if(e.keyCode == '13'){
					searchBtn.click();
				}
			});
			searchBtn.addEventListener('click', function(){
				that.searchKeyword = searchKeyword.id;
				that.searchAc();
			});
		}
	},
	/** cctv 총 갯수*/
	getTotInciCount : function(){
		var params = {
			postData:{serviceName: 'cctvService', methodName:'getTotCctvCount'},
			record:{rungEndDtm:[{value:null}]}
		}
		AF.ajax(NS.ctx+"/mpng/getData.json", params, function(returnData){
			var data = returnData.data;
			if(returnData.data){
				renderTotCctvCnt(returnData.data);
			}
		},'json');
	},
	/*통신*/
	geojson: function(url, callback){
		// Create an XMLHttpRequest object
		const xhttp = new XMLHttpRequest();

		// Define a callback function
		xhttp.onload = function(){
			callback(JSON.parse(this.responseText));
		}

		// Send a request
		xhttp.open("GET", url);
		xhttp.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
		xhttp.send();
	},
	runningTraffic: function(){
		let extent = mainApp.map.map.getView().calculateExtent();
		let lnglat1 = mainApp.map.transform_([extent[0], extent[1]], 'EPSG:5181', 'EPSG:4326'); // 위경도로
        let lnglat2 = mainApp.map.transform_([extent[2], extent[3]], 'EPSG:5181', 'EPSG:4326'); // 위경도로
		
		var params = {
			postData : {
				serviceName : "itsTrafficService",
				methodName : 'getGridList',
				paging : false,
				top:lnglat2[1],//extent[2],
				left:lnglat1[0],//extent[1],
				bottom: lnglat1[1],//extent[0],
				right:lnglat2[0],//extent[3]
			}
		}
		
		AF.ajax(NS.ctx+"/mpng/getList.json", params, function(returnData){
			let data = returnData.rows; //실제로 디비에서 호출해오는 데이터를 호출
			
			/* 5번 레이어 생성시 colors에 색상을 정의하시면됩니다. 속도값을 인덱스로 정의하셔서 표출.*/
			let lyr5Temp = mainApp.map.getLayerC({
				lid:'lyr4'
			});
			let src = lyr5Temp.getSource();
			let ftrs = src.getFeatures();
			
			for(let i = 0; i < data.length; i++){
				/* 피처 조회 */
				let ftr = mainApp.map.getFeatureC({
					lid: 'lyr4',
					fid: data[i].linkId
				});
				if(!ftr) continue;
				/* 색상변경 */
				ftr.setStyle(lyr5Temp.istyle[data[i].gdcvGrad]);
			}
		},"json");
	},
	/** 조회 버튼*/
	searchAc : function(){
		let that = this;
		let searchKeyword = document.querySelector('#searchKeyword').value;
		let searchCondition = document.querySelector('#searchCondition li.on'); 
		if(that.searchInterval) clearInterval(that.searchInterval);
		let params = {
			postData: {serviceName: 'cctvService', methodName:'getGridList', paging:false},
			record: {/* gg4Direction:[{value:'1'}] */},
			paging: {recordCountPerPage:5, firstIndex:0},
			sorting: [{column:'saveTime', order:'desc'}]
		}
		NS.loading('#searchList', true); //해당 DIV에 로딩
		let func = (function(){
			AF.ajax(NS.ctx+"/mpng/getList.json", params, function(returnData){
				if(returnData.resultCode == 300) return;
				let rows = returnData.rows;
				for(let i of rows){
					that.dataset[i.cdId] = [i.xCrdn, i.yCrdn];
				}
				cctv.renderCctvList(rows);
				mainApp.setCctv(rows);
				mainApp.setCctvVis(true);
			},'json');
			return function(){
				AF.ajax(NS.ctx+"/mpng/getList.json", params, function(returnData){
					if(returnData.resultCode == 300) return;
					
					let rows = returnData.rows;
					if(typeof curLi !== "undefined"){
						cctv.renderCctvList(rows, curLi);
					}else{
						cctv.renderCctvList(rows);
					}
				},'json');
			}
		})();
		
		that.searchInterval = setInterval(func, that.searchIntervalTime);
	},
	/** 해당 좌표로 이동 */
	moveTo : function(key, type, flag){
		let that = this;
		if(type == 'inter'){
			if(!that.interObj.hasOwnProperty(key)){
				return;
			}
			let data = that.interObj[key];
			mainApp.setIntersection(data);
			
			NS.dataToHtml(data, '#gridPop', renderRoadPop);
//			mainPg.openPop('gridPop', data.xCrdn, data.yCrdn);
			
			mainApp.map.setCenter([data.xCrdn, data.yCrdn]);
			
			return;
		}
		
		if(!that.nodeObj.hasOwnProperty(key)){
			return;
		}
		let data = that.nodeObj[key];
		mainApp.setRoad(data);
		
		let guganLayer = mainApp.map.getLayer('gg4info');
		if(guganLayer) mainApp.map.removeLayer(guganLayer);
		
		let gugan_opt = {
			layers: "ushub:gg4info",
			format: "image/png",
			transparent: true,
			exceptions: "application/vnd.ogc.se_inimage",
			viewparams:'id:'+key
		}
		guganLayer = mainApp.map.addLayerWMS("gg4info", "http://hubmap.its.ulsan.kr/ushub/wms", gugan_opt);
		
		if(type == 'link'){
			mainApp.map.setCenter([data.xx, data.yy]);
			return;
		}
		if(type == 'st'){
			NS.dataToHtml({name:data.nodeShortname1}, '#gridPop', renderBasicPop, renderNoData);
			mainPg.openPopup('gridPop', data.stX2, data.stY2);
			mainApp.map.setCenter([data.stX2, data.stY2]);
			return;
		}
		if(type == 'ed'){
			NS.dataToHtml({name:data.nodeShortname2}, '#gridPop', renderBasicPop, renderNoData);
			mainPg.openPopup('gridPop', data.edX2, data.edY2);
			mainApp.map.setCenter([data.edX2, data.edY2]);
			return;
		}
		
		mainPg.changeZIndex(['Traffic','gg4info','ROAD']);
	},
	/** 노선상세 뒤로가기*/
	roadBack : function(){
		if(this.routeInterval){
			clearInterval(this.routeInterval);
			this.routeInterval = null;
		}
		mainApp.clearFeatures(['ROAD']);
		let guganLayer = mainApp.map.getLayer('gg4info');
		if(guganLayer) mainApp.map.removeLayer(guganLayer);
		
		mainPg.removeTooltip('gridPop');
		mainPg.detailBack();
	},
	renderCctvList : function(rows, curLi){
		cctv.curLi = curLi;
		NS.dataToHtml(rows, '#searchList', renderCctvLists, renderNoData);
	},
	getDataset : function(){
		return this.dataset;
	}
}))();
"use strict";

$(document).ready(function() {
	
	createMap(getVertex);
	initializeLegend(2);
	loadPage();
//	initialize();
//	doGo('https://210.95.12.126/media/1003/chunklist.m3u8');
	
	$(document).on("click", ".listli", function(){
		var lat = $(this).find("input").eq(0).val();
		var lng = $(this).find("input").eq(1).val();
	
		var cId = $(this).attr("id");
		$(this).parent().find(".click").removeClass("click");
		$(this).addClass("click");
		
		$.each(CCTV_MARKERS, function(index, value){
			if(value.id == cId){
				naver.maps.Event.trigger(value, "click");
			}
			
		});
		
	});
});

function loadPage(){
	ajaxCall("traf/selectMainCCTVList.do", null, null, function(list){
		$("#cctv_list").empty();
		var cnt = 0;
		
		$.each(list.resultList, function(index, value){
			if(value.X_CRDN != undefined && value.Y_CRDN != undefined){
				var html = "<li id='"+ value.MGMT_NUM +"' class='listli'>";
				html += "<input type='hidden' name='latLocation' value='"+ value.Y_CRDN +"'>";
				html += "<input type='hidden' name='lngLocation' value='"+ value.X_CRDN +"'>";
				html += "<h4>" + value.LOC_NAME + "</h4>";
				html += value.LOC_ADDR == undefined ? "" : "<p>" + value.LOC_ADDR + "</p>";
				html += "</li>";
				
				$("#cctv_list").append(html);
				cnt++;
			} else {
				console.log(index + " 는 CCTV의 위치좌표가 업습니다.");
			}
		});
		
		$(".count span").text(cnt);
	}, null);
}

//function initialize() {
//	/* 메인화면 바로가기 열기닫기 */
//	$('.list_btn').click(function() {
//		if ($('.main_map_box').hasClass("list_on")) {
//			$('.main_map_box').addClass('list_off');
//			$('.main_map_box').removeClass('list_on');
//		} else {
//			$('.main_map_box').removeClass('list_off');
//			$('.main_map_box').addClass('list_on');
//		}
//		$('.main_map').trigger("resize");
//	});
//}

/** 영상 출력 테스트 */
//function doGo(url) {
//	var xhrArgs = {
//		url:	url,
//		preventCache:	true,
//		sync:		true,
//		handleAs:	"text",
//		headers:	{ 
//					"Content-Type" : "application/json; charset=utf-8" 
//				},
//		load: function(data) {
//			console.log("### ", data);
//			var m3u8Txt = data;
//			var txtArr = m3u8Txt.split("https");
//			var strUrl = "https" + txtArr[txtArr.length - 1];
//			console.log("strUrl ", strUrl);
//			playMp4(strUrl);
//		},
//		error: function(response, ioArgs) {
//			console.log("Failed: "+response);
//		}
//	}	
//	doXhrPost(xhrArgs);
//}
//
//function playMp4(url) {
//	url = url.replace("httpss", "https");
//	
//	if(myvideo == undefined){
//		myvideo = videojs("video", {
//			sources: [
//			          {src : url, type:"video/mp4"}
//			          ],
//          controls : true,
//          playsinline : true,
//          muted : true,
//          preload : "metadata",
//          autoplay : true,
//		});
//	} else {
//		myvideo.dispose();
//		myvideo = videojs("video", {
//			sources: [
//			          {src : url, type:"video/mp4"}
//			          ],
//	          controls : true,
//	          playsinline : true,
//	          muted : true,
//	          preload : "metadata",
//	          autoplay : true,
//		});
//	}
//	
//	var myPlayer = videojs("video");
//	myPlayer.on("play", function(){
//		// cctv 재생
//		$(".pop_cctv_vjs h4").text('※ CCTV 영상은 30초간  제공됩니다.').css({
//			color : "#000000"
//		});
//	})
//	myPlayer.on("ended", function(e){
//		// cctv 끝날 때
//		$(".pop_cctv_vjs h4").text('※ CCTV 영상이 종료되었습니다.').css({
//			color : "#ff0000"
//		});
//	});
//	
////		document.getElementById("video");
////	myvideo.muted = true;
////	myvideo.src = url;
////	myvideo.play();
////	myvideo.addEventListener('ended', myHandler, false);
////    function myHandler(e) {
////    	console.log("play ended ", e);
////    	myvideo.pause();
////    	myvideo.src = "";
//        // What you want to do after the event
////    }
//}
//
//var xhrReq;
//function xhrRequest(params) {
//	this.params = params;
//	this.xhr = window.XMLHttpRequest ? new XMLHttpRequest()
//			: new ActiveXObject("Microsoft.XMLHTTP");
//	
//	this.setParams = function(params) {
//		if (this.waiting) {
//			console.log("xhrRequest: still waiting:" + this.params.url);
//			return false;
//		}
//		this.params = params;
//		return true;
//	}
//	
//	this.waiting = false;
//
//	this.send = function(method) {
//		var url = this.params.url;
//		var today = new Date();
//
//		if (this.params.preventCache)
//			url = url + (url.indexOf('?') > 0 ? "&" : "?")
//					+ "dojo_preventCache=" + today.getTime();
//
//		this.waiting = true;
//		this.xhr.open(method, url, !this.params.sync);
//		
//		this.xhr.onreadystatechange = function() {
//			if (!xhrReq.waiting){
//				console.log(xhrReq.waiting);
//				return;
//			}
//			if (this.readyState == 4) {
//				if (this.status == 200) {
//					try {
//						xhrReq.params.load(
//								xhrReq.params.handleAs == "json" ? JSON
//										.parse(this.responseText)
//										: this.responseText, xhrReq);
//					} catch (e) {
//						console.log("can't call callback for "
//								+ xhrReq.params.url);
//					}
//				} else if (xhrReq.params.error) {
//					try {
//						xhrReq.params.error(this.responseText, xhrReq);
//						alert("session에 연결할 수 없습니다.");
//					} catch (e) {
//						console.log("can't call error callback for "
//								+ xhrReq.params.url);
//					}
//				}
//				xhrReq.waiting = false
//			}
//		}
//		
//		this.xhr.send(method == "POST" ? this.params.postData : null);
//	}
//	
//}
//
//function doXhr(method, params) {
//	if (xhrReq == null){
//		xhrReq = new xhrRequest(params);
//	}
//	else if (!xhrReq.setParams(params))
//		return;
////	xhrReq.setParams(params);
//	xhrReq.send(method);
//	return true;
//}
//
//function doXhrGet(params) {
//	doXhr("GET", params);
//}
//
//function doXhrPost(params) {
//	doXhr("POST", params);
//}


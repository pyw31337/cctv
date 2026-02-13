"use strict";

var cctv_name;
let cctvId;
let uplink = new Array();
let downlink = new Array();
$(document).ready(function() {
//	getDanusisIp();
	// 일반지도, 위성지도, 로드뷰
	createMapTab("mapSettingbtn");
	$(".pop_cctv").hide();
	createMap(getVertex);
	loadPage();
	initialize();
	menuClick("traffic");
	
	$(window).on('resize', function(){
		if(cctvId){
			$.each(CCTV_MARKERS, function(index, value){
				if(value.id == cctvId){
					oMap.setCenter(new kakao.maps.LatLng(value.Y_CRDN,value.X_CRDN));
				}
			});
		}else{
			oMap.setCenter(new kakao.maps.LatLng(centerLat,centerLng));
		}
	});
});

function initialize() {
	
	$("#search_keyword").on("keydown",function(e){
		if(e.keyCode == 13) {
			$("#btn_search_cctv").trigger("click");
		}
	});
	$("#btn_search_cctv").click(function(){
		cctv_name = $("#search_keyword").val();
		
		if(cctv_name.length>0){
			var cctv_expText = new Array();
			var cctv_check_keyword = new Array();
			for(var i =0; i < cctv_name.length; i++){
				cctv_check_keyword[i] = cctv_name.substring(i,i+1);
			}
			
			cctv_expText = ['*','@','^','!','#','$','/','[','%','&','=','>','<',']','/'];
			$.each(cctv_expText,function(index,value){
				for(var h = 0;h<cctv_check_keyword.length;h++ ){
					if(cctv_expText[index]==cctv_check_keyword[h]){
						alert("특수 문자를 입력 할 수 없습니다.");
						cctv_name = '';
						return ;
					} 
				}
			});
			
			var cctv_sqlArray = new Array;
			cctv_sqlArray =['OR','SELECT','INSERT','DELETE','UPDATE','CREATE','DROP','EXEC','UNION','FETCH','DECLARE','TRUNCATE'];
		
			var cctv_regex;
			for(var j = 0; j < cctv_sqlArray.length;j++){
				cctv_regex = new RegExp(cctv_sqlArray[j],"gi");

				if(cctv_regex.test(cctv_name) == true){
					alert("/"+cctv_sqlArray[j]+"/와(과) 같은 특정문자로 검색할 수 없습니다." );
					cctv_name = '';
				}
			}
		}
		
		loadPage();
	})
}

function loadPage() {
	var data = {
		cctv_name : cctv_name
	}
	ajaxCall("traf/selectLiveCCTVList.do", data, null, function(list) {

		$(".trtab1").empty();

		$(".trcount span").empty().text(list.resultList.length)
		if(list.resultList.length == 0){
			var html = "<div style='text-align: center;font-size: 18px;margin-top: 20px; font-weight: bold'>검색결과가 없습니다</div>";
		
			$("#cctvlist").children("ul").append(html);
			return ;
		}
		
		$.each(list.resultList, function(index, value) {
			if(value.X_CRDN != undefined && value.Y_CRDN != undefined) {
				const html = `<li><button id="${value.DEVC_ID}">${value.LOC_NAME}</button></li>`;

				$("#cctvul").append(html);
			} else {
				console.log(index + " 는 CCTV의 위치 데이터가 없습니다.");
			}
		});
		
		setCctvMarkers(list);
	}, null);
	
	$("#cctvul").on("click",function(e) {
		if(e.target.nodeName == "UL" || e.target.nodeName == "LI") {return; }
		var title = e.target.textContent;
		cctvId = e.target.attributes.id.value;
		$('.trtab1 li button').attr("title",title);
		
		var window_width = $(window).width();	
		
		if(window_width <= 1440) { //mob 화면 
				$(".trafficwrap").addClass("listoff");
			}else{  //pc 화면, 영상 재생중일때
				$(".trafficwrap").removeClass("listoff");
			}
		
		var loc_name = e.target.textContent;
		if(e.target.parentNode.className =='click'){
			$(".trtab1 li").removeClass('click');
		    e.target.parentNode.setAttribute("title",'');
			$(".popup").remove();
	   	    $.each(CCTV_MARKERS, function(index, value){
	   	 	const imageSize   = new kakao.maps.Size(MARKER["CCTV_SIZE"]["W"], MARKER["CCTV_SIZE"]["H"]);
	   	    const imageOption = {offset: new kakao.maps.Point(0, 0), alt : loc_name + ' CCTV'}; 
		         if(value.id == cctvId){
		           value.setImage(new kakao.maps.MarkerImage(MARKER.CCTV_NORMAL_IMG , imageSize, imageOption));
		           value.name = 'unClick';
		         }
		     });
	   	    oMap.setZoomable(true);
		}else{
	    	$(".trtab1").children("li").removeClass();
		    $('.popup').remove();
	        $(this).children("li").removeAttr('title');
	    	e.target.parentNode.className = 'click'; 
	 	    e.target.setAttribute("title",title+' 선택됨');
	   	    $.each(CCTV_MARKERS, function(index, value){
		         if(value.id == cctvId){
		            kakao.maps.event.trigger(value, "click");
		            // 웹 접근성
	  				$(".btnre").focus();
		         }
		     });
	   	    oMap.setZoomable(false);
		}
	  }); 
}



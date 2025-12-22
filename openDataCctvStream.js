/**************************************************************************************
 * 000000
 **************************************************************************************/
function StreamCctv(cctvid, mapType, callback){
  if(cctvid.CCTVID != null) {
    cctvid = cctvid.CCTVID ;
  }

  var cctvObj;
  
  $.ajax({
    url: '/map/getCctvInfoById.do?cctvId=' + cctvid,
    async: false,
    success: function(data) {
      // cctvObj = JSON.parse(data);
      cctvObj = data;
    }
  });
  
  this.gWidth      = "320";
  this.gHeight     = "245";
  this.gCctvId     = cctvObj.CCTVID;
  this.gCctvName   = cctvObj.CCTVNAME;
  this.gCenterName = cctvObj.CENTERNAME;
  this.gDx         = cctvObj.XCOORD;
  this.gDy         = cctvObj.YCOORD;
  this.gLocate     = cctvObj.LOCATE;
  this.gCctvIp     = cctvObj.CCTVIP;
  this.gPort       = cctvObj.PORT;
  this.gCh         = cctvObj.CH;
  this.gId         = cctvObj.ID;
  this.gPasswd     = cctvObj.PASSWD;
  this.gMovie      = cctvObj.MOVIE;

  if(this.gCctvId.substring(0, 3) == 'L01'){
    this.gKind = 'Seoul';
  } else if(this.gCctvId.substring(0, 3) == 'L02'){
    this.gKind = 'N';
  } else if(this.gCctvId.substring(0, 3) == 'L03'){
    this.gKind = 'O';
  } else if(this.gCctvId.substring(0, 3) == 'L04'){
    this.gKind = 'P';
  } else if(this.gCctvId.substring(0, 3) == 'L08'){
    this.gKind = 'd';
  } else{
    this.gKind = cctvObj.KIND;
  }

  // 레이어팝업 - 정지영상, 유고처리
  this.getImageHtml = function(){
    if(this.gMovie == 'U'){//유고처리
      var width = 322;
      var height = 239;
      var top = (window.screen.height - height) / 2;
      var left = (window.screen.width - width) / 2;
      var features = 'width='+ width +',height='+ height +',top='+ top +',left='+ left +',toolbar=no,scrollbars=no,status=no,resizable=no,location=no';
      window.open('/view/map/cctvUgo.jsp', 'UTIC도시교통정보센터', features);
    }else{//정지영상
      var path="/images/map/cctv_no.gif";
      var btn="<a onclick='javascript:;' class='pdr'></a>";
      if(this.gLocate != null){
        path = networkCheck.getCctvPath();
        path += this.gLocate.substring(this.gLocate.lastIndexOf("/")+1,this.gLocate.length);
      }

      if(this.gMovie == 'Y'){
        btn = "<a onclick='javascript:cctvPopup.hidePopup(\"" + this.gCctvId  + "\");cctv.popupCctvStream(\"" + this.gCctvId + "\");' class='pdr'><img src='./../../contents/images/map/btn_gomovie.gif' alt='동영상보기' /></a>";
      }
      return "<div class='screenshop shad cctv'>"
         + "<p class='hd'>" + this.gCctvName + "<span>" 
         + btn
         + "<a onclick='javascript:cctvPopup.hidePopup(\"" + this.gCctvId  + "\");'><img src='/images/map/btn_cctv_clse.gif' alt='닫기' /></a></span></p>"
         + "<div class='screenshot_area player'>"
         + "<img src='" + path + "' alt='정지영상' width='100%' height='100%' />"
         + "</div>"
         + "<p class='bot'>" + this.gCenterName + "</p>"
         + "</div>";
    }
  };

  // 레이어팝업 - 동영상(default 영상)
  this.getStreamHtml = function(){
    
    var objectHtml = this.objectHTML();
    return "<div class='video shad cctv'>"
       + "<p class='hd'>" + this.gCctvName + "<span>"
       + "<a onclick='javascript:self.close();'><img src='/images/map/btn_cctv_clse.gif' alt='닫기' /></a></span></p>"
       + "<div class='cctv_area player' width='" + this.gWidth + "' height='" + this.gHeight + "'>" + objectHtml + "</div>"
       + "<p class='bot03'></p>"
       + "<p class='bot02'>" + this.gCenterName + "</p>"
       + "</div>";
  };

  this.objectHTML = function(){
    var objectHtml = '';
    switch(this.gKind){
      case 'A':
        //서울 내부순환도로 동영상 A 
        objectHtml = this.cctvHTML_A();
        break;
      case 'D':
        //수도권 국도(서울 국토)
        objectHtml = this.cctvHTML_D();
        break;
      case 'E':
        //대전
        objectHtml = this.cctvHTML_E();
        break;
      case 'F':
        //전주
        objectHtml = this.cctvHTML_F();
        break;
      case 'G':
        //광주
        objectHtml = this.cctvHTML_G();
        break;
      case 'I':
        //부산
        objectHtml = this.cctvHTML_I();
        break;
      case 'J':
        //울산
        objectHtml = this.cctvHTML_J();
        break;
      case 'K':
        //제주
        objectHtml = this.cctvHTML_K();
        break;
      case 'L':
        //한국도로공사 
        objectHtml = this.cctvHTML_Lx();
        break;
      case 'M':
        //원주
        objectHtml = this.cctvHTML_M();
        break;
      case 'Q':
        //대전지방국토관리청
        objectHtml = this.cctvHTML_Q();
        break;
      case 'S':
        //부산지방국토관리청
        objectHtml = this.cctvHTML_S();
        break;
      //case 'T':
        //안산
        //objectHtml = this.cctvHTML_T();
        //break;
      case 'U':
        //서울외곽순환고속도로
        objectHtml = this.cctvHTML_U();
        break;
      case 'X':       
        //안양
        objectHtml = this.cctvHTML_X();
        break;          
      case 'N':
      case 'L02':
        //인천
        objectHtml = this.cctvHTML_N();
        break;
      case 'P':
      case 'E53':
        //광양
        objectHtml = this.cctvHTML_P();         
        break;
      case 'V':
        //군산
        objectHtml = this.cctvHTML_V();         
        break;
      case 'W':
        //포항
        objectHtml = this.cctvHTML_W();
        break;    
      case 'Z':
        //천안
        objectHtml = this.cctvHTML_Z();
        break;
      case 'a':
        //과천
        objectHtml = this.cctvHTML_Aa();
        break;
      case 'b':
        //성남
        objectHtml = this.cctvHTML_Bb();
        break;
      case 'c':
        //시흥
        objectHtml = this.cctvHTML_Cc();
        break;
      //case 'd':
        //용인
      //  objectHtml = this.cctvHTML_Dd();
      //  break;
      case 'm':
        //원주
        objectHtml = this.cctvHTML_Mm();
        break;
      case 'Seoul':
        //서울
        objectHtml = this.cctvHTML_Seoul();
        break;
      case 'y':
        //여수 - 2015.09.25 추가
        objectHtml = this.cctvHTML_y();
        break;
    }
    return objectHtml;
  };

  this.cctvPlay = function(){
    try{
      switch(this.gKind){
        case 'F':
          //전주F
          this.cctvPlay_F();
          break;
        case 'G':
          //광주(전라)
          this.cctvPlay_G();
          break;
        case 'I':
          //부산
          this.cctvPlay_I();
          break;          
        case 'K':
          //제주
          this.cctvPlay_K();
          break;
        case 'M':
          //원주
          this.cctvPlay_M();
          break;
        case 'U':
          //서울외곽순환고속도로
          this.cctvPlay_U();
          break;  
        case 'X':       
          //안양
          this.cctvPlay_X();
          break;          
        //case 'V':
          //군산
        //  this.cctvPlay_V();          
        //  break;  
        case 'L':
          //한국도로공사 
          this.cctvHTML_Lx();
          break;
      }
    }catch(e){
      alert(e);
    }
  };

  //서울 내부순환도로 동영상 A
  this.cctvHTML_A = function(){
    return "<object id='mov' width='" + this.gWidth + "' height='" + this.gHeight + "' classid=CLSID:22d6f312-b0f6-11d0-94ab-0080c74c7e95 codebase='http://activex.microsoft.com/activex/controls/mplayer/en/nsmp2inf.cab#Version=6,4,5,715' type='application/x-oleobject'" 
      + "standby='Loading...' type=application/x-oleobject>"
      + "<param name='FileName' VALUE='http://smartway.seoul.go.kr/infoImg/cctv/asx/" + this.gCctvIp + "'>"
      + "<param name='ShowControls' VALUE='0'>"
      + "<param name='ControlType' VALUE='1'>"
      + "<param name='AutoStart' VALUE='1'>"
      + "<param name='ShowDisplay' VALUE='0'>"
      + "<param name='Enabled' VALUE='true'>"
      + "<param name='Volume' VALUE='0'>"
      + "<param name='BufferingTime' VALUE='1'>"
      + "<param name='PlayCount' VALUE='0'>"
      + "<param name='EnableContextMenu' Value='0'>"
      + "<param name='ShowGotoBar' VALUE='0'>"
      + "<param name='ShowStatusBar' VALUE='0'>"
      + "</object>";
  };

  //건교부 수도권국도교통센터 동영상(서울국토) D
  this.cctvHTML_D = function(){ 
    return "<iframe frameborder='0' marginheight='0' scrolling='no' src='http://210.99.10.240/default.asp?cctv_id=" + this.gId + "&cctv_chn=" + this.gCctvIp + "&cctv_nm=" + this.gCctvName + "' width='" + this.gWidth + "' height='" + this.gHeight + "'></iframe>";
  };

  //전주 동영상 F
  this.cctvHTML_F = function(){
    if(this.gCh == "2"){
      return '<object width="'+this.gWidth+'" height="'+ this.gHeight +'" id="player" classid="CLSID:6BF52A52-394A-11d3-B153-00C04F79FAA6" standby="Loading  Windows  Media  Player  components..." viewastext="">'
        +'<param name="URL" value="mms://'+this.gCctvIp+':'+this.gId+'">'
        +'<param name="rate" value="1">'
        +'<param name="balance" value="0">'
        +'<param name="currentPosition" value="4.795">'
        +'<param name="defaultFrame" value="">'
        +'<param name="playCount" value="1">'
        +'<param name="autoStart" value="-1">'
        +'<param name="currentMarker" value="0">'
        +'<param name="invokeURLs" value="-1">'
        +'<param name="baseURL" value="">'
        +'<param name="volume" value="50">'
        +'<param name="mute" value="0">'
        +'<param name="uiMode" value="none">'
        +'<param name="stretchToFit" value="-1">'
        +'<param name="windowlessVideo" value="0">'
        +'<param name="enabled" value="-1">'
        +'<param name="enableContextMenu" value="0">'
        +'<param name="fullScreen" value="0">'
        +'<param name="SAMIStyle" value="">'
        +'<param name="SAMILang" value="">'
        +'<param name="SAMIFilename" value="">'
        +'<param name="captioningID" value="">'
        +'<param name="enableErrorDialogs" value="0">'
        +'<param name="_cx" value="6773">'
        +'<param name="_cy" value="5080">'
        +'<param name="URL" value="mms://'+this.gCctvIp+':'+this.gId+'">'
        +'<param name="rate" value="1">'
        +'<param name="balance" value="0">'
        +'<param name="currentPosition" value="0">'
        +'<param name="defaultFrame" value="">'
        +'<param name="playCount" value="1">'
        +'<param name="autoStart" value="1">'
        +'<param name="currentMarker" value="0">'
        +'<param name="invokeURLs" value="-1">'
        +'<param name="baseURL" value="">'
        +'<param name="enableContextMenu" value="0">'
        +'<param name="volume" value="50">'
        +'<param name="mute" value="0">'
        +'<param name="uiMode" value="none">'
        +'<param name="stretchToFit" value="1">'
        +'<param name="windowlessVideo" value="0">'
        +'<param name="enabled" value="1">'
        +'<param name="fullScreen" value="0">'
        +'<param name="SAMIStyle" value="">'
        +'<param name="SAMILang" value="">'
        +'<param name="SAMIFilename" value="">'
        +'<param name="captioningID" value="">'
        +'<param name="enableErrorDialogs" value="0">'
        +'</object>'
        
    } else if(this.gCh == "3"){
    }
  };  

  //제주 동영상 K
  this.cctvHTML_K = function(){
    return "<object id='mov' width='" + this.gWidth + "' height='" + this.gHeight + "' codeBase='http://www.jejuits.go.kr/New/vm/nvrservice.cab#version=1,0,0,8' classid='CLSID:F426C152-9E07-40AA-AAC3-669D4D44999E'>"
      + "<param name='_Version' value='65536'>"
      + "<param name='_ExtentX' value='8467'>"
      + "<param name='_ExtentY' value='6747'>"
      + "<param name='_StockProps' value='0'>"
      + "</object>";
  };

  //원주 M
  this.cctvHTML_M = function(){
    return "<object id='mov' width='100%' height='" + this.gHeight + "' codebase='http://www.camtour.co.kr/webeye/wg_webeye.cab' classid='clsid:A8739816-022C-11D6-A85D-00C04F9AEAFB' align='center' VIEWASTEXT>"
      + "<embed type='application/x-webeye' width='100%' height='" + this.gHeight + "' align='center' pluginspage='http://www.camtour.co.kr/webeye/wg_webeye-install.html' img_resolution='2' img_expand='1'>"
      + "</embed>"
      + "</object>";
  };

  //원주지방국토관리청 m 
  this.cctvHTML_Mm = function(){
    return "<object id='mov' width='" + this.gWidth + "' height='" + this.gHeight + "' classid='CLSID:22D6f312-B0F6-11D0-94AB-0080C74C7E95' codebase='http://activex.microsoft.com/activex/controls/mplayer/en/nsmp2inf.cab#Version=5,1,52,701' type='application/x-oleobject' standby='Loading...' VIEWASTEXT>"
      + "<param name='filename' value='mms://" + this.gCctvIp + ":" + this.gId + "' />"
      + "<param name='animationatstart' value='1' />"
      + "<param name='AutoStart' value='1' />"
      + "<param name='balance' value='0' />"
      + "<param name='currentmarker' value='0' />"
      + "<param name='currentposition' value='0' />"
      + "<param name='displaymode' value='4' />"
      + "<param name='enablecontextmenu' value='0' />"
      + "<param name='enabled' value='1' />"
      + "<param name='fullscreen' value='0' />"
      + "<param name='invokeurls' value='1' />"
      + "<param name='PlayCount' value='1' />"
      + "<param name='rate' value='1' />"
      + "<param name='showcontrols' value='0' />"
      + "<param name='showstatusbar' value='0' />"
      + "<param name='stretchtofit' value='0' />"
      + "<param name='transparentatstart' value='1' />"
      + "<param name='uimode' value='FULL' />"
      + "<param name='displaybackcolor' value='0' />"
      + "<embed id='player' animationatstart='1' autostart='1' displaybackcolor='black' showcontrols='1' showstatusbar='0' showtracker='1' showpositioncontrols='0' pluginspage='http://www.microsoft.com/korea/windows/windowsmedia/'src='mms://" + this.gCctvIp + "/" + this.gId + "' type='video/x-ms-asf-plugin' title='CCTV 실시간동영상'>"
      + "</embed>"
      + "</object>";         
  };

  //대전지방국토관리청 Q
  this.cctvHTML_Q = function(){
    if(this.gCctvIp.substr(0,3) != 'dvr'){
      var html = "<object id='mov' width='" + this.gWidth + "' height='" + this.gHeight + "' classid='CLSID:6BF52A52-394A-11d3-B153-00C04F79FAA6' codebase='http://activex.microsoft.com/activex/controls/mplayer/en/nsmp2inf.cab#Version=6,4,5,715' standby='Loading...' VIEWASTEXT>"
           + "<param name='URL' value='mms://" + this.gCctvIp + "/live" + this.gId + "'>"
           + "<param name='rate' value='1'>"
           + "<param name='balance' value='0'>"
           + "<param name='currentPosition' value='0'>"
           + "<param name='defaultFrame' value='0'>"
           + "<param name='playCount' value='1'>"
           + "<param name='autoStart' value='1'>"
           + "<param name='currentMarker' value='0'>"
           + "<param name='invokeURLs' value='-1'>"
           + "<param name='baseURL' value>"
           + "<param name='enableContextMenu' value='0'>"
           + "<param name='volume' value='50'>"
           + "<param name='mute' value='0'>"
           + "<param name='uiMode' value='none'>"
           + "<param name='stretchToFit' value='1'>"
           + "<param name='windowlessVideo' value='0'>"
           + "<param name='enabled' value='1'>"
           + "<param name='fullScreen' value='0'>"
           + "<param name='SAMIStyle' value=''>"
           + "<param name='SAMILang' value=''>"
           + "<param name='SAMIFilename' value=''>"
           + "<param name='captioningID' value=''>"
           + "<param name='enableErrorDialogs' value='0'></object>";
      return html;
    }            
  };

  //안산 T
  //this.cctvHTML_T = function(){
  //  return "<div id='Layer1' style='z-index: 1; position: absolute; top: 0px; left: 0px; overflow: hidden; width: 320; height: 280; float: left; margin-left: 10px;'>"
  //      + "<iframe src='http://its.iansan.net/streamCctv.do?commPort=" + this.gPort + "' frameborder='0' width='320' height='280' scrolling='no'  />"
  //      + "</div>"  
  //};

  //서울외곽순환고속도로 U
  this.cctvHTML_U = function(){
    return "<OBJECT id='mov' width='" + this.gWidth + "' height='" + this.gHeight + "' classid='CLSID:7CF64D27-519C-4EA1-A979-ACDDB8764E49' codebase='http://www.flexwatch.com/app_link/download/FwMediaCtl.cab'>"
      + "<param name='strIpAddr' value='" + this.gCctvIp + "'>"
      + "<param name='iSvrID' value='0'>"
      + "<param name='iChnID' value='" + this.gCh + "'>"
      + "<param name='strUserID' value='root'>"
      + "<param name='strUserPWD' value='root'>"
      + "<param name='iPauseTime' value='0'>"
      + "<param name='iTimeout' value='5'>"
      + "</OBJECT>";    
  };

  //안양 X (220.90.139.14)
  this.cctvHTML_X = function(){
    return "<object id='mov' width='" + this.gWidth + "' height='" + this.gHeight + "' classid='CLSID:DD01C8CA-5DA0-4b01-9603-B7194E561D32' codebase='http://58.76.192.14/rel/webViewer.cab#Version=1,5,49,125'>"
      + "</object>";    
  };

  
  //인천 N & L02
  this.cctvHTML_N = function(){
    return "<object id='mov' width='" + this.gWidth + "' height='" + this.gHeight + "' classid='CLSID:22d6f312-b0f6-11d0-94ab-0080c74c7e95' type='application/x-oleobject' standby='Loading...' VIEWASTEXT>"
      + "<param name='FileName' value='mms://stream.fitic.go.kr/CCTV" + this.gCctvId.substring(this.gCctvId.length-2,this.gCctvId.length) + "'>"
      + "<param name='ShowControls' value='0'>"
      + "<param name='ControlType' value='1'>"
      + "<param name='AutoStart' value='1'>"
      + "<param name='ShowDisplay' value='0'>"
      + "<param name='Enabled' value='ture'>"
      + "<param name='Volume' value='0'>"
      + "<param name='BufferingTime' value='1'>"
      + "<param name='PlayCount' value='1'>"
      + "<param name='EnableContextMenu' value='0'>"
      + "<param name='ShowGotoBar' value='0'>"
      + "<param name='ShowStatusBar' value='1'>"
      + "</object>";    
  };

  //부천 O & L03
  this.cctvHTML_O = function(){};

  //광양 P & E53
  this.cctvHTML_P = function(){
    return "<div style='margin: -100 -190; width:" + this.gWidth + "px; height:" + this.gHeight + "px;'>" 
     + "<iframe src='http://its.gwangyang.go.kr/traffic/cctv.do?cctvid=" + this.gCctvId + "' frameborder='0' width='" + this.gWidth + "' height='" + this.gHeight + "' scrolling='no'></iframe>"
     + "</div>" ;
  };

  // 군산
  this.cctvHTML_V = function(){
    
    var pwd = this.gCctvIp.split(".")[3];
    
    return "<object id='Player' width='" + this.gWidth + "' height='" + this.gHeight + "' codeBase='http://its.gunsan.go.kr/images/AMC.cab#Version=2.0' classid='CLSID:745395C8-D0E1-4227-8586-624CA9A10A8D'>"
      + "<param name='AutoStart' value='1'>"
      + "<param name='UIMode' value='none'>"
      + "<param name='MediaType' value='mjpeg'>"
      + "<param name='NetworkTimeout' value='5000'>"
      + "<param name='MediaUsername' value='root'>"
      + "<param name='MediaPassword' value='gits" + pwd + "!'>"
      + "<param name='MediaURL' value='http://" + this.gCctvIp + "/axis-cgi/mjpg/video.cgi'>"
      + "<param name='EnableContextMenu' value='true'>"
      + "<param name='StretchToFit' value='true'>"
      + "<param name='MaintainAspectRatio' value='true'>"
      + "</object>";
  };  
  
  // 군산 
  //this.cctvPlay_V = function(){
  //  try{
  //    var player = parent.document.getElementById("mov");
  //      player.ChannelSelect(this.gCh, 1);
  //      player.StartEx(this.gCctvIp, '', '', 'guest', 'guest', '', '', '');
  //  }catch(e){
  //    alert(e);
  //  }
  //};
  
  // 여수
  this.cctvHTML_y = function(){   
    return "<object id='Player' width='" + this.gWidth + "' height='" + this.gHeight + "' codeBase='http://its.yeosu.go.kr/AMC.cab' classid='CLSID:745395C8-D0E1-4227-8586-624CA9A10A8D'>"       
      + "<param name='_cx' value='21167'>"
      + "<param name='_cy' value='15875'>"
      + "<param name='MediaURL' value='http://112.164.152." + this.gCctvIp + "/axis-cgi/mjpg/video.cgi?resolution=2CIF&amp;camera=" + this.gCh + "'>"
      + "<param name='AutoStart' value='-1'>"
      + "<param name='UIMode' value='none'>"
      + "<param name='Mute' value='-1'>"
      + "<param name='Volume' value='30'>"
      + "<param name='MediaUsername' value='root'>"
      + "<param name='MediaPassword' value='ystits#$'>"
      + "<param name='NetworkTimeout' value='5000'>"
      + "<param name='MediaType' value='mjpeg-unicast'>"
      + "<param name='FullScreen' value='0'>"
      + "<param name='MediaFile' value=''>"
      + "<param name='StretchToFit' value='-1'>"
      + "<param name='ShowToolbar' value='0'>"
      + "<param name='ShowStatusBar' value='0'>"
      + "<param name='PTZControlURL' value=''>"
      + "</object>";
  };
  
  //포항 W
  this.cctvHTML_W = function(){
    return "<object id='mov' width='" + this.gWidth + "' height='240' classid='clsid:A703D7FD-2572-46ED-A79E-BF049394A45F' CODEBASE='http://itraffic.ipohang.org/cctv_pop/player/player.cab#version=455,0,0,1'>"
      + "<param name='server_ip' value='61.43.42.5'>"
      + "<param name='server_port' value='8020'>"
      + "<param name='camera' value='" + this.gId + "'>"
      + "<param name='id' value='root'>"
      + "<param name='pass' value='router'>"
      + "<PARAM NAME='type' VALUE='embeded'>"
      + "</object>";
  };

  //천안 Z  
  this.cctvHTML_Z = function(){
    return "<iframe style='padding:0 0;' src=http://61.108.201.13/wall_view/viewer01.php?kind=Z&ip=" + this.gCctvIp + "&ch=" + this.gId +" width='" + this.gWidth + "' height='" + this.gHeight + "' name='VitCtrl'></iframe>";
  };

  //과천 a
  this.cctvHTML_Aa = function(){
    return "<iframe src='http://its.gccity.go.kr/realtime/CCTVView_Streaming.jsp?CCTVID=L06" + this.gCctvId.substring(this.gCctvId.length-2,this.gCctvId.length) + "&W=320&H=240' frameborder='0' width='320' height='240' scrolling='no'></iframe>";
  };

  //서울(지방경찰청) 분류코드 없음
  this.cctvHTML_Seoul = function(){
    return "<object id='mov' classid='clsid:D27CDB6E-AE6D-11cf-96B8-444553540000' codebase='http://download.macromedia.com/pub/shockwave/cabs/flash/swflash.cab#version=9,0,0,0' width='320' height='240'>"
        + "<param name='bgcolor' value='#000000' />"
        + "<param name='movie' value='http://www.utic.go.kr/contents/js/img/smpa_player.swf' />"
        + "<param name='allowfullscreen' value='true' />"
        + "<param name='allowscriptaccess' value='always' />"
        + "<param name='wmode' value='none' />"
        + "<param name='flashvars' value='file="+ this.gId +".stream&streamer=rtmp://61.108.209."+ this.gCctvIp +":1935/live&bufferlength=3&autostart=true&stretching=exactfit&fullscreen=true&image=http://www.utic.go.kr/contents/js/img/320240-5.gif&skin=http://www.utic.go.kr/contents/js/img/skin_black30live.swf&frontcolor=FFFFFF&lightcolor=00AEEF&backcolor=111111' />"
        + "<embed src='http://its.pyeongtaek.go.kr/js/player/player.swf' width='320' height='240'  name='movie' flashvars='file="+ this.gId +".stream&streamer=rtmp://61.108.209."+ this.gCctvIp +"/live/&controlbar=none&autostart=true&stretching=exactfit&duration=&image=play.png' style='border:0px solid #c5d6ff' type='application/x-shockwave-flash' pluginspage='http://www.macromedia.com/go/getflashplayer' />"
        + "</object>";

  };

  //한국도로공사 L 
  this.cctvHTML_Lx = function(){
    return "<div style='position:absolute; top:-100px; left:-27px;'>"
        + "<iframe width=370 height=380 frameborder=0 scrolling='no' src='http://www.roadplus.co.kr/cctvPlayer.do?op=cctvPlayer&cctvId=" + this.gCctvIp + "'>"
        + "</div>";
  };

  //대전 동영상 E
  this.cctvHTML_E = function(){
    var id = parseInt('15');
    var url = cctvObj.ID < 31 ? "mms://210.99.67.118:7500/"+cctvObj.ID : "mms://210.99.67.119:7500/"+cctvObj.ID;
    return "<object id=mmplay type=application/x-oleobject width='320' height='240' standby='Loading Windows Media Player components...' classid=CLSID:22d6f312-b0f6-11d0-94ab-0080c74c7e95>"
      + "<param name='FileName' value='" + url + "'>"
      + "<param name='ShowControls' value='0'>"
      + "<param name='ControlType' value='1'>"
      + "<param name='AutoStart' value='1'>"
      + "<param name='ShowDisplay' value='0'>"
      + "<param name='Enabled' value='ture'>"
      + "<param name='Volume' value='0'>"
      + "<param name='BufferingTime' value='1'>"
      + "<param name='PlayCount' value='1'>"
      + "<param name='EnableContextMenu' value='0'>"
      + "<param name='ShowGotoBar' value='0'>"
      + "<param name='ShowStatusBar' value='1'>"
      + "</object>";
  };

  //광주(전라도) 동영상 G //http://www.gjtic.go.kr/activex/AMC.cab
  this.cctvHTML_G = function(){
    return '<embed src="http://211.185.199.' + this.gCctvIp + ':132/mjpg/video.swf"></embed>';
  };

  //부산 동영상 I
  this.cctvHTML_I = function(){
  };

  //성남 b (정보없음)
  this.cctvHTML_Bb = function(){
  };

  //시흥c
  this.cctvHTML_Cc = function(){

    return "<object id='mov' width='" + this.gWidth + "' height='" + this.gHeight + "' classid='clsid:22D6F312-B0F6-11D0-94AB-0080C74C7E95'>"
      + "<param name='Filename' value='mms://27.101.133.164/" + this.gCctvIp + "' />"
      + "<param name='ClickToPlay' value='true' />"
      + "<param name='AutoSize' value='true' />"
      + "<param name='AutoStart' value='true' />"
      + "<param name='ShowControls' value='false' />"
      + "<param name='ShowAudioControls' value='false' />"
      + "<param name='ShowDisplay' value='false' />"
      + "<param name='ShowTracker' value='false' />"
      + "<param name='ShowStatusBar' value='false' />"
      + "<param name='EnableContextMenu' value='false' />"
      + "<param name='ShowPositionControls' value='false' />"
      + "<param name='ShowCaptioning' value='false' />"
      + "<param name='AutoRewind' value='true' />"
      + "<param name='Enabled' value='true' />"
      + "<param name='EnablePositionControls' value='true' />"
      + "<param name='EnableTracker' value='true' />"
      + "<param name='PlayCount' value='1' />"
      + "<param name='SendWarningEvents' value='true' />"
      + "<param name='SendErrorEvents' value='true' />"
      + "<param name='SendKeyboardEvents' value='false' />"
      + "<param name='SendMouseClickEvents' value='false' />"
      + "<param name='SendMouseMoveEvents' value='false' />"
      + "<param name='ShowGotoBar' value='false' />"
      + "<param name='TransparentAtStart' value='false' />"
      + "<param name='Volume' value='0' />"
      + "<param name='EnableContextMenu' value='false' />" 
      + "<param name='UIMode' value='none' />"
      + "</object>";
  };  
  //용인d
  this.cctvHTML_Dd = function(){    
    return "<object id=mmplay type=application/x-oleobject width='" + this.gWidth + "' height='" + this.gHeight + "' standby='Loading Windows Media Player components...' classid=CLSID:22d6f312-b0f6-11d0-94ab-0080c74c7e95>"
      + "<param name='FileName' value='mms://211.249.12.147/" + this.gCctvId + "'>"
        + "<param name='ShowControls' value='0'>"
        + "<param name='ControlType' value='1'>"
        + "<param name='AutoStart' value='1'>"        
        + "<param name='ShowDisplay' value='0'>"
        + "<param name='Enabled' value='ture'>"
        + "<param name='Volume' value='0'>"
        + "<param name='BufferingTime' value='1'>"
        + "<param name='PlayCount' value='1'>"
        + "<param name='EnableContextMenu' value='0'>"
        + "<param name='ShowGotoBar' value='0'>"
        + "<param name='ShowStatusBar' value='1'>"
        + "</object>";
  };

  this.cctvPlay_F = function(){
    try{
      if(this.gCh.length != 1){
        return;
      }
      var isNav, isIE, timer_id;
      isNav = (navigator.appName == 'Netscape') ? true : false;
      isIE = (navigator.appName.indexOf('Microsoft') != -1) ? true : false;
      var player = parent.document.getElementById("player");
      StartService(this.gCctvIp, this.gCh);

      function StartService(ip, ch){
        if(player){
          SetParameters(ch);
          player.Connect(ip, 8080);
        }else{
          window.alert('WebEye Plugin or Control not installed in this system');
        }
      }

      function SetParameters(ch){
        player.SetAuthInfo('guest', 'guest');
        if (isNav) player.SetVideoSource(ch);
        else if (isIE) player.VideoSource = ch;

        if (isNav) player.SetFrameRate('0');
        else if (isIE) player.FrameRate = 0;

        if (isNav) player.SetImageResolution('2');
        else if (isIE) player.ImgResolution='2';
        player.Play();
      }

      function StopService(){
        if (player){
          player.Stop();
          player.Disconnect();
        }
      }

      function ReadStatus(){
        if (player){
          self.status = player.GetStatusMsg();
        } 
      }

      function onUnLoad(){
        if (player){
          StopService();
          if (isIE) self.clearInterval(timer_id);
        } 
      }
    }catch(e){alert(err);}
  };

  //광주(전라) 동영상 G 
  this.cctvPlay_G = function(){   
    try{
      return;
      /*var player = parent.document.getElementById("mov");
        player.AutoRun = false;   //묻지 않는다. 단 [guest][]가 서버에 지정이 되어 있어야 한다.
        player.ContactAddress = '211.185.199.' + this.gCctvIp;
        player.DisplayMode = '0x00' + this.gId;  
        player.ShowControl = 0;  
        player.ConnectionSpeed = 6;      //SPEED는 반드시 확인을 해 주십시요.
        player.Connect(0);                      //0=UDP Mode, 1=TCP/IP Mode
        setTimeout('chSelect()',2000);

        function chSelect(){        
          if (this.gCh == 1) {
            player.SendCmdVideoOnOff(1,1);  
            player.SendCmdVideoOnOff(2,0);  
            player.SendCmdVideoOnOff(3,0);  
            player.SendCmdVideoOnOff(4,0);
          } else if (this.gCh == 2) {
            player.SendCmdVideoOnOff(1,0);  
            player.SendCmdVideoOnOff(2,1);  
            player.SendCmdVideoOnOff(3,0);  
            player.SendCmdVideoOnOff(4,0);
          } else if (this.gCh == 3) {
            player.SendCmdVideoOnOff(1,0);  
            player.SendCmdVideoOnOff(2,0);  
            player.SendCmdVideoOnOff(3,1);  
            player.SendCmdVideoOnOff(4,0);
          } else {
            player.SendCmdVideoOnOff(1,0);  
            player.SendCmdVideoOnOff(2,0);  
            player.SendCmdVideoOnOff(3,0);  
            player.SendCmdVideoOnOff(4,1);
          }
        }*/
    }catch(e){alert(err);}
  };

  //대구 동영상 H 
  this.cctvPlay_H = function(){   
    try{
      var player = parent.document.getElementById("mov");
      player.SetAuthInfo('guest', 'guest');
      player.VideoSource = this.gCh;
      player.FrameRate = 0;
      player.Connect(this.gCctvIp, 8080);
      player.play();
    }catch(e){alert(err);}
  };

  //제주 동영상 K
  this.cctvPlay_K = function(){
    try{
      var player = parent.document.getElementById("mov");
      player.AccessKey = this.gId;
      player.IP = this.gCctvIp;
      player.Port = 9400;
      player.Connect();
    }catch(e){alert(err);}
  };

  //원주 M
  this.cctvPlay_M = function(){
    try{
      var player = parent.document.getElementById("mov");
      player.SetAuthInfo('guest', 'itsguest');
      player.VideoSource = this.gCh;
      player.FrameRate = 0;
      player.Connect(this.gCctvIp, 8080);
      player.play();
    }catch(e){alert(err);}
  };

  //서울외곽순환고속도로 U
  this.cctvPlay_U = function(){
    try{
      var player = parent.document.getElementById("mov");
      player.StartStreaming();
    }catch(e){alert(err);}
  };

  //안양 X
  this.cctvPlay_X = function(){
    try{
      var player = parent.document.getElementById("mov");
      player.LocalConfig(9) ;
      var con = player.Connect('vsnm://' + this.gCctvIp + ':' + this.gPort + '/video1', 'admin', '1234');
      player.Play(con);
    }catch(e){alert(err);}
  };

  //대전 동영상 E
  this.cctvPlay_E = function(){
    try{
      player.ShowInfo=0; 
      player.SetPositionCam(1,'대전광역시');
      player.ContactAddress = '210.99.67.' + this.gCctvIp;
      player.DisplayMode = parseInt(this.gId);
      player.ShowControl = 0;
      player.ChangeChannel = 0;
      player.ConnectionSpeed = parseInt(this.gPasswd);
      player.Connect(0);  
    }catch(e){alert(err);}
  };
  
  if(callback){
    callback(this);
  }
};  
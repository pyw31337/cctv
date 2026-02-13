//챗봇 이벤트 추가
$('.chat-btn').on('click', function () {
    let chatBox = $('.chatbot-box');
    if(chatBox.css('display') === 'none'){
        chatBox.css('display', 'flex');
    }else{
        chatBox.css('display', 'none');
    }
});

$('.chatbot-close').on('click', function(){
    let chatBox = $('.chatbot-box');
    chatBox.css('display', 'none');
})

$('.chatbot-input input').on('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault(); // 줄바꿈 방지
        sendChat(); // 메시지 전송
    }
});

$('.send-btn').on('click', function(){
    sendChat();
});

const $box = $('.chatbot-box');
const $header = $('.chatbot-header');
let isDragging = false;
let offsetX = 0;
let offsetY = 0;
let hasStartedDragging = false;

$header.on('mousedown', function (e) {
    isDragging = true;
    hasStartedDragging = false; // 드래그 초기화
    $('body').css('user-select', 'none');
});

$(document).on('mousemove', function (e) {
    if (isDragging) {
        if (!hasStartedDragging) {
            // 첫 움직임 시점에서 offset 저장 + fixed 적용
            const boxOffset = $box.offset();

            offsetX = e.pageX - boxOffset.left;
            offsetY = e.pageY - boxOffset.top;

            $box.css({
                left: boxOffset.left + 'px',
                top: boxOffset.top + 'px',
                right: 'auto',
                bottom: 'auto',
                position: 'fixed',
            });

            hasStartedDragging = true;
        }

        const newLeft = e.pageX - offsetX;
        const newTop = e.pageY - offsetY;

        $box.css({ left: newLeft + 'px', top: newTop + 'px' });
    }
});

$(document).on('mouseup', function () {
    isDragging = false;
    hasStartedDragging = false;
    $('body').css('user-select', 'auto');
});


$(document).on('mousemove', function (e) {
    if (isDragging) {
        let newLeft = e.clientX - offsetX;
        let newTop = e.clientY - offsetY;

        $box.css({ left: newLeft + 'px', top: newTop + 'px' });
    }
});

$(document).on('mouseup', function () {
    isDragging = false;
    $('body').css('user-select', 'auto');
});

// 클로저를 이용한 데이터를 저장 함수
function fetchJsonData() {
    // 클로저 변수로 데이터를 저장할 변수를 선언합니다.
    let data = null;
    // 클로저 함수를 반환합니다.
    return function(url) {
        const headers = new Headers();
        headers.append('Content-Type', "application/json");

        // fetch를 이용하여 API에서 데이터를 가져옵니다.
        data = fetch(url, {
            method: "POST",
            headers: headers
        })
            .then(response => response.json()) // JSON 형식으로 변환합니다.
            .then(json => {
                data = json; // 데이터를 변수에 저장합니다.
                return json; // 데이터를 반환합니다.
            })
            .catch(error => console.error(error)); // 에러 처리합니다.
        return data;
    };
}
// fetchData 함수를 호출하여 데이터를 가져오는 함수를 생성합니다.
const postJsonData = fetchJsonData();

function fetchLoadJsonData() {
    // 클로저 변수로 데이터를 저장할 변수를 선언합니다.
    let data = null; // 클로저 변수로 데이터를 저장

    return async function (url) {
        const headers = new Headers();
        headers.append('Content-Type', "application/json");

        showLoadingBar(); // 로딩바 표시

        try {
            const response = await fetch(url, {
                method: "POST",
                headers: headers
            });
            const json = await response.json();
            data = json; // 데이터를 클로저 변수에 저장
            return json;
        } catch (error) {
            console.error("데이터 요청 오류:", error);
            throw error;
        } finally {
            hideLoadingBar(); // 요청 완료 후 로딩바 숨김
        }
    };
}
// fetchData 함수를 호출하여 데이터를 가져오는 함수를 생성합니다.
const postLoadJsonData = fetchLoadJsonData();

// FETCH 를 사용한 HTML Return 함수
function fetchHtmlData() {
    let data = null;

    return function(url) {
        const headers = new Headers();
        headers.append('Content-Type', "text/html");
        data = fetch(url, {
            method: "POST",
            headers: headers
        }).then(response => response.text()) // Response text 형식으로 변환합니다.
          .catch(error => console.error(error)); // 에러 처리합니다.
        return data;
    };
}
// fetchData 함수를 호출하여 데이터를 가져오는 함수를 생성합니다.
const postHtmlData = fetchHtmlData();

// FETCH 를 사용한 File Return 함수
function fetchFileData() {
    let data = null;

    return function(url) {
        let decodedFilename;
        const headers = new Headers();
        headers.append('Content-Type', "application/json");
        data = fetch(url, {
            method: "POST",
            headers: headers
        }).then((response) => {
            if (!response.ok) {
                throw Error(response.statusText)
            }
            const disposition = response.headers.get('Content-Disposition');
            const filename = disposition.match(/filename\*?=['"]?([^;\n"]*)['"]?/)[1];
            decodedFilename = decodeURIComponent(filename.replace(/\+/g, ' '));
            return response.blob()
        }).then((blob) => {
                if (blob != null) {
                    let url = window.URL.createObjectURL(blob)
                    let aTag = document.createElement('a')
                    aTag.href = url
                    aTag.download = decodedFilename
                    document.body.appendChild(aTag)
                    aTag.click()
                    aTag.remove()
                }
        }).catch((err) => {
                console.log(err)
        })
    };
}
// fetchData 함수를 호출하여 데이터를 가져오는 함수를 생성합니다.
const postFileData = fetchFileData();

function updateURLParameter(url, paramName, paramValue) {
    if(isInvalidURL(url)){
        url = window.location.protocol+"//"+window.location.host+url
    }
    // URL을 분석하기 위해 URL 객체 생성
    let urlObj = new URL(url);
    // URLSearchParams를 사용하여 쿼리 파라미터를 처리
    let params = urlObj.searchParams;
    if (paramValue === null || paramValue === undefined) {
        // 파라미터 값을 null이나 undefined로 전달하면 해당 파라미터를 제거
        params.delete(paramName);
    } else {
        // 파라미터 추가 또는 업데이트
        params.set(paramName, paramValue);
    }
    // 새로운 URL 반환
    return urlObj.toString();
}

/**
 * URL 객체를 생성하여 유효성 확인
 * @param string
 * @returns {boolean}
 */
function isInvalidURL(string) {
    try {
        new URL(string);
        return false;
    } catch (error) {
        return true;
    }
}

/**
 * 세션 스토리지 활용 유틸
 * @type {{removeItem: sessionStorageUtil.removeItem, clear: sessionStorageUtil.clear, hasItem: (function(*): boolean), getItem: ((function(*): (any|null|null|undefined))|*), setItem: sessionStorageUtil.setItem}}
 */
const sessionStorageUtil = {
    // 데이터 저장
    setItem: (key, value) => {
        try {
            const jsonValue = JSON.stringify(value); // 객체나 배열을 JSON 문자열로 변환
            sessionStorage.setItem(key, jsonValue);
        } catch (error) {
            console.error("Failed to set item in sessionStorage:", error);
        }
    },

    // 데이터 읽기
    getItem: (key) => {
        try {
            const jsonValue = sessionStorage.getItem(key);
            return jsonValue ? JSON.parse(jsonValue) : null; // JSON 문자열을 객체로 변환
        } catch (error) {
            console.error("Failed to get item from sessionStorage:", error);
            return null;
        }
    },

    // 데이터 삭제
    removeItem: (key) => {
        try {
            sessionStorage.removeItem(key);
        } catch (error) {
            console.error("Failed to remove item from sessionStorage:", error);
        }
    },

    // 모든 데이터 초기화
    clear: () => {
        try {
            sessionStorage.clear();
        } catch (error) {
            console.error("Failed to clear sessionStorage:", error);
        }
    },

    // 키 존재 여부 확인
    hasItem: (key) => {
        return sessionStorage.getItem(key) !== null;
    },
};


function fn_page_move(page){
    postData(page);
    $('#currentPageNo').html(page);
}

/**
 * 세션 업데이트
 * @param page
 * @param cnd
 * @param wrd
 */
function updateSession(page, cnd, wrd){
    sessionStorageUtil.clear();
    sessionStorageUtil.setItem('boardInfo', {pageIndex: page, searchCnd: cnd, searchWrd: wrd });
}

// 로딩바 표시 함수
function showLoadingBar() {
    let overlay = document.getElementById("loadingOverlay");

    // 오버레이(배경) 생성
    if (!overlay) {
        overlay = document.createElement("div");
        overlay.id = "loadingOverlay";
        overlay.style.position = "fixed";
        overlay.style.top = "0";
        overlay.style.left = "0";
        overlay.style.width = "100vw";
        overlay.style.height = "100vh";
        overlay.style.backgroundColor = "rgba(0, 0, 0, 0.5)"; // 반투명 배경
        overlay.style.display = "flex";
        overlay.style.justifyContent = "center";
        overlay.style.alignItems = "center";
        overlay.style.zIndex = "9999";
        overlay.style.pointerEvents = "auto"; // 클릭 막기
        document.body.appendChild(overlay);
    }

    let spinner = document.getElementById("loadingSpinner");

    // 스피너(로딩 애니메이션) 생성
    if (!spinner) {
        spinner = document.createElement("div");
        spinner.id = "loadingSpinner";
        spinner.style.width = "50px";
        spinner.style.height = "50px";
        spinner.style.border = "5px solid rgba(255, 255, 255, 0.3)";
        spinner.style.borderTop = "5px solid white";
        spinner.style.borderRadius = "50%";
        spinner.style.animation = "spin 1s linear infinite";
        overlay.appendChild(spinner);
    }

    overlay.style.display = "flex"; // 표시
}

// 로딩바 숨기기 함수
function hideLoadingBar() {
    let overlay = document.getElementById("loadingOverlay");
    if (overlay) {
        overlay.style.display = "none"; // 숨기기
    }
}

function escapeHtml(text) {
    if (text.startsWith('"') && text.endsWith('"')) {
        text = text.substring(1, text.length - 1);
    }

    // JSON 이스케이프 처리 복구
    text = text.replace(/\\"/g, '"').replace(/\\\\/g, '\\');

    // 줄바꿈
    text = text.replace(/\\n/g, '<br>');

    // XSS 방어: 위험한 태그 제거
    text = text.replace(/<script.*?>.*?<\/script>/gi, '');
    text = text.replace(/<\/?(iframe|object|embed|form|input|button|style|svg|link|meta)[^>]*?>/gi, '');
    text = text.replace(/\s(on\w+)=["']?[^"']*["']?/gi, ''); // onerror, onclick 등 제거
    text = text.replace(/javascript:/gi, '');

    // 마크다운 링크 [text](url)
    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
        '<a href="$2" target="_blank" style="color: blue; text-decoration: underline;">[$1]</a>'
    );

    // 괄호로 된 링크 (http...)
    text = text.replace(/\((https?:\/\/[^\s)]+)\)/g,
        '<a href="$1" target="_blank" style="color: blue; text-decoration: underline;">[바로가기]</a>'
    );

    // 일반 링크
    text = text.replace(/(?<!["'>(])\b(https?:\/\/[^\s<]+)/g,
        '<a href="$1" target="_blank" style="color: blue; text-decoration: underline;">[바로가기]</a>'
    );

    // 굵게 **텍스트**
    text = text.replace(/\*\*(.*?)\*\*/g,
        '<span style="font-weight: bold;">$1</span>'
    );

    return text;
}


// 챗봇 채팅 전달
function sendChat() {
    const input = $('.chatbot-input input');
    const sendBtn = $('.send-btn');
    const chatBox = $('.chat');
    const url = "/chatbot/getresult.do";
    const userMessage = input.val().trim();

    if (userMessage === '') return;

    input.prop('disabled', true).css('background', 'var(--c-gray-10)');
    sendBtn.prop('disabled', true);

    chatRequest(userMessage);

    let msgHist = [];

    $.each($('.chat-message p'), function(idx, item) {
        const text = $(item).text().trim().toString();  // 텍스트만 추출
        let messageObj = {};
        if (idx % 2 === 0) {
            messageObj = {
                role: 'user',
                content: text
            };
        } else {
            messageObj = {
                role: 'assistant',
                content: text
            };
        }
        msgHist.push(messageObj);  // 이제는 { role, content } 객체가 들어감
    });

    $.ajax({
        type: "POST",
        url: url,
        data: {message:JSON.stringify(msgHist)},
        success: function (res) {
            let result = '';
            try {
                result = JSON.parse(res)?.result;
            } catch (e) {
                console.error("JSON 파싱 오류:", e);
            }

            if (!result) {
                chatResponse("답변을 생성하는 과정에서 문제가 발생하였습니다.");
            } else {
                if(result === "fail25times"){
                    chatResponse("챗봇 이용한도에 도달하였습니다. (일 기준 접속자별 25건의 질문에만 응답합니다.)");
                }else{
                    chatResponse(result);
                }
            }
        },
        error: function (xhr, status, error) {
            console.error("서버 오류:", status, error);
            chatResponse("서버와의 통신 중 오류가 발생했습니다.");
        },
        complete: function () {
            input.val('').prop('disabled', false).css('background', 'none');
            sendBtn.prop('disabled', false);
        }
    });
}

function chatRequest(message) {
    const safeMessage = escapeHtml(message);
    $('.chat').append(`<div class="chat-message right"><p>${safeMessage}</p></div>`);
    scrollToBottom();
}

function chatResponse(message) {
    const safeMessage = escapeHtml(message);
    $('.chat').append(`
        <div class="chat-message left">
            <img src="/images/icthome/chatbot-pf.svg" alt="챗봇 프로필" class="chatbot-icon" />
            <p>${safeMessage}</p>
        </div>
    `);
    scrollToBottom();
}

function scrollToBottom() {
    const chat = $('.chat');
    chat.stop().animate({
        scrollTop: chat[0].scrollHeight
    }, 400);
}

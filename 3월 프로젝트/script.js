function calculate(){

let name = document.getElementById("name").value;

let weight = Number(document.getElementById("weight").value);

let exercise = Number(document.getElementById("exercise").value);

let coffee = Number(document.getElementById("coffee").value);

let weather = Number(document.getElementById("weather").value);


// 기본 수분
let base = weight * 30;

// 운동 추가
let exerciseWater = exercise * 300;

// 카페인 추가
let caffeineWater = coffee * 200;

// 날씨 보정
let weatherWater = 0;

if(weather >= 25 && weather < 30){
    weatherWater = 300;
}
else if(weather >= 30){
    weatherWater = 500;
}

// 총 섭취량
let total = base + exerciseWater + caffeineWater + weatherWater;


// 시간별 분배
let morning = Math.round(total * 0.3);
let lunch = Math.round(total * 0.4);
let dinner = Math.round(total * 0.3);


// 결과 출력
document.getElementById("total").innerText =
name + "님은 오늘 총 " + total + "ml의 물을 마시는 것이 좋습니다.";

document.getElementById("morning").innerText =
"아침 권장 섭취량 : " + morning + "ml";

document.getElementById("lunch").innerText =
"점심 권장 섭취량 : " + lunch + "ml";

document.getElementById("dinner").innerText =
"저녁 권장 섭취량 : " + dinner + "ml";

}

import numpy as np

perch_length = np.array([8.4, 13.7, 15.0, 16.2, 17.4, 18.0, 18.7, 19.0, 19.6, 20.0, 21.0,
       21.0, 21.0, 21.3, 22.0, 22.0, 22.0, 22.0, 22.0, 22.5, 22.5, 22.7,
       23.0, 23.5, 24.0, 24.0, 24.6, 25.0, 25.6, 26.5, 27.3, 27.5, 27.5,
       27.5, 28.0, 28.7, 30.0, 32.8, 34.5, 35.0, 36.5, 36.0, 37.0, 37.0,
       39.0, 39.0, 39.0, 40.0, 40.0, 40.0, 40.0, 42.0, 43.0, 43.0, 43.5,
       44.0])
perch_weight = np.array([5.9, 32.0, 40.0, 51.5, 70.0, 100.0, 78.0, 80.0, 85.0, 85.0, 110.0,
       115.0, 125.0, 130.0, 120.0, 120.0, 130.0, 135.0, 110.0, 130.0,
       150.0, 145.0, 150.0, 170.0, 225.0, 145.0, 188.0, 180.0, 197.0,
       218.0, 300.0, 260.0, 265.0, 250.0, 250.0, 300.0, 320.0, 514.0,
       556.0, 840.0, 685.0, 700.0, 700.0, 690.0, 900.0, 650.0, 820.0,
       850.0, 900.0, 1015.0, 820.0, 1100.0, 1000.0, 1100.0, 1000.0,
       1000.0])

from sklearn.model_selection import train_test_split

# 훈련 / 테스트 세트 분리, target 데이터를 weight안에 넣어놓는다.
train_input, test_input, train_target, test_target = train_test_split(perch_length, perch_weight, random_state=42)

# 2차원 배열로 재구성
train_input = train_input.reshape(-1, 1)
test_input = test_input.reshape(-1, 1)

from sklearn.neighbors import KNeighborsRegressor

knr = KNeighborsRegressor(n_neighbors=3)

# knn 회귀(knr) 모델 훈련
knr.fit(train_input, train_target)

print(knr.predict([[50]]))

import matplotlib.pyplot as plt

# 50cm 농이 이웃 구하기, [[]]는 2차원 배열의 형태 입력을 하기 위한 배열이다. [[50]]은 샘플 1개, 특성 1개를 뜻한다.(길이 50)
distances, indexes = knr.kneighbors([[50]])

# 산점도
plt.scatter(train_input, train_target)

# 이웃 샘플 다시 그리기
plt.scatter(train_input[indexes], train_target[indexes], marker='D')

# 50cm 농어 데이터
plt.scatter(50, 1033, marker='^')
plt.xlabel('length')
plt.ylabel('weight')
plt.show()

# 가장 가까운 이웃 3개의 인덱스 번호로 무게의 평균을 구해 출력하는 방식이다.
print(np.mean(train_target[indexes]))

# 100cm 농어
print(knr.predict([[100]]))

# 100cm 농어의 이웃 데이터셋 구하기
distances, indexes = knr.kneighbors([[100]])

# 훈련 세트 기반 산점도
plt.scatter(train_input, train_target)

# 이웃 샘플 마커 표시
plt.scatter(train_input[indexes], train_target[indexes], marker='D')
plt.scatter(100, 1033, marker='^')
plt.xlabel('length')
plt.ylabel('weight')
plt.show()

# 선형 회귀 모델 호출
from sklearn.linear_model import LinearRegression
lr = LinearRegression()

# 선형 회귀 모델 훈련
lr.fit(train_input, train_target)

# 50cm 농어 예측
print(lr.predict([[50]]))
# 예측값 : 1241.83860323

# coef_ : 가중치 weight (기울기), intercept_ : 편향 (y절편)
print(lr.coef_, lr.intercept_)

plt.scatter(train_input, train_target)

# 직선의 x축 최소,최대 규모 설정 [15, 50]
plt.plot([15, 50], [15*lr.coef_+lr.intercept_, 50*lr.coef_+lr.intercept_])

# 50cm 농어 데이터
plt.scatter(50, 1241.8, marker='^')
plt.xlabel('length')
plt.ylabel('weight')
plt.show()

# 모델에게 농어 무게 예측
print(lr.score(train_input, train_target))  # 훈련 세트
print(lr.score(test_input, test_target))    # 테스트 세트

# 넘파이를 이용하여 길이를 제곱하면 음수값이 사라진다. column_stack으로 배열을 2차원 배열로 만든다.
# 곡선형 선을 그을것이기 때문에 이차함수로 각 길이를 모두 제곱해주고 점을 찍어 곡선으로 만든다.
train_poly = np.column_stack((train_input ** 2, train_input))
test_poly = np.column_stack((test_input ** 2, test_input))

# 배열에는 [(길이)². (길이)]의 형식으로 넣는다.
print(train_poly.shape, test_poly.shape)
# 길이의 제곱, 길이를 배열에 넣는 이유는 길이 데이터가 없을 경우에 ax²+c에서 x의 계수가 없기 때문에
# 원점을 꼭짓점으로 하는 이차함수가 모두 그려진다. 그래서 더욱 다양한 그래프를 그리기 위해 x값에 계수를 붙여 꼭짓점의 위치가 다르게 한다.

# 새로운 선형 회귀 모델 생성
lr = LinearRegression()
lr.fit(train_poly, train_target)

# [길이², 길이] 예시 코드
print(lr.predict([[50**2, 50]]))

# 가중치와 y절편 출력 코드
print(lr.coef_, lr.intercept_)

# 2차함수 그래프 구현 코드
point = np.arange(15, 50)

plt.scatter(train_input, train_target)
plt.plot(point, 1.01*point**2 - 21.6*point + 116.05)

plt.scatter(50, 1574, marker='^')
plt.xlabel('length')
plt.ylabel('weight')
plt.show()

# [길이², 길이]를 사용하는 이유는 데이터가 곡선형이기 때문에 직선보다 곡선형인 2차 방정식으로 나타내기 위해서이다.
print(lr.score(train_poly, train_target))
print(lr.score(test_poly, test_target))
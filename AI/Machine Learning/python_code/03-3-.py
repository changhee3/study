# 판다스 호출
import pandas as pd
perch_full = pd.read_csv('https://bit.ly/perch_csv_data')
perch_full.head() # csv 파일에서 처음 5개의 행을 불러온다

# 넘파이 호출
import numpy as np
perch_weight = np.array([5.9, 32.0, 40.0, 51.5, 70.0, 100.0, 78.0, 80.0, 85.0, 85.0, 110.0,
       115.0, 125.0, 130.0, 120.0, 120.0, 130.0, 135.0, 110.0, 130.0,
       150.0, 145.0, 150.0, 170.0, 225.0, 145.0, 188.0, 180.0, 197.0,
       218.0, 300.0, 260.0, 265.0, 250.0, 250.0, 300.0, 320.0, 514.0,
       556.0, 840.0, 685.0, 700.0, 700.0, 690.0, 900.0, 650.0, 820.0,
       850.0, 900.0, 1015.0, 820.0, 1100.0, 1000.0, 1100.0, 1000.0,
       1000.0])

# 데이터셋 나누기
from sklearn.model_selection import train_test_split
train_input, test_input, train_target, test_target = train_test_split(perch_full, perch_weight, random_state=42)

# 변환기 클래스 선언
from sklearn.preprocessing import PolynomialFeatures

# PolynomialFeatures는 기존 변수들을 이용해서 거듭제곱이나 곱셈을 이용하여 새로운 변수를 자동으로 만들어주는 변환기이다.
poly = PolynomialFeatures()
poly.fit([[2, 3]])
print(poly.transform([[2, 3]]))
# [[2, 3]]은 2와 3의 거듭제곱과 곱셈으로 [[1. 2. 3. 4. 6. 9.]]를 생성한다.

# 1을 제외한 모든 조합을 출력한다.
poly = PolynomialFeatures(include_bias=False)
poly.fit([[2, 3]])
print(poly.transform([[2, 3]]))

# (42, 9)에서 9는 특성의 갯수를 의미한다.
# 특성이 늘어나는 경우 그래프는 커지지만 넘파이 배열에서는 값만 커진다.
poly = PolynomialFeatures(include_bias=False)
poly.fit(train_input)
train_poly = poly.transform(train_input)
print(train_poly.shape)

# 9개 특성의 이름을 확인하는 메서드 사용
poly.get_feature_names_out()

test_poly = poly.transform(test_input)

# 다중 회귀 모델 훈련하기
from sklearn.linear_model import LinearRegression
lr = LinearRegression()
lr.fit(train_poly, train_target)
print(lr.score(train_poly, train_target))

print(lr.score(test_poly, test_target))

# 최고 차수를 5로 늘려 만들어진 특성이 총 55개이다.
poly = PolynomialFeatures(degree=5, include_bias=False)
poly.fit(train_input)
train_poly = poly.transform(train_input)
test_poly = poly.transform(test_input)
print(train_poly.shape)

lr.fit(train_poly, train_target)
print(lr.score(train_poly, train_target))

print(lr.score(test_poly, test_target))
# 특성의 개수가 많아지면 선형모델은 강력해지지만 훈련세트에 과대적합 되므로 테스트 세트에 대한 취약점을 드러낸다.
# 만약 파라미터를 훈련세트를 학습하기 위한 손잡이라고 가정한다면 테스트 세트를 위한 손잡이가 없는것이다.

from sklearn.preprocessing import StandardScaler
ss = StandardScaler()
ss.fit(train_poly)
train_scaled = ss.transform(train_poly)
test_scaled = ss.transform(test_poly)


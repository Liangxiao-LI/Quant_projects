#!/usr/bin/env python3

from skfolio.datasets import load_sp500_dataset
from skfolio.optimization import DistributionallyRobustCVaR
from skfolio.preprocessing import prices_to_returns

# Load recent historical prices and convert them to returns
prices = load_sp500_dataset()["2020":]
X = prices_to_returns(prices)

# Distributionally robust CVaR optimization
model = DistributionallyRobustCVaR(wasserstein_ball_radius=0.01)
model.fit(X)
print("Distributionally Robust CVaR weights, radius=0.01:")
print(model.weights_)

# Increasing the radius makes the model more conservative
model = DistributionallyRobustCVaR(wasserstein_ball_radius=0.10)
model.fit(X)
print("\nDistributionally Robust CVaR weights, radius=0.10:")
print(model.weights_)

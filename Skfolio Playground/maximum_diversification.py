#!/usr/bin/env python3

from skfolio.datasets import load_sp500_dataset
from skfolio.optimization import MaximumDiversification
from skfolio.preprocessing import prices_to_returns

# Load historical prices and convert them to returns
prices = load_sp500_dataset()
X = prices_to_returns(prices)

# Maximum diversification optimization
model = MaximumDiversification()
model.fit(X)
print("Maximum Diversification weights:")
print(model.weights_)

portfolio = model.predict(X)
print("\nPortfolio diversification:")
print(portfolio.diversification)

# Maximum diversification with an upper weight constraint
model = MaximumDiversification(max_weights=0.20)
model.fit(X)
print("\nMaximum Diversification weights, max_weights=0.20:")
print(model.weights_)

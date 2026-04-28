#!/usr/bin/env python3

from skfolio import RiskMeasure
from skfolio.datasets import load_sp500_dataset
from skfolio.optimization import MeanRisk, ObjectiveFunction
from skfolio.preprocessing import prices_to_returns

# Load historical prices and convert them to returns
prices = load_sp500_dataset()
X = prices_to_returns(prices)

# Minimum variance optimization
model = MeanRisk(risk_measure=RiskMeasure.VARIANCE)
model.fit(X)
print("Minimum Variance weights:")
print(model.weights_)

# Maximum Sharpe Ratio optimization
model = MeanRisk(
    objective_function=ObjectiveFunction.MAXIMIZE_RATIO,
    risk_measure=RiskMeasure.STANDARD_DEVIATION,
)
model.fit(X)
print("\nMaximum Sharpe Ratio weights:")
print(model.weights_)

# Minimum CVaR optimization with weight and linear constraints
model = MeanRisk(
    risk_measure=RiskMeasure.CVAR,
    max_weights=0.20,
    linear_constraints=["AMD <= 0.10", "BAC + JPM >= 0.15"],
)
model.fit(X)
print("\nMinimum CVaR weights:")
print(model.weights_)

# Compute portfolios along the mean-variance efficient frontier
model = MeanRisk(
    risk_measure=RiskMeasure.VARIANCE,
    efficient_frontier_size=10,
)
model.fit(X)
print("\nEfficient Frontier weights shape:")
print(model.weights_.shape)

population = model.predict(X)
print("\nPopulation:")
print(population)
#!/usr/bin/env python3

from skfolio import RiskMeasure
from skfolio.datasets import load_sp500_dataset
from skfolio.optimization import RiskBudgeting
from skfolio.preprocessing import prices_to_returns

# Load historical prices and convert them to returns
prices = load_sp500_dataset()
X = prices_to_returns(prices)

# Variance risk parity optimization
model = RiskBudgeting(risk_measure=RiskMeasure.VARIANCE)
model.fit(X)
print("Variance Risk Budgeting weights:")
print(model.weights_)

# CVaR risk budgeting with custom asset budgets
risk_budget = {asset: 1.0 for asset in X.columns}
risk_budget["AAPL"] = 1.5
risk_budget["GE"] = 0.2
risk_budget["JPM"] = 0.2
model = RiskBudgeting(
    risk_measure=RiskMeasure.CVAR,
    risk_budget=risk_budget,
)
model.fit(X)
print("\nCVaR Risk Budgeting weights:")
print(model.weights_)

portfolio = model.predict(X)
print("\nPortfolio CVaR:")
print(portfolio.cvar)

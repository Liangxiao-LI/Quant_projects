#!/usr/bin/env python3

from skfolio import RiskMeasure
from skfolio.datasets import load_sp500_dataset
from skfolio.optimization import (
    MeanRisk,
    NestedClustersOptimization,
    ObjectiveFunction,
    RiskBudgeting,
)
from skfolio.preprocessing import prices_to_returns

# Load historical prices and convert them to returns
prices = load_sp500_dataset()
X = prices_to_returns(prices)

# Maximize the Sharpe Ratio inside clusters and allocate risk across clusters
inner_estimator = MeanRisk(
    objective_function=ObjectiveFunction.MAXIMIZE_RATIO,
    risk_measure=RiskMeasure.STANDARD_DEVIATION,
)
outer_estimator = RiskBudgeting(risk_measure=RiskMeasure.CVAR)
model = NestedClustersOptimization(
    inner_estimator=inner_estimator,
    outer_estimator=outer_estimator,
)
model.fit(X)
print("Nested Clusters Optimization weights:")
print(model.weights_)
print("\nCluster labels:")
print(model.clustering_estimator_.labels_)

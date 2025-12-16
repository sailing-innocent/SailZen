# -*- coding: utf-8 -*-
# @file regression.py
# @brief Regression analysis utilities
# @author sailing-innocent
# @date 2025-06-09
# @version 1.0
# ---------------------------------
import numpy as np


# Linear Regression return estimated k, b
def linear_regression_1d(x: np.array, y: np.array):
    # Linear Regression with MSE Loss
    # Returns parameters for y = kx + b

    n = len(x)
    if n != len(y):
        raise ValueError("x and y arrays must have the same length")

    if n < 2:
        raise ValueError("Need at least 2 data points for linear regression")

    # Calculate means
    x_mean = np.mean(x)
    y_mean = np.mean(y)

    # Calculate slope (k) using least squares formula
    numerator = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sum((x - x_mean) ** 2)

    if denominator == 0:
        raise ValueError("Cannot perform regression: all x values are identical")

    k = numerator / denominator

    # Calculate intercept (b)
    b = y_mean - k * x_mean

    return k, b

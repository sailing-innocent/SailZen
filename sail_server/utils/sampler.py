# -*- coding: utf-8 -*-
# @file sampler.py
# @brief The Sampler class
# @author sailing-innocent
# @date 2025-04-27
# @version 1.0
# ---------------------------------

from typing import List, Tuple, Dict, Any


class TimeValueSampler:
    """
    A class to sample time and value pairs.
    """

    def __init__(self, get_time_value_func, time_reqs: List[int], influence: int = 0):
        """
        Initialize the TimeValueSampler with time requirements and influence.

        :param time_reqs: List of time requirements.
        :param influence: Influence value (default is 0).
        """
        self.time_reqs = time_reqs
        self.influence = influence
        self.time_values: List[Tuple[int, int]] = get_time_value_func()
        # assume time_reqs and time_values are sorted

    def gaussian_kernel(self, x: float, mu: float, sigma: float) -> float:
        """
        Gaussian kernel function.

        :param x: The input value.
        :param mu: The mean of the Gaussian distribution.
        :param sigma: The standard deviation of the Gaussian distribution.
        :return: The value of the Gaussian kernel at x.
        """
        return (1 / (sigma * (2 * 3.141592653589793) ** 0.5)) * (
            2.718281828459045 ** (-0.5 * ((x - mu) / sigma) ** 2)
        )

    def sample(self) -> List[Tuple[int, int]]:
        """
        Sample the time and value pairs based on the time requirements.

        :return: List of sampled time and value pairs.
        - SPH Sampling:
            - for sorted samples, calculate distance for each req and push into stack
            - for each req, calculate value in stack, if stack empty, mark it
        - Near Interpolation
            - for each empty-stack req, calculate by near interpolation
            - find the first empty-stack req
                - if first (unlikely) use the right value
            - find the first non-empty-stack req
                - if last no (unlikely) use the left value
            - if first and last, use the average of left and right values
        """

        # Initialize the stack with the first time value pair
        req_stack = [[] for _ in self.time_reqs]
        res = [0 for _ in self.time_reqs]
        N_rq = len(self.time_reqs)
        N_tv = len(self.time_values)

        i_tv = 0
        i_rq = 0
        while i_tv < N_tv and i_rq < N_rq:
            # print(f"i_tv: {i_tv}, i_rq: {i_rq}")
            tv_time, tv_value = self.time_values[i_tv]
            rq_time = self.time_reqs[i_rq]
            sigma = self.influence
            distance = (rq_time - tv_time) / sigma

            # print(f"tv_time: {tv_time}, rq_time: {rq_time}, distance: {distance}")

            if distance < -1:
                pass
            elif distance < 1:
                # Calculate the Gaussian kernel value
                d = self.gaussian_kernel(distance, 0, sigma)
                req_stack[i_rq].append((d, tv_value))
            else:
                i_rq = N_rq - 1  # Finalize the time-value pair for this stack

            # for all request, iterate the time-value source
            i_rq += 1
            if i_rq >= N_rq:
                i_rq = 0
                i_tv += 1

        # print(req_stack)
        # SPH Sampling
        for i_rq in range(N_rq):
            if len(req_stack[i_rq]) == 0:
                # No time-value pair found for this request
                continue

            # Calculate the value for this request based on the stack
            total_value, total_weight = 0, 0
            for d, tv_value in req_stack[i_rq]:
                total_value += d * tv_value
                total_weight += d

            res[i_rq] = total_value / total_weight

        # Near Interpolation for empty stacks
        for i_rq in range(N_rq):
            if len(req_stack[i_rq]) == 0:
                # Find the first non-empty stack to interpolate
                left_value = None
                right_value = None

                # Find the left value
                for j in range(i_rq - 1, -1, -1):
                    if len(req_stack[j]) > 0:
                        left_value = res[j]
                        break

                # Find the right value
                for j in range(i_rq + 1, N_rq):
                    if len(req_stack[j]) > 0:
                        right_value = res[j]
                        break

                # Interpolate based on the found values
                if left_value is not None and right_value is not None:
                    res[i_rq] = (left_value + right_value) / 2
                elif left_value is not None:
                    res[i_rq] = left_value
                elif right_value is not None:
                    res[i_rq] = right_value
                else:
                    # If no left or right value, set to 0 or some default value
                    res[i_rq] = 0

        return res


import unittest


class TestTimeValueSampler(unittest.TestCase):
    def setUp(self):
        # Common setup for tests
        self.time_reqs = [0, 10, 20, 30, 40, 50, 60, 100]
        self.influence = 6
        self.mock_time_values = [
            (15, 100),
            (24, 200),
            (31, 220),
            (62, 300),
            (75, 400),
            (80, 500),
        ]
        self.get_time_value_func = lambda: self.mock_time_values

    def test_initialization(self):
        """Test that the TimeValueSampler initializes with correct attributes"""
        sampler = TimeValueSampler(
            self.get_time_value_func, self.time_reqs, self.influence
        )

        self.assertEqual(sampler.time_reqs, self.time_reqs)
        self.assertEqual(sampler.influence, self.influence)
        self.assertEqual(sampler.time_values, self.mock_time_values)

        res = sampler.sample()
        print(res)


if __name__ == "__main__":
    unittest.main()

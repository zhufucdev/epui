from typing import *


def is_inside(parent: Tuple[float, float], child: Tuple[float, float]):
    return child[0] <= parent[0] and child[1] <= parent[1]


def is_strictly_inside(parent: Tuple[float, float], child: Tuple[float, float]):
    return child[0] < parent[0] and child[1] < parent[1]


def subtract(vector: Tuple[float, float], option: Tuple[float, float]):
    return vector[0] - option[0], vector[1] - option[1]


def plus(vector: Tuple[float, float], option: Tuple[float, float]):
    return vector[0] + option[0], vector[1] + option[1]


def multiply(vector: Tuple[float, float], factor: float):
    return vector[0] * factor, vector[1] * factor


def is_positive(vector: Tuple[float, float]):
    return vector[0] > 0 and vector[1] > 0


def int_vector(vector: Tuple[float, float]):
    return int(vector[0]), int(vector[1])

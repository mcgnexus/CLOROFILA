"""Regresion Ridge (minimos cuadrados regularizados) con numpy puro.

Modelo lineal: cab = w0 + w·x con x = canales estandarizados.
Solucion cerrada: w = (X'X + λI)^-1 X'y (sin regularizar el sesgo).
"""
import numpy as np


def ajustar_ridge(X: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
    """Ajusta Ridge y devuelve el vector [sesgo, w1..wp]."""
    n, p = X.shape
    A = X.T @ X + lam * np.eye(p)
    return np.linalg.solve(A, X.T @ y)


def predecir(X: np.ndarray, coef: np.ndarray) -> np.ndarray:
    """Predice con coeficientes [sesgo, w1..wp] (X ya con columna de unos)."""
    return X @ coef


def con_sesgo(X: np.ndarray) -> np.ndarray:
    """Anade columna de unos para el termino independiente."""
    return np.column_stack([np.ones(len(X)), X])


def mae(y: np.ndarray, p: np.ndarray) -> float:
    """Error absoluto medio."""
    return float(np.mean(np.abs(y - p)))


def rmse(y: np.ndarray, p: np.ndarray) -> float:
    """Raiz del error cuadratico medio."""
    return float(np.sqrt(np.mean((y - p) ** 2)))

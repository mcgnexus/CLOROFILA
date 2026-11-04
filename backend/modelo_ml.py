"""Inferencia del modelo ML de Cab (carga el .npz de entrenar_cab.py).

Uso futuro: exponer la estimacion via POST /api/cab en main.py.
"""
from pathlib import Path

import numpy as np


def cargar_modelo(ruta: str | Path) -> dict:
    """Carga pesos y estadisticos de estandarizacion."""
    z = np.load(ruta, allow_pickle=True)
    return {"sesgo": float(z["sesgo"]), "pesos": np.array(z["pesos"]),
            "media": np.array(z["media"]), "desv": np.array(z["desv"]),
            "columnas": [str(c) for c in z["columnas"]]}


def predecir_cab(modelo: dict, canales: dict) -> float:
    """Estima Cab (µg/cm2) a partir de un dict {canal: cuentas}."""
    x = np.array([float(canales[c]) for c in modelo["columnas"]])
    xs = (x - modelo["media"]) / modelo["desv"]
    return float(modelo["sesgo"] + xs @ modelo["pesos"])

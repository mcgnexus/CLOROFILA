"""PROSPECT-D oficial para el pipeline ML (adapter delgado).

Delega en `prospect_oficial.prospect_referencia` (matematicas oficiales
contrastadas bit a bit contra prosail 2.0.5 + tablas oficiales
verificadas por hash). Mantiene la API anterior para no romper
`dataset_sintetico.py`, `entrenar_cab.py` ni `modelo_ml.py`.

El gemelo heuristico del dashboard (`twin_model.py`) no se toca:
sigue siendo la demo rapida del dashboard, documentada como tal.
"""
import numpy as np

from prospect_oficial.carga_tablas import LAM
from prospect_oficial.prospect_referencia import prospect_d as _oficial
from twin_model import (
    FACTOR_CALIBRACION, LONGITUDES_ONDA, MODOS_VALIDOS, ORDEN_CANALES,
    RESPUESTA_CANAL,
)

__all__ = ["prospect_d", "predecir_canales_prospect",
           "canales_a_reflectancia", "LONGITUDES", "EXTRAS_POR_DEFECTO"]

# Parametros PROSPECT-D secundarios fijos para la demo (dentro del rango
# de entrenamiento del modelo ML: car U(2,16), cant U(0,2), cm U(0.003,0.012)).
# Gemelo y simulador usan los mismos para que la comparacion sea directa.
EXTRAS_POR_DEFECTO = {"car": 8.0, "cant": 1.0, "cbrown": 0.0, "cm": 0.005}


def prospect_d(cab: float, car: float = 8.0, cant: float = 1.0,
               cbrown: float = 0.0, cw: float = 0.015, cm: float = 0.005,
               n: float = 1.5) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """PROSPECT-D oficial: (longitudes 400-2500 nm, R, T) en [0,1].

    Args:
        cab: clorofila a+b (µg/cm2). car: carotenoides (µg/cm2).
        cant: antocianinas (µg/cm2). cbrown: marrones (0-1).
        cw: agua (cm). cm: materia seca (g/cm2). n: estructura.
    """
    return _oficial(n, cab, car, cbrown, cw, cm, cant)


def predecir_canales_prospect(cab: float, cw: float, n: float = 1.5,
                              modo: str = "reflectancia", car: float = 8.0,
                              cant: float = 1.0, cbrown: float = 0.0,
                              cm: float = 0.005) -> dict:
    """Predice los 10 canales del AS7341 con PROSPECT-D oficial (cuentas).

    Usa la misma geometria de canales y factor de calibracion que el
    gemelo heuristico para que ambos sean comparables.
    """
    if modo not in MODOS_VALIDOS:
        raise ValueError(f"modo debe ser uno de {MODOS_VALIDOS}")
    _, r, t = prospect_d(cab, car, cant, cbrown, cw, cm, n)
    espectro = r if modo == "reflectancia" else t
    if not np.all(np.isfinite(espectro)):
        # Falla en voz alta: un NaN/inf aqui indicaria parametros fuera
        # del dominio fisico o un error numerico, no una medida valida.
        raise ValueError("espectro PROSPECT-D no finito para "
                         f"(cab={cab}, cw={cw}, n={n}, modo={modo})")
    pred = {}
    for canal in ORDEN_CANALES:
        if canal == "Clear":
            continue
        centro, sigma = RESPUESTA_CANAL[canal]
        idx = np.where(np.abs(LAM - centro) <= 3 * sigma)[0]
        peso = np.exp(-(((LAM[idx] - centro) / sigma) ** 2) / 2.0)
        valor = float(np.sum(espectro[idx] * peso) / np.sum(peso))
        pred[canal] = max(0, int(round(valor * FACTOR_CALIBRACION)))
    media = sum(pred.values()) / len(pred)
    pred["Clear"] = max(0, int(round(media * 1.8)))
    return {c: pred[c] for c in ORDEN_CANALES}


def canales_a_reflectancia(canales: dict) -> dict:
    """Convierte cuentas a fraccion 0-1 (inversa del factor de calibracion)."""
    return {c: canales[c] / FACTOR_CALIBRACION for c in ORDEN_CANALES}


# Re-exportado para conveniencia (misma geometria que el gemelo).
LONGITUDES = LONGITUDES_ONDA

"""Modelo PROSPECT-D de optica foliar (implementacion propia del formalismo).

Formalismo real de PROSPECT (Jacquemoud & Baret 1990; Feret et al. 2017):
hoja como apilamiento de N capas elementales identicas, interfaces con
reflexion de Fresnel promediada para luz difusa, transmitancia interna
de la capa con la solucion exacta de Allen et al. y combinacion de
capas con las ecuaciones de Stokes.

Parametros (convenio PROSPECT-D):
  n      : estructura (1.0 fina - 2.5 gruesa), admite fraccionarios
  cab    : clorofila a+b (µg/cm2)
  car    : carotenoides (µg/cm2)
  cant   : antocianinas (µg/cm2)
  cbrown : pigmentos marrones (0-1)
  cw     : agua, espesor equivalente (cm)
  cm     : materia seca (g/cm2)

Los coeficientes de absorcion vienen de prospect_datos.py (aproximados
de trabajo; ver advertencia en ese modulo).
"""
import math

import numpy as np

from prospect_datos import (
    CAB_MAX, CAB_MIN,
    CANT_MAX, CANT_MIN, CAR_MAX, CAR_MIN,
    CBROWN_MAX, CBROWN_MIN, CM_MAX, CM_MIN, CW_MAX, CW_MIN,
    FUENTE_COEFICIENTES, KAB, KANT, KBROWN, KCAR, KM, KW,
    LAM, N_MAX, N_MIN, N_REFRACTIVO,
)
from twin_model import (
    FACTOR_CALIBRACION, LONGITUDES_ONDA, MODOS_VALIDOS, ORDEN_CANALES,
    RESPUESTA_CANAL,
)

EULER = 0.5772156649015329  # constante de Euler-Mascheroni

__all__ = ["prospect_d", "predecir_canales_prospect", "exp1_vec",
           "FUENTE_COEFICIENTES"]


def exp1_vec(x: np.ndarray) -> np.ndarray:
    """Integral exponencial E1(x) para x > 0, vectorizada (sin scipy).

    Serie para x <= 1 y fraccion continua de Lentz para x > 1
    ( Numerical Recipes, precision ~1e-12 ).
    """
    x = np.asarray(x, dtype=float)
    out = np.zeros_like(x)
    peq = (x > 0) & (x <= 1.0)
    if np.any(peq):
        xs = x[peq]
        # E1 = -ln(x) - γ - Σ (-x)^n / (n·n!)
        termino = -xs.copy()  # n = 1: (-x)^1 / 1
        suma = termino.copy()
        for n in range(2, 60):
            termino *= -xs / n
            inc = termino / n
            suma += inc
            if np.all(np.abs(inc) < 1e-14):
                break
        out[peq] = -np.log(xs) - EULER - suma
    gra = x > 1.0
    if np.any(gra):
        # Fraccion continua de Lentz (Numerical Recipes): E1 = h·e^-x.
        xg = x[gra]
        tiny = 1e-300
        b = xg + 1.0
        c = np.full_like(xg, 1.0 / tiny)
        d = 1.0 / b
        h = d.copy()
        for i in range(1, 200):
            a = -i * i
            b = b + 2.0
            d = a * d + b
            d = np.where(np.abs(d) < tiny, tiny, d)
            c = b + a / c
            c = np.where(np.abs(c) < tiny, tiny, c)
            d = 1.0 / d
            delta = c * d
            h = h * delta
            if np.all(np.abs(delta - 1.0) < 1e-12):
                break
        out[gra] = h * np.exp(-xg)
    return out


def _fresnel(n1: np.ndarray, n2: np.ndarray, cos1: float) -> np.ndarray:
    """Reflectancia de Fresnel no polarizada (R=1 si hay reflexion total)."""
    sin1_2 = max(0.0, 1.0 - cos1 * cos1)
    sin2_2 = (n1 / n2) ** 2 * sin1_2
    refl_total = sin2_2 > 1.0
    sin2_2 = np.minimum(sin2_2, 1.0)
    cos2 = np.sqrt(1.0 - sin2_2)
    rs = ((n1 * cos1 - n2 * cos2) / (n1 * cos1 + n2 * cos2)) ** 2
    rp = ((n1 * cos2 - n2 * cos1) / (n1 * cos2 + n2 * cos1)) ** 2
    r = 0.5 * (rs + rp)
    return np.where(refl_total, 1.0, r)


def _interfaces(n: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Reflectancias medias difusas externa (r12) e interna (r21).

    Promedia Fresnel sobre angulos de incidencia con peso sen·cos
    (malla fina de 0.25°; la rama interna incluye reflexion total).
    """
    ang = np.deg2rad(np.arange(0.0, 90.0 + 0.25, 0.25))
    cos1 = np.cos(ang)
    peso = 2.0 * np.sin(ang) * cos1
    peso /= peso.sum()
    unos = np.ones_like(n)
    r12 = sum(p * _fresnel(unos, n, c) for p, c in zip(peso, cos1))
    r21 = sum(p * _fresnel(n, unos, c) for p, c in zip(peso, cos1))
    return r12, r21


# Interfaces precalculadas (solo dependen del indice de refraccion).
_R12, _R21 = _interfaces(N_REFRACTIVO)


def _limitar(x: float, lo: float, hi: float) -> float:
    """Recorta un parametro a su rango de validez."""
    return max(lo, min(hi, x))


def prospect_d(cab: float, car: float = 8.0, cant: float = 1.0,
               cbrown: float = 0.0, cw: float = 0.015, cm: float = 0.005,
               n: float = 1.5) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ejecuta PROSPECT-D y devuelve (longitudes, R, T).

    Args:
        cab: clorofila a+b (µg/cm2). car: carotenoides (µg/cm2).
        cant: antocianinas (µg/cm2). cbrown: marrones (0-1).
        cw: agua (cm). cm: materia seca (g/cm2). n: estructura.

    Returns:
        Tupla (LAM, R, T) con R, T en [0,1] y R + T <= 1 garantizado.
    """
    n = _limitar(n, N_MIN, N_MAX)
    cab = _limitar(cab, CAB_MIN, CAB_MAX)
    car = _limitar(car, CAR_MIN, CAR_MAX)
    cant = _limitar(cant, CANT_MIN, CANT_MAX)
    cbrown = _limitar(cbrown, CBROWN_MIN, CBROWN_MAX)
    cw = _limitar(cw, CW_MIN, CW_MAX)
    cm = _limitar(cm, CM_MIN, CM_MAX)

    # Absorcion de la capa elemental (pigmentos diluidos en N capas).
    k = (cab * KAB + car * KCAR + cant * KANT + cbrown * KBROWN
         + cw * KW + cm * KM) / n

    # Transmitancia interna exacta de la capa (Allen et al.).
    tau = np.ones_like(k)
    pos = k > 0
    kk = k[pos]
    tau[pos] = (1.0 - kk) * np.exp(-kk) + kk * kk * exp1_vec(kk)

    # Una capa compacta (Stokes) con las interfaces precalculadas.
    t12, t21 = 1.0 - _R12, 1.0 - _R21
    den = 1.0 - _R21 * _R21 * tau * tau
    den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    r1 = _R12 + t12 * t21 * _R21 * tau * tau / den
    t1 = t12 * t21 * tau / den

    # Apilado de m = floor(n) capas identicas (adding).
    m = max(1, int(math.floor(n)))
    r, t = r1.copy(), t1.copy()
    for _ in range(m - 1):
        d = 1.0 - r1 * r
        d = np.where(np.abs(d) < 1e-12, 1e-12, d)
        r = r1 + t1 * r * t1 / d
        t = t1 * t / d

    # Parte fraccionaria de N por interpolacion lineal (conserva energia).
    frac = n - m
    if frac > 1e-9:
        d = 1.0 - r1 * r
        d = np.where(np.abs(d) < 1e-12, 1e-12, d)
        r_mas = r1 + t1 * r * t1 / d
        t_mas = t1 * t / d
        r = r + frac * (r_mas - r)
        t = t + frac * (t_mas - t)

    # Seguridad numerica final (la fisica ya garantiza R + T <= 1).
    r = np.clip(r, 0.0, 1.0)
    t = np.clip(t, 0.0, 1.0)
    return LAM.copy(), r, t


def predecir_canales_prospect(cab: float, cw: float, n: float = 1.5,
                              modo: str = "reflectancia", car: float = 8.0,
                              cant: float = 1.0, cbrown: float = 0.0,
                              cm: float = 0.005) -> dict:
    """Predice los 10 canales del AS7341 con PROSPECT-D (cuentas ADC).

    Usa la misma geometria de canales y factor de calibracion que el
    gemelo heuristico para que ambos sean comparables.
    """
    if modo not in MODOS_VALIDOS:
        raise ValueError(f"modo debe ser uno de {MODOS_VALIDOS}")
    _, r, t = prospect_d(cab, car, cant, cbrown, cw, cm, n)
    espectro = r if modo == "reflectancia" else t
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

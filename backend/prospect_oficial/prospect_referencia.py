"""PROSPECT-D de referencia: matematicas oficiales con tablas oficiales.

Implementa las ecuaciones publicadas de PROSPECT-D (Jacquemoud & Baret
1990; Feret et al. 2017) siguiendo la estructura de la implementacion de
referencia `prosail` 2.0.5 (J. Gomez-Dans, GPLv3):
  - `calctav`: transmitancia media de interfaz (Stern 1964; Allen 1973).
  - `refl_trans_one_layer`: una capa compacta (Allen et al. 1969).
  - Apilado de N capas (real) con las ecuaciones de Stokes (1862).

Usa las tablas oficiales `prospect_d_spectra.txt` (indice de refraccion
y coeficientes especificos de absorcion). Ver PROCEDENCIA.md.

Diferencias con el antiguo `prospect.py` (heuristico, eliminado):
  - Interfaces fisicas en vez de promediado numerico propio.
  - N fraccionario exacto (Stokes) en vez de interpolacion.
  - Coeficientes oficiales en vez de gaussianas inventadas.
"""
import numpy as np

from prospect_oficial.carga_tablas import (
    KAB, KCAR, KANT, KBROWN, KM, KW, LAM, NR,
)

__all__ = ["prospect_d", "calctav", "refl_trans_one_layer"]


def calctav(alpha_deg: float, nr: np.ndarray) -> np.ndarray:
    """Transmitancia media difusa de la interfaz (Stern 1964, Allen 1973).

    Args:
        alpha_deg: angulo maximo de incidencia (grados). La referencia usa
            40 para la cara superior iluminada y 90 para las interfaces
            internas difusas.
        nr: indice de refraccion por longitud de onda.

    Returns:
        Transmitancia media (array).
    """
    n2 = nr * nr
    npx = n2 + 1.0
    nm = n2 - 1.0
    a = (nr + 1.0) * (nr + 1.0) / 2.0
    k = -(n2 - 1.0) * (n2 - 1.0) / 4.0
    sa = np.sin(np.deg2rad(alpha_deg))

    if alpha_deg != 90:
        b1 = np.sqrt((sa * sa - npx / 2) * (sa * sa - npx / 2) + k)
    else:
        b1 = 0.0
    b2 = sa * sa - npx / 2
    b = b1 - b2
    b3 = b ** 3
    a3 = a ** 3
    ts = (k ** 2 / (6 * b3) + k / b - b / 2) - (
        k ** 2.0 / (6 * a3) + k / a - a / 2)

    tp1 = -2 * n2 * (b - a) / (npx ** 2)
    tp2 = -2 * n2 * npx * np.log(b / a) / (nm ** 2)
    tp3 = n2 * (1 / b - 1 / a) / 2
    tp4 = (16 * n2 ** 2 * (n2 ** 2 + 1)
           * np.log((2 * npx * b - nm ** 2) / (2 * npx * a - nm ** 2))
           / (npx ** 3 * nm ** 2))
    tp5 = (16 * n2 ** 3
           * (1.0 / (2 * npx * b - nm ** 2) - 1 / (2 * npx * a - nm ** 2))
           / (npx ** 3))
    tp = tp1 + tp2 + tp3 + tp4 + tp5
    return (ts + tp) / (2 * sa ** 2)


def refl_trans_one_layer(alpha: float, nr: np.ndarray,
                         tau: np.ndarray) -> tuple:
    """Reflectancia y transmitancia de una capa elemental (Allen 1969).

    Returns:
        (r, t, ra, ta): capa en vacio (r, t) y capa iluminada (ra, ta).
    """
    talf = calctav(alpha, nr)
    ralf = 1.0 - talf
    t12 = calctav(90, nr)
    r12 = 1.0 - t12
    t21 = t12 / (nr * nr)
    r21 = 1 - t21

    denom = 1.0 - r21 * r21 * tau * tau
    ta = talf * tau * t21 / denom
    ra = ralf + r21 * tau * ta

    t = t12 * tau * t21 / denom
    r = r12 + r21 * tau * t
    return r, t, ra, ta


def prospect_d(n: float, cab: float, car: float, cbrown: float, cw: float,
               cm: float, ant: float = 0.0,
               alpha: float = 40.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """PROSPECT-D oficial: (longitudes, reflectancia, transmitancia).

    Args:
        n: estructura (admite fraccionarios). cab/car/ant: pigmentos
            (µg/cm2). cbrown: marrones (0-1). cw: agua (cm).
            cm: materia seca (g/cm2). alpha: angulo (grados, 40 por defecto).

    Returns:
        (LAM, R, T) con R, T en [0,1].
    """
    from scipy.special import expi

    kall = (cab * KAB + car * KCAR + ant * KANT + cbrown * KBROWN
            + cw * KW + cm * KM) / n
    t1 = (1 - kall) * np.exp(-kall)
    t2 = kall ** 2 * (-expi(-kall))
    tau = np.ones_like(t1)
    tau[kall > 0] = (t1 + t2)[kall > 0]

    r, t, ra, ta = refl_trans_one_layer(alpha, NR, tau)

    # Apilado de N capas reales (Stokes 1862).
    d = np.sqrt((1 + r + t) * (1 + r - t) * (1.0 - r + t) * (1.0 - r - t))
    rq, tq = r * r, t * t
    a = (1 + rq - tq + d) / (2 * r)
    b = (1 - rq + tq + d) / (2 * t)

    bnm1 = np.power(b, n - 1)
    bn2 = bnm1 * bnm1
    a2 = a * a
    denom = a2 * bn2 - 1
    rsub = a * (bn2 - 1) / denom
    tsub = bnm1 * (a2 - 1) / denom

    # Caso sin absorcion (r + t >= 1).
    sin_abs = (r + t) >= 1.0
    tsub[sin_abs] = (t / (t + (1 - t) * (n - 1)))[sin_abs]
    rsub[sin_abs] = 1 - tsub[sin_abs]

    denom = 1 - rsub * r
    tran = ta * tsub / denom
    refl = ra + ta * rsub * t / denom
    return LAM.copy(), np.clip(refl, 0.0, 1.0), np.clip(tran, 0.0, 1.0)

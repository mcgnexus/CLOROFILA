"""Datos espectrales de trabajo para el modelo PROSPECT-D.

Contiene la malla de longitudes de onda, el indice de refraccion n(lam)
y los coeficientes especificos de absorcion por constituyente:
Kab, Kcar, Kant, Kbrown, Kw, Km.

ADVERTENCIA: son coeficientes APROXIMADOS de trabajo, construidos a
partir de valores ancla documentados en la literatura (picos de
absorcion conocidos). NO son las tablas oficiales de Feret et al. 2017.
Estan aislados en este modulo para poder sustituirlos por las tablas
publicadas sin tocar las matematicas de prospect.py.

Unidades (convenio PROSPECT-D):
  Kab, Kcar, Kant : cm2/µg   (Cab, Car, Cant en µg/cm2)
  Kbrown          : adimensional (Cbrown 0-1)
  Kw              : 1/cm     (Cw en cm de espesor equivalente)
  Km              : cm2/g    (Cm en g/cm2)
"""
import numpy as np

FUENTE_COEFICIENTES = (
    "aproximados de trabajo (picos documentados en literatura); "
    "pendientes de calibracion con Feret et al. 2017"
)

# Malla espectral del modelo: 400-2500 nm a 1 nm.
LAM_MIN, LAM_MAX, PASO = 400, 2500, 1
LAM = np.arange(LAM_MIN, LAM_MAX + PASO, PASO, dtype=float)


def _gauss(lam: np.ndarray, centro: float, sigma: float, amp: float) -> np.ndarray:
    """Campana gaussiana."""
    return amp * np.exp(-(((lam - centro) / sigma) ** 2))


# Indice de refraccion: descenso suave ~1.52 (400 nm) -> ~1.39 (2500 nm).
N_REFRACTIVO = np.maximum(1.38, 1.52 - 6.0e-5 * (LAM - 400.0))

# Clorofila a+b: picos azul (~442) y rojo (~680), fondo bajo en verde.
KAB = (0.0035
       + _gauss(LAM, 442.0, 25.0, 0.070)
       + _gauss(LAM, 680.0, 20.0, 0.085)
       + _gauss(LAM, 625.0, 15.0, 0.008))

# Carotenoides: absorcion 400-550 nm, pico ~470, nula mas alla de 550.
KCAR = (_gauss(LAM, 470.0, 30.0, 0.030)
        + 0.090 * np.clip((550.0 - LAM) / 150.0, 0.0, 1.0))

# Antocianinas: pico ~550 nm.
KANT = _gauss(LAM, 550.0, 35.0, 0.050)

# Pigmentos marrones: caida exponencial desde el azul.
KBROWN = 0.50 * np.exp(-(LAM - 400.0) / 250.0)

# Agua: picos en 970, 1200, 1450 y 1940 nm (+ fondo despreciable).
KW = (0.001
      + _gauss(LAM, 970.0, 30.0, 0.50)
      + _gauss(LAM, 1200.0, 35.0, 1.20)
      + _gauss(LAM, 1450.0, 50.0, 28.0)
      + _gauss(LAM, 1940.0, 60.0, 110.0))

# Materia seca: fondo ~15 con joroba en 1700-2300 nm.
KM = (15.0
      + 8.0 * np.exp(-(((LAM - 1900.0) / 400.0) ** 2))
      + _gauss(LAM, 2100.0, 60.0, 10.0)
      + _gauss(LAM, 2300.0, 50.0, 12.0))

# Rangos de validez y valores tipicos (hoja verde sana de referencia).
N_MIN, N_MAX, N_TIPICO = 1.0, 2.5, 1.5
CAB_MIN, CAB_MAX, CAB_TIPICO = 0.0, 120.0, 40.0   # µg/cm2
CAR_MIN, CAR_MAX, CAR_TIPICO = 0.0, 30.0, 8.0     # µg/cm2
CANT_MIN, CANT_MAX, CANT_TIPICO = 0.0, 10.0, 1.0  # µg/cm2
CBROWN_MIN, CBROWN_MAX, CBROWN_TIPICO = 0.0, 1.0, 0.0
CW_MIN, CW_MAX, CW_TIPICO = 0.0, 0.10, 0.015      # cm
CM_MIN, CM_MAX, CM_TIPICO = 0.0, 0.05, 0.005      # g/cm2

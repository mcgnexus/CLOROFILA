"""Modelo simplificado de gemelo digital (Cab, Cw, N).

Predice que deberia medir el AS7341 para una hoja con concentracion
de clorofila (Cab), contenido de agua (Cw) y parametro estructural (N)
dados, en la MISMA escala (cuentas ADC) que el simulador/mediciones,
en dos modos opticos: reflectancia y transmitancia.

Modelo:
1. Reflectancia teorica continua R(lam) en [0,1], inspirada en PROSAIL
   pero muy simplificada: absorcion de clorofila con picos en 445 y
   680 nm (ley tipo Beer-Lambert), meseta alta en NIR con absorcion
   suave por agua.
2. Convolucion numerica con la respuesta espectral gaussiana de cada
   canal del AS7341.
3. Paso a cuentas con un factor de calibracion compartido con el
   simulador (misma iluminacion/ganancia supuestas).

Limitaciones conocidas (ver README):
- Clear se aproxima como combinacion escalada, no como integral real.
- Cw solo afecta de forma apreciable al NIR: estos canales no permiten
  estimar el agua con fiabilidad.
- El indice 0-100 es una normalizacion demostrativa de Cab, no un
  diagnostico agronomico.
"""
import math

# Rango de validez del modelo.
CAB_MIN = 5.0    # µg/cm2, hoja clorotica
CAB_MAX = 80.0   # µg/cm2, hoja verde intensa
CAB_REF = 40.0   # referencia de hoja sana
CW_MIN = 0.005   # cm de agua equivalente (≈ g/cm2)
CW_MAX = 0.05
CW_REF = 0.015
# Parametro estructural N (nº de capas; 1.0 = hoja fina, 2.5 = gruesa).
# Inspirado en PROSPECT pero muy simplificado: modula el reparto de la
# luz dispersada entre reflectancia y transmitancia.
N_MIN = 1.0
N_MAX = 2.5
N_REF = 1.5  # valor neutro: reproduce la calibracion de la Fase 3

# Factor de paso reflectancia -> cuentas (iluminacion x ganancia x tiempo
# de integracion, supuestos constantes y compartidos con el simulador).
FACTOR_CALIBRACION = 5000.0

MODOS_VALIDOS = ("reflectancia", "transmitancia")

# Coeficiente de absorcion de clorofila (ajustado para que Cab=40 de
# ~260 cuentas en F2/F8 y ~1400-1500 en F5).
ALFA_CHL = 0.06
# Transmitancia: picos mas bajos y menor nivel maximo que en reflectancia.
ALFA_CHL_TRANSMITANCIA = 0.05

# Respuesta espectral aproximada por canal: (centro_nm, sigma_nm).
# Sigma ~ FWHM/2.355 con FWHM tipicos de 30-40 nm en VIS y ~60 nm en NIR.
RESPUESTA_CANAL = {
    "F1": (415, 14.0),
    "F2": (445, 15.0),
    "F3": (480, 16.0),
    "F4": (515, 16.0),
    "F5": (555, 18.0),
    "F6": (590, 17.0),
    "F7": (630, 18.0),
    "F8": (680, 20.0),
    "NIR": (910, 30.0),
}

ORDEN_CANALES = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "Clear", "NIR"]

LONGITUDES_ONDA = {
    "F1": 415, "F2": 445, "F3": 480, "F4": 515,
    "F5": 555, "F6": 590, "F7": 630, "F8": 680,
    "Clear": 0, "NIR": 910,
}


def _absorcion_clorofila(lam: float) -> float:
    """Forma espectral de absorcion de clorofila (picos en 445 y 680 nm)."""
    pico_azul = 0.9 * math.exp(-(((lam - 445.0) / 35.0) ** 2))
    pico_rojo = 1.0 * math.exp(-(((lam - 680.0) / 45.0) ** 2))
    fondo_verde = 0.15 * math.exp(-(((lam - 550.0) / 120.0) ** 2))
    return pico_azul + pico_rojo + fondo_verde


def _r_max(lam: float) -> float:
    """Reflectancia maxima (hoja sin clorofila), con joroba verde-amarilla."""
    return 0.30 + 0.10 * math.exp(-(((lam - 560.0) / 90.0) ** 2))


def _limitar_n(n: float) -> float:
    """Recorta N a su rango de validez."""
    return max(N_MIN, min(N_MAX, n))


def _reparto_estructural(n: float) -> tuple[float, float]:
    """Factores (reflectancia, transmitancia) segun la estructura N.

    Hoja mas gruesa (N alto): mas retrodispersion (R sube) y menos
    transmision (T baja). En N_REF ambos factores valen 1.
    """
    n = _limitar_n(n)
    n_norm = (n - N_MIN) / (N_MAX - N_MIN)
    n_ref_norm = (N_REF - N_MIN) / (N_MAX - N_MIN)
    delta = n_norm - n_ref_norm
    return 1.0 + 0.35 * delta, 1.0 - 0.35 * delta


def _aplicar_estructura(r_base: float, t_base: float, n: float) -> tuple[float, float]:
    """Aplica el reparto estructural y garantiza R + T <= 1 (fisica basica)."""
    f_r, f_t = _reparto_estructural(n)
    r, t = r_base * f_r, t_base * f_t
    total = r + t
    if total > 0.97:
        # Conservacion de la energia: reescala sin cambiar el cociente R/T.
        factor = 0.97 / total
        r, t = r * factor, t * factor
    return max(0.0, min(1.0, r)), max(0.0, min(1.0, t))


def _rt_base(lam: float, cab: float, cw: float) -> tuple[float, float]:
    """Reflectancia y transmitancia base (N neutro) para una longitud de onda.

    Returns:
        Tupla (r, t) en [0,1] antes del reparto estructural.
    """
    cab = max(CAB_MIN, min(CAB_MAX, cab))
    cw = max(CW_MIN, min(CW_MAX, cw))
    if lam >= 800:
        # Meseta NIR con absorcion suave por agua (mayor en transmision).
        r = 0.48 * math.exp(-cw * 8.0)
        t = 0.42 * math.exp(-cw * 10.0)
        return r, t
    absorcion = _absorcion_clorofila(lam)
    r = 0.025 + (_r_max(lam) - 0.025) * math.exp(-absorcion * cab * ALFA_CHL)
    t = 0.02 + (_t_max(lam) - 0.02) * math.exp(
        -absorcion * cab * ALFA_CHL_TRANSMITANCIA)
    atenuacion_agua = math.exp(-cw * 2.0)
    return r * atenuacion_agua, t * atenuacion_agua


def reflectancia_teorica(lam: float, cab: float, cw: float, n: float = N_REF) -> float:
    """Reflectancia teorica R en [0,1] para una longitud de onda.

    Args:
        lam: longitud de onda en nm (para lam >= 800 se usa el modelo NIR).
        cab: clorofila en µg/cm2.
        cw: contenido de agua en cm.
        n: parametro estructural (1.0 = fina, 2.5 = gruesa).

    Returns:
        Reflectancia entre 0 y 1.
    """
    r_base, t_base = _rt_base(lam, cab, cw)
    r, _ = _aplicar_estructura(r_base, t_base, n)
    return r


def _t_max(lam: float) -> float:
    """Transmitancia maxima (hoja sin clorofila), con joroba verde."""
    return 0.16 + 0.12 * math.exp(-(((lam - 560.0) / 90.0) ** 2))


def transmitancia_teorica(lam: float, cab: float, cw: float, n: float = N_REF) -> float:
    """Transmitancia teorica T en [0,1] para una longitud de onda.

    Args:
        lam: longitud de onda en nm (para lam >= 800 se usa el modelo NIR).
        cab: clorofila en µg/cm2.
        cw: contenido de agua en cm.
        n: parametro estructural (1.0 = fina, 2.5 = gruesa).

    Returns:
        Transmitancia entre 0 y 1 (siempre menor que la reflectancia
        equivalente, con caida fuerte en el NIR por el agua).
    """
    r_base, t_base = _rt_base(lam, cab, cw)
    _, t = _aplicar_estructura(r_base, t_base, n)
    return t


def _integrar_canal(centro: float, sigma: float, cab: float, cw: float,
                    modo: str = "reflectancia", n: float = N_REF) -> float:
    """Convolucion numerica de R(lam) o T(lam) con la gaussiana del canal."""
    if modo not in MODOS_VALIDOS:
        raise ValueError(f"modo debe ser uno de {MODOS_VALIDOS}")
    n = _limitar_n(n)
    if modo == "reflectancia":
        def funcion(lam: float, cab: float, cw: float) -> float:
            return reflectancia_teorica(lam, cab, cw, n)
    else:
        def funcion(lam: float, cab: float, cw: float) -> float:  # type: ignore[no-redef]
            return transmitancia_teorica(lam, cab, cw, n)
    paso = 2.0
    lam_min = centro - 3 * sigma
    lam_max = centro + 3 * sigma
    num = 0.0
    den = 0.0
    lam = lam_min
    while lam <= lam_max:
        peso = math.exp(-(((lam - centro) / sigma) ** 2) / 2.0)
        num += funcion(lam, cab, cw) * peso
        den += peso
        lam += paso
    return num / den if den > 0 else 0.0


def predecir_canales(cab: float, cw: float, modo: str = "reflectancia",
                     n: float = N_REF) -> dict:
    """Predice los 10 canales del AS7341 en cuentas ADC.

    Args:
        cab: concentracion de clorofila (µg/cm2).
        cw: contenido de agua (cm de espesor equivalente).
        modo: "reflectancia" o "transmitancia".
        n: parametro estructural (1.0 = hoja fina, 2.5 = gruesa).

    Returns:
        dict {canal: cuentas (int)} en el orden de ORDEN_CANALES.
    """
    if modo not in MODOS_VALIDOS:
        raise ValueError(f"modo debe ser uno de {MODOS_VALIDOS}")
    n = _limitar_n(n)
    pred = {}
    for canal in ORDEN_CANALES:
        if canal == "Clear":
            continue  # se calcula despues como combinacion
        centro, sigma = RESPUESTA_CANAL[canal]
        r = _integrar_canal(centro, sigma, cab, cw, modo, n)
        pred[canal] = max(0, int(round(r * FACTOR_CALIBRACION)))
    # Clear: aproximacion escalada del nivel medio de luz (banda ancha).
    media = sum(pred.values()) / len(pred)
    pred["Clear"] = max(0, int(round(media * 1.8)))
    return {c: pred[c] for c in ORDEN_CANALES}


def comparar_lectura(medido: dict, prediccion: dict, orden: list | None = None) -> dict:
    """Compara una lectura real/simulada con la prediccion del gemelo.

    Args:
        medido: dict {canal: cuentas} de la lectura.
        prediccion: dict {canal: cuentas} del modelo.
        orden: lista de canales a incluir (por defecto, interseccion).

    Returns:
        dict con error_por_canal, rmse, rmse_rel, sesgo y n_canales.
    """
    if orden is None:
        orden = [c for c in prediccion if c in medido]
    errores = {c: medido[c] - prediccion[c] for c in orden}
    n = len(errores)
    if n == 0:
        return {"error_por_canal": {}, "rmse": 0.0,
                "rmse_rel": 0.0, "sesgo": 0.0, "n_canales": 0}
    mse = sum(e * e for e in errores.values()) / n
    rmse = math.sqrt(mse)
    media_pred = sum(prediccion[c] for c in orden) / n
    return {
        "error_por_canal": errores,
        "rmse": round(rmse, 2),
        "rmse_rel": round(rmse / media_pred, 4) if media_pred else 0.0,
        "sesgo": round(sum(errores.values()) / n, 2),
        "n_canales": n,
    }


def indice_clorofila(cab: float) -> float:
    """Normaliza Cab a un indice demostrativo 0-100.

    ADVERTENCIA: es una renormalizacion lineal de Cab, no una medida
    agronomica calibrada de salud vegetal.
    """
    x = (cab - CAB_MIN) / (CAB_MAX - CAB_MIN)
    return round(max(0.0, min(1.0, x)) * 100.0, 1)

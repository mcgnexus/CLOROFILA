"""Simulador del sensor espectral AS7341 (FASE 3).

Genera lecturas sinteticas a partir del gemelo digital (twin_model):
toma la prediccion teorica para un estado de hoja (Cab, Cw, modo) y le
suma deriva instrumental lenta + ruido gaussiano. Opcionalmente simula
estres (caida del NIR, subida del rojo, clorosis en el verde) para
demostrar la deteccion de anomalias del gemelo.
"""
import math
import random
import time
from datetime import datetime, timezone

from twin_model import (
    LONGITUDES_ONDA,
    MODOS_VALIDOS,
    N_REF,
    ORDEN_CANALES,
    predecir_canales,
)

# Deriva instrumental residual por canal (ademas de la deriva de Cab).
AMPLITUD_DERIVA = {
    "F1": 15,
    "F2": 15,
    "F3": 20,
    "F4": 40,
    "F5": 70,
    "F6": 50,
    "F7": 35,
    "F8": 20,
    "Clear": 100,
    "NIR": 90,
}

# Desviacion tipica del ruido gaussiano por canal.
RUIDO = {
    "F1": 8,
    "F2": 8,
    "F3": 10,
    "F4": 20,
    "F5": 35,
    "F6": 25,
    "F7": 18,
    "F8": 10,
    "Clear": 50,
    "NIR": 45,
}

ORDEN_CANALES = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "Clear", "NIR"]
# Re-exportados desde twin_model para compatibilidad con codigo Fase 1.
__all__ = ["SimuladorAS7341", "ORDEN_CANALES", "LONGITUDES_ONDA",
           "AMPLITUD_DERIVA", "RUIDO"]


class SimuladorAS7341:
    """Generador de lecturas sinteticas del AS7341 basado en el gemelo.

    El estado "verdadero" de la hoja (cab, cw) deriva lentamente para
    que el dashboard se vea vivo; la lectura es la prediccion del
    modelo para ese estado mas deriva instrumental y ruido.
    """

    def __init__(self, semilla: int | None = None,
                 cab_base: float = 45.0, cw: float = 0.015,
                 modo: str = "reflectancia", estres: bool = False,
                 n: float = N_REF):
        """Crea el simulador.

        Args:
            semilla: semilla opcional para reproducibilidad en tests.
            cab_base: clorofila verdadera media (µg/cm2).
            cw: contenido de agua verdadero (cm).
            modo: "reflectancia" o "transmitancia".
            estres: si True, aplica firma de estres a la lectura.
            n: parametro estructural verdadero de la hoja.
        """
        if semilla is not None:
            random.seed(semilla)
        if modo not in MODOS_VALIDOS:
            raise ValueError(f"modo debe ser uno de {MODOS_VALIDOS}")
        self._t0 = time.monotonic()
        self.cab_base = cab_base
        self.cw = cw
        self.modo = modo
        self.estres = estres
        self.n = n
        self.cab_actual = cab_base

    def set_estado(self, cab_base: float | None = None,
                   cw: float | None = None, modo: str | None = None,
                   estres: bool | None = None, n: float | None = None):
        """Actualiza el estado verdadero (usado por POST /api/config)."""
        if cab_base is not None:
            self.cab_base = cab_base
        if cw is not None:
            self.cw = cw
        if modo is not None:
            if modo not in MODOS_VALIDOS:
                raise ValueError(f"modo debe ser uno de {MODOS_VALIDOS}")
            self.modo = modo
        if estres is not None:
            self.estres = estres
        if n is not None:
            self.n = n

    def generar_lectura(self, modo: str | None = None) -> dict:
        """Genera una lectura completa con timestamp ISO 8601 UTC.

        Args:
            modo: override puntual del modo (por defecto, self.modo).

        Returns:
            dict con "timestamp", "canales", "longitudes_onda",
            "orden_canales", estado verdadero y flags de modo/estres.
        """
        modo_efectivo = modo or self.modo
        t = time.monotonic() - self._t0
        # Deriva lenta del estado verdadero de la hoja (periodo 60 s).
        self.cab_actual = self.cab_base + 4.0 * math.sin(2 * math.pi * t / 60.0)
        base = predecir_canales(self.cab_actual, self.cw, modo_efectivo, self.n)
        # Firma de estres: colapso parcial del NIR, enrojecimiento y
        # perdida del pico verde (patron tipico simplificado).
        if self.estres:
            base = dict(base)
            base["NIR"] = int(base["NIR"] * 0.82)
            base["F8"] = base["F8"] + 120
            base["F7"] = base["F7"] + 60
            base["F5"] = max(0, base["F5"] - 150)
        canales = {}
        for i, canal in enumerate(ORDEN_CANALES):
            deriva = AMPLITUD_DERIVA[canal] * math.sin(2 * math.pi * t / 20.0 + i * 0.6)
            ruido = random.gauss(0, RUIDO[canal])
            canales[canal] = max(0, int(round(base[canal] + deriva + ruido)))

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "canales": canales,
            "longitudes_onda": dict(LONGITUDES_ONDA),
            "orden_canales": list(ORDEN_CANALES),
            "cab_verdadero": round(self.cab_actual, 2),
            "cw": self.cw,
            "modo": modo_efectivo,
            "n": self.n,
            "estres": self.estres,
        }

"""Carga la tabla oficial PROSPECT-D con verificacion de integridad."""
import hashlib
from pathlib import Path

import numpy as np

TABLA = Path(__file__).resolve().parent / "prospect_d_spectra.txt"

# SHA256 del fichero oficial prospect_d_spectra.txt de prosail 2.0.5.
SHA256_ESPERADO = "e703b345f0a0860808e230ca0869f5b108ca1115ab9950c9651a29fee72c474d"

# Columnas del fichero: [longitud, nr, kab, kcar, kant, kbrown, kw, km].
LAM = NR = KAB = KCAR = KANT = KBROWN = KW = KM = None


def _cargar() -> None:
    """Carga la tabla verificando su hash (falla si fue modificada)."""
    global LAM, NR, KAB, KCAR, KANT, KBROWN, KW, KM
    datos = TABLA.read_bytes()
    sha = hashlib.sha256(datos).hexdigest()
    if sha != SHA256_ESPERADO:
        raise ValueError(
            f"Tabla oficial modificada o corrupta: sha256={sha} "
            f"(esperado {SHA256_ESPERADO}). Ver PROCEDENCIA.md.")
    cols = np.loadtxt(TABLA, comments="#", unpack=True)
    (LAM, NR, KAB, KCAR, KANT, KBROWN, KW, KM) = cols
    assert LAM[0] == 400.0 and LAM[-1] == 2500.0 and len(LAM) == 2101


_cargar()

# Rangos oficiales tipicos (documentacion de prosail / articulos).
N_MIN, N_MAX = 0.8, 2.5
CAB_MIN, CAB_MAX = 0.0, 80.0
CAR_MIN, CAR_MAX = 0.0, 20.0
CANT_MIN, CANT_MAX = 0.0, 10.0
CBROWN_MIN, CBROWN_MAX = 0.0, 1.0
CW_MIN, CW_MAX = 0.0, 0.20
CM_MIN, CM_MAX = 0.0, 0.05

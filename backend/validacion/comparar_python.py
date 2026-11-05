"""Compara prospect_referencia.py contra espectros del paquete R `prospect`.

Uso:
    Rscript comparar_R.R grid_prospect.csv espectros_R.csv
    python comparar_python.py grid_prospect.csv espectros_R.csv

Requiere R >= 4 con el paquete `prospect` de los autores instalado.
"""
import csv
import sys

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from prospect_oficial.prospect_referencia import prospect_d as mio

grid = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
rfile = list(csv.DictReader(open(sys.argv[2], encoding="utf-8")))

max_r = max_t = 0.0
for i, g in enumerate(grid, start=1):
    w = np.array([float(r[f"wvl_{i}"]) for r in rfile])
    rr = np.array([float(r[f"reflectance_{i}"]) for r in rfile])
    tr = np.array([float(r[f"transmittance_{i}"]) for r in rfile])
    lm, rm, tm = mio(float(g["n"]), float(g["cab"]), float(g["car"]),
                     float(g["brown"]), float(g["ewt"]), float(g["lma"]),
                     float(g["ant"]))
    assert np.array_equal(w, lm), "mallas distintas"
    max_r = max(max_r, float(np.nanmax(np.abs(rr - rm))))
    max_t = max(max_t, float(np.nanmax(np.abs(tr - tm))))
print("GLOBAL max|dR|=%.2e max|dT|=%.2e" % (max_r, max_t))
print("OK" if max(max_r, max_t) < 1e-9 else "DIVERGENCIA")

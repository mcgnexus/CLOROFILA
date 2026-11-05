# Procedencia de PROSPECT-D oficial

## Fuente

- Tablas: `prospect_d_spectra.txt` del paquete **prosail 2.0.5**
  (J. Gomez-Dans, NCEO & UCL), fichero identico al distribuido en PyPI.
- URL: https://github.com/jgomezdans/prosail
- SHA256: `e703b345f0a0860808e230ca0869f5b108ca1115ab9950c9651a29fee72c474d`
  (2101 filas, 400-2500 nm; `carga_tablas.py` lo verifica al cargar).
- El fichero documenta su origen: `dataSpec_PDB.m (January, 16th 2017)`,
  con datos de Feret, Gitelson, Noble & Jacquemoud (2017) y pigmentos
  marrones de F. Baret (EMMAH, INRA Avignon).

## Referencias cientificas

- Feret, J.-B., Gitelson, A.A., Noble, S.D. & Jacquemoud, S. (2017).
  PROSPECT-D: Towards modeling leaf optical properties through a
  complete lifecycle. Remote Sensing of Environment, 193, 204-215.
  https://doi.org/10.1016/j.rse.2017.03.004
- Ecuaciones: Stern (1964), Allen et al. (1969), Stokes (1862).
- Implementacion de referencia: paquete R `prospect`
  (https://gitlab.com/jbferet/prospect/).

## Que se adopto

- `prospect_d_spectra.txt`: copia integra y verificada por hash.
- `prospect_referencia.py`: implementacion propia de las ecuaciones
  publicadas, siguiendo la estructura de `prospect_d.py` de prosail
  para permitir comparacion directa.

## Contraste contra el paquete R de los autores (ejecutado 2026-11-05)

- Entorno: R 4.6.2 (instalacion de usuario) + paquete `prospect` 2.0.1
  instalado desde GitLab (`remotes::install_gitlab("jbferet/prospect")`).
- Rejilla: 12 casos en `../validacion/grid_prospect.csv` (N 1.0-2.5
  incluidos fraccionarios 1.33/1.7/2.2, Cab 0-80, carotenoides,
  antocianinas, marrones, agua y materia seca; incluye el caso limite
  sin absorcion).
- Resultado: `comparar_python.py` informa **max|dR| = 2.15e-15,
  max|dT| = 2.16e-15** (ruido de punto flotante). Los avisos de NaN en
  regimenes extremos son identicos en ambas implementaciones.
- Fixture: `../validacion/espectros_R.csv` (salida R) permite repetir
  el lado Python sin R.

## Licencia

- `prosail` declara licencia **GPLv3** (Copyright J Gomez-Dans
  2017-2018). Este directorio se distribuye bajo los mismos terminos;
  si el proyecto se distribuye, debe cumplir GPLv3 (incluir avisos y
  ofrecer el codigo fuente).
- Paquete R `prospect`: GPL-3.

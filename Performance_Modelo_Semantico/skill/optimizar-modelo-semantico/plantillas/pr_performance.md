# perf(<modelo>): <resumen corto de las optimizaciones>

## Qué cambia

| Propuesta | Objeto | Cambio | Archivo TMDL | ¿Cambia el resultado? | ¿Requiere refresh? |
|---|---|---|---|---|---|
| P01 | `'Tabla'[Columna]` | <qué se hizo> | `definition/tables/Tabla.tmdl` | no | sí |

Propuestas aprobadas en `propuestas.csv` (columna `aprobada = si`). Las que quedaron afuera y por qué:

- P0X: <motivo>

## Evidencia (antes)

Corrida `antes` sobre el commit `<sha>`: <dos o tres datos del diagnóstico que justifican el cambio, por ejemplo "la columna X ocupa el 48 % del modelo" o "Q02 pasa el 85 % del tiempo en el formula engine">.

## Medición (antes y después)

<!-- Pegar acá informe_perf.md de NB_PERF_03. Hasta que exista, dejar: -->
_Pendiente: desplegar esta rama en el workspace de prueba, correr NB_PERF_01 y NB_PERF_02 con `CORRIDA = despues_<pr>` y NB_PERF_03._

## Cómo revisar

1. Diff de los `.tmdl`: cada commit es una propuesta (`perf(P01): ...`).
2. BPA del PR (si está activo el workflow de CI): sin errores nuevos.
3. Veredicto de NB_PERF_03 = `APROBADO`, o explicación de cada regresión o resultado distinto.
4. Después del merge: el proceso habitual de despliegue a producción y un refresh si alguna fila dice "requiere refresh = sí".

## Vuelta atrás

Revertir el merge del PR y volver a sincronizar el workspace desde Git. Si hubo refresh, refrescar de nuevo después de revertir.

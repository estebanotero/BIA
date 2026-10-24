# Reglas de calidad · <modelo o LOAD_GROUP> · <AAAA-MM-DD>

**Qué cubre:** <hechos y dimensiones de gold que controla>
**Reglas propuestas:** <n> (CUADRE <n> · INTEGRIDAD <n> · FRESCURA <n> · VOLUMEN <n> · NEGOCIO <n>) · ERROR <n> · WARN <n>

## Reglas

| Código | Categoría | Tipo | Qué controla | Tolerancia o rango | Severidad | Por qué |
|---|---|---|---|---|---|---|

## Lo que no se controla (y por qué)

- <ej. cuadre contra el origen: el pipeline no registra filas leídas por la copia>

## [dato a confirmar]

| Regla | Pregunta | A quién |
|---|---|---|

## Diagnóstico (si se pidió)

| Regla | Resultado | Causa probable | Qué hacer | ¿Reprocesar? | Avisar a |
|---|---|---|---|---|---|

## Próximos pasos

1. Revisar y correr `alta_reglas_calidad.sql` en DES.
2. Probar con `NB_CAL_01` a mano (`reglas_json` = salida de `dq.usp_GET_REGLAS`).
3. <...>

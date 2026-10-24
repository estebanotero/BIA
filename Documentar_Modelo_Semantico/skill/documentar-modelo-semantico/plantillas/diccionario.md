# Diccionario de datos: [nombre del modelo]

Origen: modelo semántico de Microsoft Fabric · Workspace: [workspace] · Generado: [AAAA-MM-DD]

## Diagrama de relaciones

```mermaid
erDiagram
    [TablaHechos] }o--|| [TablaDimension] : "[columna]"
```

## Tablas

| Tabla | Filas | Modo | Descripción |
| --- | --- | --- | --- |
| [tabla] | [n] | [Import / DirectLake / DirectQuery] | [descripción o [dato a confirmar]] |

## [nombre de la tabla]

[Qué representa una fila de la tabla, o [dato a confirmar]]

| Columna | Tipo | Descripción | Ejemplo | Nulos | Clave | Relación | Sensibilidad |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [columna] | [tipo] | [descripción o [dato a confirmar]] | [valor, o - si es sensible] | [n (%)] | [Sí / -] | [→ Tabla[Columna]] | [Pública / Interna / Sensible] |

## Medidas

| Medida | Tabla | Descripción | Formato | Expresión DAX |
| --- | --- | --- | --- | --- |
| [medida] | [tabla] | [qué calcula, en palabras] | [formato] | `[expresión]` |

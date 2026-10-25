# Impacto · <cambio en una línea> · <AAAA-MM-DD>

**Qué cambia:** <nodo y qué se modifica: columna, filtro, modo de carga, baja>
**Alcance:** <n> objetos gold · <n> tablas de modelo · <n> modelos · <n> reportes · criticidad máxima <ALTA | MEDIA | BAJA>
**Linaje del:** <generado_at de catalogo.nodo>

```mermaid
flowchart LR
    %% solo el vecindario del nodo que cambia
```

## Afectados

| Capa | Objeto | Qué se rompe o cambia | Verificado en | Dueño | Criticidad |
|---|---|---|---|---|---|
| gold | `gold.<x>` | <error de carga / columna vacía / número distinto / nada> | <SQL_TEXT / modelo.json / inferido> | <dueño o [dato a confirmar]> | <ALTA> |

## No afectados (y por qué)

- `<objeto>`: <está aguas abajo pero su SQL no usa la columna>

## Qué probar antes

1. <objeto gold en DES con la metadata nueva>
2. <reglas de dq.REGLA que leen esas tablas>
3. <medidas del modelo sobre esas columnas>

## A quién avisar

| Dueño | Por qué | Cuándo |
|---|---|---|

## [verificar] y [dato a confirmar]

- <conclusiones que dependen de aristas de confianza baja o de datos que no están en el linaje>

## Próximos pasos

1. <...>

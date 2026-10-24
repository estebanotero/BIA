# Despliegue · PR #<n> · <título>

**Veredicto:** LISTO | LISTO CON CONDICIONES | BLOQUEADO
**Commit:** `<sha>` · **Ambientes:** TEST → PRD

## Qué cambia

| Item o migración | Tipo | Acción | Caso BIA |
|---|---|---|---|
| `NB_MDP_20_silver` | Notebook | modificado | Pipeline_Metadata_Medallion |
| `004_alta_erp.sql` | Migración | nueva | Perfilado_Origen_Medallion |

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Qué hacer |
|---|---|---|---|---|
| 1 | Bloqueante / Alta / Media / Baja | | archivo:línea | |

## parameter.yml propuesto

```yaml
find_replace:
  - find_value: "<valor de DES>"
    replace_value:
      TEST: "<...>"
      PRD: "<...>"
    item_type: "<Tipo>"
```

## Pasos manuales

Antes del merge:
- [ ] `[dato a confirmar]`

Después de PRD:
- [ ] Correr el pipeline o notebook afectado y revisar `log.RUN_STEP`.

## Vuelta atrás

| Qué | Cómo |
|---|---|
| Items | Revert del PR en `main`: el workflow vuelve a desplegar la versión anterior |
| Migraciones | No se revierten solas. `<script de vuelta atrás o restauración desde el backup>` |
| Datos | `<si hubo recarga, cómo volver: watermark anterior, tabla de backup>` |

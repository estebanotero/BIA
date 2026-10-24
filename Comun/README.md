# Comun: archivos que comparten varios casos

| Archivo | Lo usan | Dónde va en Fabric |
|---|---|---|
| [`patrones_sensibles.json`](patrones_sensibles.json) | `NB_DOC_01` (Documentar_Modelo_Semantico), `NB_PRF_01` (Perfilado_Origen_Medallion) y `NB_SEG_01`/`NB_SEG_02` (Seguridad_Acceso_Datos) para marcar columnas sensibles por nombre | `Files/comun/patrones_sensibles.json` del lakehouse por defecto (`LH_MEDALLION`) |

Si el archivo no está en el lakehouse, cada notebook usa su lista por defecto, que hoy es la misma que la de este JSON. Para agregar un patrón, cambialo acá (por PR), subilo al lakehouse y los casos lo toman en la próxima corrida. Si cambiás la lista por defecto de un notebook, cambiá también la de los otros y este archivo (la prueba local de Seguridad_Acceso_Datos falla si su lista difiere de este JSON).

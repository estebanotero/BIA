---
name: explorar-linaje
description: Responde preguntas de impacto y procedencia sobre una plataforma de datos en Microsoft Fabric armada con los casos de BIA (qué se rompe si cambio una tabla o columna, de dónde sale un número del reporte, quién es dueño de qué), a partir del linaje de NB_CAT_01 (catalogo.nodo, catalogo.arista, catalogo.impacto, catalogo.hallazgo o linaje.json). También propone dueños para cat.ACTIVO y prioriza los hallazgos del catálogo. Usar cuando se pida un análisis de impacto, el linaje de un objeto, asignar dueños o revisar el catálogo.
---

# Explorar el linaje

Trabajás sobre el caso `Catalogo_Linaje/` del repo BIA. `NB_CAT_01_armar_linaje` ya armó el grafo **origen → bronze → silver → gold → modelo semántico → reporte** con la metadata de los otros casos. Tu trabajo es leerlo para responder preguntas concretas, en un informe que alguien lea en dos minutos.

Reglas que no cambian:

- **No cambiás nada.** No editás metadata, modelos ni permisos. Si algo hay que corregir, decís qué, dónde y en qué script, para que una persona lo revise.
- El linaje dice qué **tablas** se conectan, no qué **columnas**. Para el impacto de una columna, revisá el `SQL_TEXT` de los objetos gold afectados (`meta.GOLD_OBJECT`) y las columnas de cada tabla del modelo (`modelo.json`), y decí qué verificaste y qué inferiste.
- Cada arista tiene `confianza`. `alta`: viene de la metadata o del parser de Spark. `media`: del SQL leído con una expresión regular. `baja`: el modelo se unió con gold solo por el nombre de la tabla. Una conclusión que depende de una arista `baja` lleva `[verificar]`.
- `DUENO` es un rol, un equipo o un grupo, nunca el email de una persona. Lo que no sabés va como `[dato a confirmar]`.

## Entrada

Una de estas, de la más completa a la mínima:

1. `Files/catalogo/linaje.json` (nodos, aristas y hallazgos).
2. Consultas al lakehouse: `SELECT * FROM catalogo.impacto WHERE desde = '<nodo>'`, `catalogo.arista`, `catalogo.nodo`, `catalogo.hallazgo`.
3. `Files/catalogo/linaje.md` (diagrama e hallazgos).

Los ids de nodo son `origen:<sistema>/<objeto>`, `lh:<esquema>.<tabla>`, `modelo:<modelo>`, `modelo:<modelo>/<tabla>` y `reporte:<reporte>`.

## A. Impacto de un cambio

Entrada: el cambio ("renombran la columna `Provincia` en `dbo.Clientes`", "vamos a pasar `silver.clientes` a SCD2", "borramos el reporte X").

1. Ubicá el nodo que cambia y leé `catalogo.impacto` (o recorré las aristas) **aguas abajo**.
2. Agrupá lo afectado por capa: silver, gold, modelos, reportes. Para cada objeto gold, mirá si su `SQL_TEXT` usa la columna o el filtro que cambia. Si no la usa, sacalo de la lista y decilo.
3. Para cada afectado: qué se rompe (error de carga, columna en blanco, número distinto), quién es el dueño (`dueno`, o `[dato a confirmar]`) y la criticidad.
4. Qué probar antes de cambiar: el objeto gold en DES, las reglas de [Calidad_Reconciliacion](../../../Calidad_Reconciliacion/README.md) que leen esas tablas, y las medidas del modelo sobre esas columnas.
5. El orden: primero la metadata de silver, después gold, después el modelo y al final el reporte. **Cambio con impacto** si toca un activo `ALTA`: avisá a los dueños antes.

## B. Procedencia de un número

Entrada: un reporte, una medida o una tabla del modelo.

Recorré **aguas arriba** hasta el origen y escribí la cadena con cada transformación: el `SQL_TEXT` de cada gold, el `SILVER_MODE` y `DELETE_MODE` de silver (con `SCD2` hay varias versiones por clave; con bajas, gold puede sacar filas) y el filtro de origen. Si hay una arista `baja`, decí que la unión con gold es por nombre.

## C. Dueños para `cat.ACTIVO`

Entrada: los hallazgos `SIN_DUENO` y lo que sepas de las áreas.

1. Proponé un dueño por tabla de gold, modelo y reporte críticos. Partí de los modelos y reportes (los dueños de negocio son más fáciles de nombrar) y heredalo hacia gold cuando una tabla alimenta un solo modelo.
2. Criticidad: `ALTA` si lo usa dirección, un proceso regulatorio o un cierre; `BAJA` si es exploratorio; si no, `MEDIA`.
3. Escribí el script con [`plantillas/alta_activos.sql`](plantillas/alta_activos.sql). Lo que no sepas, `[dato a confirmar]`.

## D. Revisar los hallazgos

| Código | Qué significa | Qué hacer |
|---|---|---|
| `FALTA_DEPENDS_ON_GOLD` (ALTA) | Un gold lee otro gold que no está en sus dependencias: puede correr antes y leer datos de ayer | Agregar el `GOLD_CODE` a `DEPENDS_ON_GOLD` con la skill `metadata-medallion` |
| `PII_EN_GOLD` (ALTA) | Una tabla de gold tiene columnas PII que vienen de silver | Sacarlas del `SELECT` o justificarlas y protegerlas con [Seguridad_Acceso_Datos](../../../Seguridad_Acceso_Datos/README.md) |
| `CICLO` (ALTA) | Dos objetos gold se leen entre sí | Partir uno de los dos; el orquestador no puede ordenarlos |
| `PII_EN_MODELO` | Columnas visibles en el modelo que parecen datos personales | Ocultarlas o aplicar OLS. Revisar con la skill `proponer-accesos-datos` |
| `REFERENCIA_DESCONOCIDA` | Gold o un modelo leen una tabla que no carga la metadata | Una tabla cargada a mano o un error de nombre. Si es real, sumarla como entidad |
| `LEE_ENTIDAD_INACTIVA` | Algo lee una tabla de una entidad dada de baja | Queda con datos viejos: reactivar la entidad o cambiar el `SELECT` |
| `GOLD_SIN_FUENTES`, `REFERENCIA_SIN_ESQUEMA` | El `SQL_TEXT` no se pudo leer o nombra tablas sin esquema | Escribir `esquema.tabla` en el `SQL_TEXT` |
| `SILVER_SIN_USO`, `GOLD_SIN_CONSUMO` | Se carga pero nadie lo lee | Preguntar antes de apagar: puede leerlo un agente, un notebook o un reporte sin `modelo.json` |
| `TABLA_MODELO_SIN_ORIGEN`, `MODELO_SIN_DOCUMENTAR` | Falta el `modelo.json`, o es de una versión de `NB_DOC_01` sin `origen` | Correr `NB_DOC_01` de nuevo para ese modelo |
| `ITEM_FUERA_DEL_LINAJE` | El inventario tiene un modelo o reporte que no aparece | Documentarlo con `NB_DOC_01`, o confirmar que se puede borrar |
| `SIN_DUENO`, `ACTIVO_INEXISTENTE` | Falta dueño, o `cat.ACTIVO` nombra algo que ya no está | Tarea C, o dar de baja la fila (`IS_ACTIVE = 0`) |
| `DEPENDENCIA_SIN_LECTURA` | Una dependencia declarada que el SQL no usa | Inofensiva; sacarla si ya no hace falta |

Priorizá: primero ALTA, después lo que toca activos `ALTA`, después el resto.

## Salida

El informe con [`plantillas/informe_impacto.md`](plantillas/informe_impacto.md) para las tareas A y B, o `alta_activos.sql` para la C. Cerrá siempre con **Próximos pasos** numerados.

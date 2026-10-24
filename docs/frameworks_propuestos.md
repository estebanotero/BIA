# Frameworks que faltan

**En corto:** BIA cubre bien el camino *origen → bronze → silver → gold → modelo semántico → agente*, con Claude en cada paso. Lo que falta es lo que rodea a ese camino cuando pasa a producción: **cómo se despliega entre ambientes, cómo se opera y cómo se gobierna**. Esta lista es una propuesta: **ninguno está construido**. Cada uno se arma solo con el OK de Eduardo, en su carpeta y por PR, con la misma estructura que el resto (ver [convenciones](convenciones.md)).

Revisión del 2026-10-24.

## Resumen

| # | Framework propuesto | Prioridad | Por qué ahora | Depende de |
|---|---|---|---|---|
| 1 | `Despliegue_Entre_Ambientes` (CI/CD DES → PRD) | **Alta** | Los seis casos dicen "probalo en desarrollo" y ninguno dice cómo llega a producción | — |
| 2 | `Monitoreo_Plataforma` (observabilidad y alertas) | **Alta** | Cada caso deja su log en un lugar distinto y nadie los mira juntos | Inventario, MDP, AGT, PERF |
| 3 | `Seguridad_Acceso_Datos` (roles, RLS/CLS, PII) | **Alta** | La PII se detecta en dos casos, pero nada aplica permisos ni etiquetas | PRF, DOC |
| 4 | `Calidad_Reconciliacion` (calidad en gold y cuadre con el origen) | Media | MDP valida fila por fila en silver; nadie controla totales ni reglas entre tablas | MDP |
| 5 | `Historia_SCD_Bajas` (SCD tipo 2 y borrado lógico) | Media | Está en los próximos pasos de MDP y es lo primero que pide un negocio con dimensiones que cambian | MDP, PRF |
| 6 | `Catalogo_Linaje` (catálogo unificado) | Baja | Ya existen las piezas (inventario, metadata, perfil, diccionario), falta unirlas | Inventario, MDP, PRF, DOC |
| 7 | `Costos_Capacidad` (FinOps de Fabric) | Baja | Útil cuando haya varias cargas programadas en la misma capacidad | MDP, Monitoreo |

## 1. Despliegue entre ambientes (CI/CD)

**Problema.** Hoy cada caso se importa a mano en un workspace. Los nombres que cambian entre DES y PRD (base de control, lakehouse, conexiones, IDs del agente) se escriben dentro de los notebooks.

**Qué tendría.**
- Workspaces DES, (TEST) y PRD conectados a Git, con deployment pipelines de Fabric o la librería `fabric-cicd` desde GitHub Actions / Azure DevOps. Tabla comparativa de las dos opciones.
- Parametrización: variable library o `parameter.yml` de `fabric-cicd` para los nombres por ambiente [verificar el soporte vigente de cada una].
- Despliegue de la base de control: los `.sql` idempotentes de MDP e Inventario como migraciones.
- El workflow de pruebas locales (desvío 10 de convenciones) como primer paso del CI.
- Rol de Claude: skill que revisa el diff de un PR de Fabric (items, parámetros, cambios con impacto) y arma el checklist de despliegue.

**Por qué primero.** Sin esto, todo lo demás queda en DES o se copia a mano a PRD, con el riesgo de que los ambientes diverjan.

## 2. Monitoreo de la plataforma

**Problema.** El estado está repartido: `log.RUN_STEP` (MDP), `agente.eval_historial` (AGT), `perf_*` (PERF), `config.DOMAIN_OBJECTS` (Inventario). Las alertas dependen de que cada pipeline falle.

**Qué tendría.**
- Vistas unificadas sobre esas tablas y un reporte operativo (corridas, duración, filas, fallas, acierto del agente, tendencia de performance).
- Alertas con Activator o la alerta del pipeline, con un único canal (correo o Teams).
- SLA por `LOAD_GROUP`: a qué hora tiene que estar gold.
- Rol de Claude: skill de diagnóstico diario que lee las vistas y escribe el parte ("qué falló, causa probable, si se puede reintentar"), extendiendo lo que ya hace `metadata-medallion` con el log.

## 3. Seguridad y acceso a los datos

**Problema.** `NB_PRF_01` y `NB_DOC_01` detectan PII y MDP la saca de los rechazos y de gold, pero no hay un modelo de permisos: quién lee cada capa, RLS en el modelo semántico, CLS en las vistas del agente, etiquetas de sensibilidad.

**Qué tendría.**
- Matriz de roles por capa (bronze solo ingeniería, silver analistas, gold y `agente.*` negocio) con grupos de Entra ID.
- RLS en el modelo semántico y OneLake security / permisos del SQL endpoint en el lakehouse [verificar estado de GA de OneLake security].
- Etiquetas de sensibilidad (Purview Information Protection) a partir de `IS_PII` y `perfil.columna.pii`.
- Revisión periódica de accesos con el inventario de items.
- Rol de Claude: skill que propone la matriz y los scripts de permisos a partir de la metadata, para revisión.

## 4. Calidad y reconciliación

**Problema.** `meta.DQ_RULE` valida filas en silver. No hay controles de totales contra el origen, de integridad entre hechos y dimensiones en gold, ni de frescura.

**Qué tendría.** Reglas de reconciliación (conteos y sumas origen vs. silver vs. gold por período), reglas entre tablas en gold, umbrales de frescura, resultados en `log` o en un esquema `dq`, y alertas vía Monitoreo. Reusa el perfil de PRF para proponer las reglas.

## 5. Historia: SCD tipo 2 y bajas en el origen

**Problema.** Silver hace `MERGE` (SCD 1). Si un cliente cambia de zona, gold pierde a qué zona pertenecía cuando compró. Las filas borradas en el origen quedan vivas en silver.

**Qué tendría.** Nuevos modos en `meta.ENTITY` (`SILVER_MODE = 'SCD2'`, columna de baja lógica que PRF ya detecta como `candidata_baja_logica`), cambios en `NB_MDP_20_silver` y pruebas locales. Es una **extensión de MDP**, no un caso aparte: podría ir como PR sobre esa carpeta.

## 6. Catálogo y linaje

**Problema.** Ya hay inventario de items, metadata del pipeline, perfil del origen y diccionario del modelo, pero cada uno en su tabla.

**Qué tendría.** Vistas que unan `config.DOMAIN_OBJECTS` + `meta.ENTITY/GOLD_OBJECT` + `perfil.*` + `doc_diccionario` en un linaje *origen → bronze → silver → gold → modelo → reporte*, con la opción de publicarlo en Microsoft Purview. Depende del desvío 5 de convenciones (una sola base de control simplifica mucho).

## 7. Costos y capacidad

**Problema.** Todas las cargas, evaluaciones del agente y mediciones de performance consumen la misma capacidad. No hay forma de ver cuánto cuesta cada una.

**Qué tendría.** Lectura de la app *Fabric Capacity Metrics*, consumo por item y por `LOAD_GROUP`, recomendaciones de horario y de SKU. [verificar cómo exponer hoy esos datos fuera de la app].

## Lo que no propongo

- **Un framework de ingesta en tiempo real** (Eventstream / Eventhouse): no hay ningún caso que lo pida todavía.
- **Un framework para Databricks**: el contexto actual es Fabric; si aparece, se arma como variante de MDP.

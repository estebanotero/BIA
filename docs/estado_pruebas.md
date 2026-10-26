# Estado de prueba de cada caso

**En corto:** todos los casos con lógica propia tienen prueba local, y ninguno se probó todavía en Fabric real. Antes de usar uno en un cliente, probalo en un workspace de desarrollo.

Estado al 2026-10-26.

| Caso | Probado localmente | Probado en Fabric real |
|---|---|---|
| Inventario_Workspace | — | No: la versión v2 y el stored procedure sin ejecutar [dato a confirmar] |
| Perfilado_Origen_Medallion | Sí, `pruebas/prueba_local.py` (Spark 3.5.3 + Delta 3.2.1) | No |
| Pipeline_Metadata_Medallion | Sí, notebooks con `pruebas/prueba_local.py`; SCD2 y bajas con `pruebas/prueba_scd2_bajas.py` | No: pipeline y stored procedures sin ejecutar |
| Calidad_Reconciliacion | Sí, lógica del notebook y reglas de ejemplo en Spark 3.5.3 | No: T-SQL y actividades del pipeline sin ejecutar |
| Documentar_Modelo_Semantico | — | No |
| Performance_Modelo_Semantico | Sí, lógica de los notebooks | No |
| Agente_Datos_Fabric | Sí, reglas del banco y MCP contra un agente simulado | No: SDK y vistas sin ejecutar |
| Despliegue_Entre_Ambientes | Sí, scripts y workflows con el validador real de fabric-cicd 1.4.0 | No: sin despliegue real, login OIDC ni conexión a la base |
| Monitoreo_Plataforma | Sí, las reglas del notebook con situaciones armadas | No: script SQL, JDBC y avisos sin ejecutar |
| Seguridad_Acceso_Datos | Sí, PII, matrices, scripts generados y revisión con datos armados | No: consultas al endpoint y scripts de permisos sin ejecutar |
| Catalogo_Linaje | Sí, funciones sin Spark y notebook completo con Spark 3.5.3 + Delta | No: T-SQL, lectura de reportes con sempy y origen de las tablas en TOM sin ejecutar |

Las pruebas locales corren en cada PR con [`.github/workflows/pruebas.yml`](../.github/workflows/pruebas.yml). Probá siempre primero en un workspace de desarrollo.

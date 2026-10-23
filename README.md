# BIA: Ingeniería y Arquitectura de Datos

Repositorio de documentación técnica y soluciones reutilizables para tareas de
**Ingeniería de Datos** y **Arquitectura de Datos**. Aquí se irán documentando
los trabajos que surjan, junto con sus decisiones, instrucciones y artefactos
para que puedan entenderse, ejecutarse y mantenerse.

## Contenido

| Tema | Descripción |
|---|---|
| Ingeniería de datos | Ingesta, transformación, calidad, almacenamiento, orquestación y operación de datos |
| Arquitectura de datos | Diseño de soluciones, integración, modelado, gobierno, seguridad y decisiones técnicas |
| Casos y procedimientos | Guías paso a paso, scripts, notebooks, diagramas y validaciones asociados a tareas concretas |

### Casos documentados

- [Inventario de items de un workspace de Microsoft Fabric](Inventario_Workspace/README.md): sincronización del inventario con una SQL database, usando staging y `MERGE` para conservar IDs y registrar bajas lógicas.

## Cómo usar este repositorio

1. Empezá por el README del caso para entender el objetivo, los requisitos y el flujo.
2. Revisá los scripts y notebooks antes de ejecutarlos; completá los valores de configuración indicados para tu entorno.
3. Probá los cambios en desarrollo y validá sus efectos antes de aplicarlos en producción.
4. Consultá la sección de seguridad y las advertencias de cada procedimiento antes de manejar credenciales o datos reales.

## Estructura

```text
BIA/
├── README.md
└── Inventario_Workspace/
    ├── README.md
    ├── NB_Workspace_inventory_v2.ipynb
    └── sql/
        └── 01_ddl_domain_objects.sql
```

Cada solución se organiza en una carpeta propia. Cuando sea útil, incluirá:

- `README.md` con contexto, requisitos, pasos y validación.
- Código o scripts ejecutables, con parámetros claramente identificados.
- Notebooks y diagramas relacionados con el caso.
- Advertencias sobre operaciones con impacto y pasos de reversión.

## Convenciones

- Documentar el problema y el resultado esperado antes de los pasos técnicos.
- Indicar servicios, permisos, dependencias y configuración necesaria.
- Usar marcadores descriptivos para valores específicos del entorno; no publicar secretos, tokens ni datos sensibles.
- Diferenciar explícitamente los pasos de lectura, escritura y los que modifican o eliminan datos.
- Incluir validaciones, limitaciones y, cuando corresponda, cómo volver atrás.
- Mantener los nombres de carpetas claros y relacionados con el caso.

## Alcance y responsabilidad

La documentación es una base de trabajo que debe revisarse frente al entorno,
las políticas y las versiones de las herramientas utilizadas. Los ejemplos no
reemplazan la revisión técnica ni la aprobación necesaria para ejecutar cambios
en ambientes compartidos o productivos.

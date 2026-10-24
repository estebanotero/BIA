---
name: documentar-modelo-semantico
description: Documenta un modelo semántico de Microsoft Fabric / Power BI a partir del modelo.json que genera NB_DOC_01. Completa descripciones.csv y arma el diccionario de datos con diagrama ER. Usar cuando se pida documentar un modelo semántico, sus tablas, columnas o medidas.
---

# Documentar un modelo semántico de Fabric

Entrada: `modelo.json` y `descripciones.csv` de `Files/doc_modelos/<modelo>/` (los genera `NB_DOC_01_extraer_modelo`).
Si en cambio tenés el Power BI Modeling MCP conectado, leé el modelo con sus herramientas en modo solo lectura y seguí los mismos pasos.

1. Leé el modelo completo antes de escribir: tablas, relaciones y medidas. Identificá hechos, dimensiones, claves y granularidad.
2. Completá en `descripciones.csv` las columnas `descripcion_nueva` y `sensibilidad`, una fila por tabla, columna y medida:
   - Una o dos oraciones en español rioplatense, para un usuario de negocio que arma reportes.
   - Tablas: qué representa una fila (granularidad) y de dónde viene si se sabe.
   - Columnas clave o de relación: con qué tabla se relacionan.
   - Medidas: qué calculan en palabras, a partir de la expresión DAX; no repitas la fórmula.
   - Sensibilidad: `Pública`, `Interna` o `Sensible`. Si la fila ya dice `Sensible`, no la bajes.
3. Si los metadatos no alcanzan para saber qué significa algo, escribí `[dato a confirmar]`; no lo inventes.
4. No cambies `descripcion_actual` ni `revisado`: `revisado = si` lo pone una persona después de revisar.
5. No copies valores de columnas sensibles en ningún texto.
6. Si te piden el diccionario sin pasar por el notebook, completá `plantillas/diccionario.md`, con el diagrama ER en Mermaid armado desde `relaciones`.
7. Al final, informá cuántos objetos quedaron con `[dato a confirmar]` y qué preguntas harían falta para cerrarlos.

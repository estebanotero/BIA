[[_TOC_]]

Introduccion
------------
> Validación y Refinamiento del Plan para la Construcción de un Agente de Soporte en Fabric y Power BI

Durante las últimas semanas fui revisando documentación del proyecto, backlog, Wiki, minutas, reuniones y conversaciones relacionadas con el trabajo que estamos realizando en YPFL. A partir de esa información armé un primer borrador con las actividades que, a mi entender, estarán concentrando gran parte del esfuerzo durante los próximos meses para @<F1E8CCCB-89D6-60B5-BF1C-3CB0530D903B> y @<DADF52E1-708A-6F72-A8A7-5C55F93D3144>.

El objetivo de este documento no es definir cómo debe trabajar cada persona ni realizar una estimación formal del proyecto. El objetivo es mucho más práctico: **entender en detalle cómo trabajamos hoy para poder diseñar un agente especializado en Fabric y Power BI que ayude a acelerar tareas reales del día a día**.

Para que ese agente sea útil, no alcanza con conocer las actividades generales del proyecto. Necesitamos comprender:
*   Qué tareas concretas realizan.
*   Cómo las ejecutan actualmente.
*   Qué información necesitan para llevarlas adelante.
*   Qué entregables generan.
*   Qué validaciones realizan antes de dar un trabajo por terminado.
*   Qué partes consumen más tiempo o esfuerzo.
*   Qué actividades consideran repetitivas, tediosas o susceptibles de ser asistidas por IA.

Por ese motivo les pido que tomen este documento como un **primer borrador abierto a revisión**.

Les agradecería especialmente que puedan:
*   Corregir cualquier interpretación incorrecta.
*   Agregar actividades que hoy no estén reflejadas.
*   Eliminar tareas que no formen parte de su trabajo real.
*   Ajustar descripciones, prioridades o secuencias de trabajo.
*   Identificar dependencias, riesgos o consideraciones que no hayan sido incluidas.
*   Señalar claramente qué aspectos les generan más carga operativa o cognitiva.
*   Proponer ideas de asistencia que consideren valiosas para un futuro agente.

La intención es que este material represente la realidad lo mejor posible. Cuanto más preciso sea el diagnóstico del trabajo cotidiano, mejores serán los resultados al momento de definir skills, capacidades, fuentes de información y automatizaciones para el agente.

En otras palabras, **la meta no es documentar el proyecto; la meta es entender el trabajo para poder amplificarlo mediante IA**.

A partir de las observaciones y correcciones que surjan de esta revisión construiremos una versión refinada que servirá como insumo para definir los primeros casos de uso, skills y capacidades del agente.

Mi lectura del trabajo que tienen por delante
------------------------------------------------

Siento que deberíamos hacer centro primero en **CAMMESA**, porque es el frente donde el trabajo de ambos está más definido. SAP todavía depende de una decisión del cliente sobre Crestone, otro proveedor o archivos manuales, por lo que yo lo pondría como bloque condicionado y no como compromiso cerrado.

### @<F1E8CCCB-89D6-60B5-BF1C-3CB0530D903B>: frente de ingeniería de datos

Para los próximos dos meses, hoy le veo estas tareas:

1.  **Completar la incorporación de las tablas de CAMMESA**
    *   Terminar el pasaje de las tablas pendientes de Bronze a Silver.
    *   Identificar qué tablas son realmente necesarias para los indicadores priorizados.
    *   Mantener la trazabilidad entre archivo, tabla, transformación y consumo posterior. En la última información disponible, todas las tablas estaban en Bronze y alrededor de 30 de más de 40 ya estaban en Silver.

2.  **Robustecer la lectura de los Excel de CAMMESA**
    *   Adaptar el código a cambios de encabezados, columnas y posiciones.
    *   Detectar tablas sin nombre o con estructuras diferentes entre meses.
    *   Evitar posiciones y nombres hardcodeados.
    *   Comparar especialmente julio, agosto y septiembre, porque ya se detectaron cambios de estructura entre períodos.

3.  **Agregar controles operativos**
    *   Validar estructura antes de procesar.
    *   Detener el pipeline cuando cambian columnas, encabezados o cantidad de campos.
    *   Generar una alerta en Teams para que una persona revise el caso.
    *   Registrar el motivo del fallo y el archivo afectado.

    Esto no debe presentarse como calidad integral de datos, que está fuera del alcance, sino como **control de estructura y prevención de procesamiento incorrecto**.

4.  **Cerrar el flujo de ingesta**
    *   Descarga o recepción del archivo.
    *   Depósito en el SharePoint dedicado.
    *   Shortcut o mecanismo de acceso desde Fabric.
    *   Procesamiento con Pandas.
    *   Persistencia en Bronze, Silver y tablas de consumo.
    *   Replicación posterior en el tenant de YPF Luz cuando se habilite Fabric.

    La solución vigente trabaja con archivos porque la API fue descartada como fuente equivalente. Además, Pandas debió utilizarse para preservar los decimales reales de los Excel.

5.  **Documentar y dejar reproducible la ingeniería**
    *   Explicar notebooks, parámetros, tablas de configuración y dependencias.
    *   Documentar qué ocurre cuando aparece un archivo con una estructura nueva.
    *   Generar inventario de artefactos.
    *   Preparar una guía de despliegue o réplica desde el entorno de BIA hacia YPF Luz.

6.  **Apoyar la definición técnica de SAP**
    *   Solo cuando el cliente confirme si utilizará Crestone, otro conector o archivos manuales.
    *   Traducir esa definición en tareas, objetos, tablas y esfuerzo.
    *   No empezar a construir un flujo SAP abierto hasta tener el mecanismo confirmado.

### @<DADF52E1-708A-6F72-A8A7-5C55F93D3144>: frente analítico

Para ella veo estas tareas:

1.  **Revisar y clasificar los indicadores priorizados**
    *   Identificar cuáles pueden resolverse con las tablas disponibles.
    *   Separar indicadores simples, intermedios y complejos.
    *   Detectar cuáles dependen de fuentes manuales o de archivos todavía no disponibles.
    *   Registrar dudas funcionales y decisiones pendientes.

    El universo mencionado llegó a 80 indicadores, pero no todos son simples ni independientes. Varios requieren métricas auxiliares, fuentes adicionales o análisis previo.

2.  **Construir y ajustar el modelo dimensional**
    *   Identificar hechos, dimensiones, granularidad y relaciones.
    *   Validar si realmente puede aplicarse un esquema estrella a todos los bloques.
    *   Diferenciar lo que pertenece al Warehouse de lo que debe quedar fuera.
    *   Diseñar el modelo para los consumos priorizados, no como un Warehouse genérico de toda CAMMESA.

3.  **Desarrollar el modelo semántico**
    *   Crear y organizar medidas.
    *   Validar dependencias entre métricas.
    *   Definir nombres, descripciones, carpetas y formatos.
    *   Preparar el modelo para Power BI y para una futura utilización por agentes.
    *   Generar documentación de medidas y relaciones.

4.  **Continuar con el reporte de validación y el dashboard demostrativo**
    *   Utilizarlo para comparar resultados contra los Excel validados por el usuario.
    *   Incorporar identidad visual de YPF Luz cuando estén disponibles los lineamientos.
    *   Construir inicialmente las páginas necesarias para validar, sin sobredimensionar el dashboard.

5.  **Preparar pruebas funcionales y UAT**
    *   Definir qué debe validar el usuario.
    *   Indicar filtros, períodos y resultados esperados.
    *   Vincular cada validación con el archivo o fuente de referencia.
    *   Registrar aceptación, observaciones y ajustes solicitados.

6.  **Documentar el modelo y el consumo**
    *   Descripción de indicadores.
    *   Fórmula y dependencias.
    *   Fuente o tablas involucradas.
    *   Supuestos.
    *   Limitaciones.
    *   Instrucciones para validar y utilizar el reporte.

### Trabajo conjunto de ambos

Además de sus responsabilidades individuales, hay un bloque que necesariamente deben trabajar juntos:
*   Mapear cada indicador a las tablas requeridas.
*   Determinar si la información se encuentra disponible.
*   Identificar métricas auxiliares.
*   Definir granularidad e historización.
*   Revisar el encadenamiento Bronze → Silver → Warehouse → modelo semántico → Power BI.
*   Estimar esfuerzo usando el backlog real.
*   Preparar el traslado al tenant de YPF Luz.
*   Mantener Original Estimate y Remaining Work actualizados en cada tarea del backlog.

* * *

Qué parece pesarles hoy
--------------------------

No lo presento como una evaluación sobre ellos, sino como **hipótesis de fricción que necesitamos que validen**.

### Lo que probablemente le pesa a @<F1E8CCCB-89D6-60B5-BF1C-3CB0530D903B>

*   Analizar manualmente Excel que cambian entre meses.
*   Descubrir dónde empiezan las tablas y cómo se llaman.
*   Adaptar repetidamente notebooks a variaciones de estructura.
*   Pasar y verificar decenas de tablas entre capas.
*   Documentar posteriormente lo que ya construyó.
*   Replicar artefactos entre el tenant de BIA y el de YPF Luz.
*   Trabajar con definiciones técnicas del cliente que cambian o llegan incompletas.
*   Coordinar accesos y trabajar con las restricciones de las cuentas de YPF Luz.

### Lo que probablemente le pesa a @<DADF52E1-708A-6F72-A8A7-5C55F93D3144>

*   Entender indicadores sin tener completas las fuentes o definiciones.
*   Descubrir dependencias recién mientras construye cada métrica.
*   Estimar fechas antes de terminar el análisis funcional.
*   Crear muchas medidas repetitivas.
*   Mantener documentación alineada con un modelo que todavía evoluciona.
*   Validar métricas una por una contra Excel.
*   Preparar reportes de validación además del dashboard final.
*   Transformar requerimientos ambiguos en un modelo dimensional concreto.

### Fricciones compartidas

*   No siempre está claro qué está definitivamente decidido.
*   SAP todavía tiene un alcance incierto.
*   La disponibilidad de Fabric en YPF Luz sigue condicionando la réplica y el despliegue.
*   Hay presión por llegar antes del cierre de año con dedicación parcial.
*   El número “80 indicadores” oculta complejidades y dependencias muy diferentes.
*   Parte del trabajo técnico se hace hoy en el tenant de BIA y después deberá trasladarse.

* * *

Tarea Pendiente
===============

Esto es un borrador mío y seguramente hay cosas incompletas o mal interpretadas. Les pido que me ayuden a corregirlo y, para cada bloque, me indiquen:

1.  **Qué tarea concreta tienen que realizar.**
2.  **Cómo la hacen hoy, paso por paso.**
3.  **Qué parte les lleva más tiempo o resulta más tediosa.**
4.  **Qué información necesitan para empezar.**
5.  **Qué resultado o artefacto deben producir.**
6.  **Qué validaciones hacen antes de darla por terminada.**
7.  **Qué parte confiarían a un agente y qué parte necesariamente quieren revisar ustedes.**
8.  **Qué repositorios, carpetas, notebooks, PBIP, TMDL, archivos o páginas de Wiki debería poder consultar el agente.**

No necesito una descripción perfecta. Me sirve que lo bajen al día a día, por ejemplo:

> “Recibo el Excel de CAMMESA, comparo las columnas con el mes anterior, identifico encabezados, ajusto el notebook, ejecuto, verifico conteos y paso las tablas a Silver. Lo más pesado es detectar manualmente qué cambió y adaptar el código”.

O:

> “Tomo un indicador priorizado, busco qué tablas lo alimentan, reviso si están disponibles, creo las medidas DAX, comparo contra Excel y documento el cálculo. Lo más pesado es descubrir dependencias y repetir la documentación”.

Con esa información vamos a armar una primera versión del agente, usarla con trabajo real y medir si efectivamente les ahorra tiempo. Obviamente consumirá créditos de Copilot, pero quiero que esos créditos se usen sobre tareas reales y repetitivas donde podamos verificar el beneficio.

La idea es que el agente los ayude a ganar músculo y velocidad, no que tome decisiones técnicas o funcionales sin revisión de ustedes.


Cómo convertiría sus respuestas en skills
--------------------------------------------

A partir de este borrador, yo diseñaría inicialmente estos seis skills:

1.  **CAMMESA File Inspector**
    *   Compara archivos de dos períodos.
    *   Detecta cambios de columnas, encabezados, rangos y tipos.
    *   Genera el informe de impacto y propone ajustes al notebook.

2.  **Fabric Notebook Reviewer**
    *   Analiza notebooks y pipelines del repositorio.
    *   Detecta código hardcodeado, duplicación, falta de manejo de errores y parámetros.
    *   Propone refactor, pruebas y documentación.

3.  **Backlog Builder**
    *   Lee el plan y los artefactos técnicos.
    *   Sugiere tareas, subtareas, criterios de aceptación, dependencias y estimaciones preliminares.
    *   Nunca modifica automáticamente la estimación sin validación humana.

4.  **Indicator Lineage Assistant**
    *   Recibe un indicador.
    *   Busca tablas, columnas, medidas auxiliares y dependencias.
    *   Genera una ficha: definición, fuente, transformación, responsable y validación.

5.  **Semantic Model Reviewer**
    *   Analiza PBIP/TMDL.
    *   Revisa relaciones, cardinalidad, modelo estrella, medidas, nombres y descripciones.
    *   Sugiere DAX, documentación y pruebas, sin reemplazar DAX Studio ni Performance Analyzer.

6.  **Documentation and UAT Generator**
    *   Produce documentación técnica y funcional desde notebooks, TMDL y decisiones registradas.
    *   Genera casos de prueba y checklist de UAT.
    *   Marca claramente lo confirmado, lo inferido y lo pendiente.

Mi recomendación es **no empezar por los seis a la vez**. Empezaría por:
*   el inspector de archivos CAMMESA;
*   el revisor de notebooks;
*   el asistente de indicadores/modelo semántico.

Son los tres que atacan más directamente las fricciones visibles de noviembre y diciembre. La documentación y el backlog pueden sumarse como segunda iteración.

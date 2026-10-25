[[_TOC_]]

[[_TOSP_]]

# BIA Time Agent

En Data Analytics venimos recorriendo un camino progresivo para llevar la Inteligencia Artificial desde la conversación y la experimentación hacia situaciones concretas de nuestro trabajo diario.

- Primero comprendimos qué es MCP.

- Después conectamos GitHub Copilot con Redmine.

- Luego comenzamos a utilizar lenguaje natural para buscar proyectos, consultar issues y registrar horas.

- El paso siguiente es convertir esa experiencia en una capacidad reutilizable, especializada y gobernada.

**BIA Time Agent** es el primer agente especializado de Data Analytics construido sobre este recorrido.

> **BIA Time Agent** ayuda a cada colaborador a identificar, revisar y registrar correctamente sus horas en **Redmine** mediante lenguaje natural, utilizando reglas explícitas, herramientas autorizadas y confirmación humana cuando corresponde.

No buscamos que la IA cargue horas a ciegas. Buscamos reducir el esfuerzo administrativo sin perder precisión, trazabilidad, seguridad ni control.

## Dónde estamos hoy

| Versión | Qué hace | Estado |
|---|---|---|
| **MVP** | Registrar cargas a partir de un pedido en lenguaje natural, con confirmación. | En uso |
| **Fase 1a** | Decirte qué días te faltan cargar, contra tu jornada, sin contar fines de semana ni feriados, y qué licencias te falta cargar en BIA - Absentismo. | Disponible en `main` (versión 0.20.0). Probada en macOS; falta validar Windows |
| **Fase 1b** | Recuperar un período atrasado: propone cargas a partir de las reuniones de tu calendario. | Disponible en `main` (versión 0.20.0). Probada en macOS; falta validar Windows |

> **Nota:** al MVP también lo llamamos **Fase 0**: lo mínimo y necesario sobre lo que se construyó todo lo demás.

## Cómo seguir

| Si querés... | Leé |
|---|---|
| Entender por qué arrancamos con un MVP | **MVP** |
| Saber qué puede hacer el agente hoy | **Capacidades** |
| Entender cómo está construido | **Arquitectura** |
| Instalarlo y empezar a usarlo | **Instalación y uso** |
| Conocer las decisiones, las pruebas y lo que viene | **Evolución** |

# Problema que queremos resolver

La **carga de horas** es una actividad necesaria, pero también **repetitiva**. En el trabajo cotidiano aparecen situaciones como estas:

- Sabemos qué actividad realizamos, pero no recordamos el ID del issue.
- Recordamos el cliente o proyecto, pero no dónde corresponde registrar el tiempo.
- Llegamos al final de la semana y tenemos que reconstruir qué hicimos cada día.
- Queremos comprobar si completamos la jornada esperada.
- Necesitamos revisar las cargas antes de registrarlas.
- Debemos distinguir entre información confirmada, inferida y todavía pendiente.

El **problema** no consiste solamente en seleccionar una opción en Redmine. El **verdadero esfuerzo** está en reconstruir el contexto, identificar el issue correcto, completar los datos necesarios y verificar que la operación se haya realizado correctamente.

**BIA Time Agent** busca simplificar ese recorrido.

![image.png](../.attachments/image-e6d7a576-986d-4075-9d9c-f84d75b7c624.png)

# Por qué importa
> Por qué importa registrar correctamente las horas

La carga de horas no existe solamente para completar una obligación administrativa. Las horas registradas ayudan a BIA a:

- Entender el esfuerzo real de cada proyecto.
- Analizar la rentabilidad de clientes e iniciativas.
- Mejorar las estimaciones de futuras propuestas.
- Planificar capacidad y asignaciones.
- Detectar desvíos entre esfuerzo previsto y esfuerzo real.
- Contar con evidencia sobre las actividades realizadas.
- Evitar reconstruir semanas completas utilizando únicamente la memoria.

La calidad de esta información depende de que las horas sean registradas en el proyecto, issue, fecha y actividad correctos.
Por eso el objetivo del agente no es solamente aumentar la velocidad de carga. El objetivo es ayudar a mejorar la calidad y la trazabilidad de la información registrada.

---

# Del MCP al agente

## Etapa 1: acceso a Redmine mediante MCP

El servidor MCP de Redmine pone a disposición herramientas para interactuar con Redmine.
Por ejemplo:

- Buscar proyectos.
- Consultar issues.
- Revisar entradas de tiempo.
- Registrar horas.

MCP define cómo GitHub Copilot descubre y utiliza esas herramientas.
La API de **Redmine** continúa siendo la interfaz técnica que finalmente consulta o modifica el sistema.

## Etapa 2: asistente mediante lenguaje natural

Una vez conectadas las herramientas, el colaborador puede expresar una intención:

    Cargame una hora hoy en el issue 12345 como meeting.

**GitHub Copilot** interpreta la solicitud, selecciona la herramienta correspondiente y prepara la operación.
Sin embargo, disponer de herramientas no alcanza para tener un agente especializado.

## Etapa 3: BIA Time Agent

**BIA Time Agent** incorpora una definición estable sobre:
*   Cuál es su propósito.
*   Qué operaciones puede realizar.
*   Qué información debe validar.
*   Cuándo debe solicitar confirmación.
*   Qué datos no puede inventar.
*   Qué herramientas puede utilizar.
*   Qué resultados debe mostrar.
*   Cuándo debe detenerse.
*   Qué situaciones quedan fuera de su alcance.

La diferencia puede resumirse así:
| Componente | Responsabilidad |
| --- | --- |
| API de Redmine | Expone las operaciones propias de Redmine |
| Servidor MCP | Presenta esas operaciones como herramientas para el agente |
| Skills | Describen cómo ejecutar correctamente una tarea |
| Definición del agente | Establece propósito, comportamiento, reglas y límites |
| Modelo de IA | Interpreta la intención y construye el plan de ejecución |
| Colaborador | Conserva la autoridad sobre las decisiones y acciones importantes |

* * *

Definición del agente
=====================

Propósito
---------

**BIA Time Agent** es un agente especializado de GitHub Copilot que asiste a los colaboradores de BIA para identificar, revisar y registrar correctamente sus horas en Redmine. Transforma una solicitud expresada en lenguaje natural en una propuesta verificable de carga.

El agente:
1.  Interpreta la actividad indicada por el colaborador.
2.  Identifica los datos recibidos.
3.  Determina qué información falta.
4.  Consulta las herramientas autorizadas que resulten necesarias.
5.  Prepara una propuesta.
6.  Distingue lo confirmado de lo inferido.
7.  Solicita confirmación cuando corresponde.
8.  Ejecuta la acción mediante el MCP de Redmine.
9.  Verifica el resultado real devuelto por Redmine.

![image.png](../.attachments/image-37c64ec5-c080-4864-8fe8-390d43290d46.png)

Misión
------

> Reducir al mínimo el esfuerzo necesario para registrar correctamente las horas en Redmine, sin inventar información ni perder trazabilidad, seguridad o control humano.

Especialización
---------------

**BIA Time Agent** no es un agente generalista de Redmine. Su especialización es:
*   Carga de horas.
*   Consulta de entradas propias.
*   Revisión de períodos.
*   Conciliación de horas.
*   Identificación de información faltante.
*   Preparación de propuestas verificables.

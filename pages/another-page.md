---
layout: default
title: Práctica 1 · Follow Line
description: Documentación técnica sobre las estrategias de control PID y visión artificial implementadas para el seguimiento de trayectoria
---

El objetivo de esta práctica es desarrollar un sistema de control autónomo capaz de mantener un vehículo sobre una línea en un circuito cerrado. Para lograr la optimización del tiempo de vuelta, el desarrollo se ha estructurado iterativamente, evolucionando desde un modelo puramente reactivo hasta una arquitectura predictiva.

Antes de detallar las aproximaciones de control, es fundamental definir el marco de evaluación utilizado para cuantificar el rendimiento del algoritmo.

---

### Métricas de Evaluación del Desempeño

Para evitar una sintonización empírica o subjetiva de las constantes del controlador, se han implementado dos métricas calculadas en tiempo real durante la ejecución. Estas evalúan tanto la precisión geométrica como la estabilidad dinámica del vehículo.

**1. Estabilidad de Trazada (RMSE)**
Evalúa la desviación promedio del vehículo respecto a la referencia ideal (el centro de la línea). Se calcula como la raíz cuadrada de la media de los errores laterales al cuadrado, penalizando severamente las salidas de pista o desviaciones lejanas.

**2. Oscilación y Esfuerzo de Control (Zigzag)**
Un RMSE bajo no garantiza un buen controlador si el vehículo mantiene la trayectoria a base de oscilaciones violentas. Para medir el balanceo en la dirección, se cuantifica la tasa de variación media de la señal de control de giro. Un valor elevado indica inestabilidad o un ajuste excesivo de la constante derivativa, mientras que un valor cercano a cero refleja una conducción suave.

---

### Vídeo Explicativo

<div style="text-align: center; margin-bottom: 20px;">
    <iframe width="100%" height="400" src="https://www.youtube.com/embed/vfVKAqjipJ4?si=BE4J4qIQncB-Hyj_" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>
</div>

---

### Aproximación 1: Control Reactivo por Centroide

La primera arquitectura implementada se basa en la localización del centro de masa de la segmentación de color. Es un enfoque puramente reactivo que evalúa el estado presente del vehículo.

**Lógica de Control:**
A través de los momentos espaciales de la imagen binarizada, se extrae la coordenada X del centroide (dividiendo el momento de primer orden entre la masa total de píxeles). El error lateral continuo es simplemente la diferencia entre el centro óptico de la cámara y esta coordenada X.

Este error alimenta directamente los controladores PID:

**Análisis del control de giro:**
* **Kp (Proporcional):** Es la respuesta principal al error. Define la agresividad con la que el coche busca el centro de la línea. Un valor alto reduce el error rápido pero introduce oscilaciones si no se amortigua correctamente.
* **Kd (Derivativo):** Actúa como un amortiguador de la dirección. Al medir la velocidad de cambio del error, predice el sobreviraje y aplica un "contravolante" justo antes de cruzar la línea de referencia. Es el componente clave para estabilizar el balanceo y reducir la métrica de Zigzag.
* **Ki (Integral):** Tiene como objetivo corregir desviaciones acumuladas en curvas de radio constante. En este escenario se mantiene en valores mínimos para evitar el fenómeno de inestabilidad por acumulación de error en cambios de dirección rápidos.

**Análisis del control de velocidad:**
Para el control longitudinal, se utiliza el valor absoluto del error lateral. Esto genera un "esfuerzo de frenado" que se resta a la velocidad máxima del vehículo, asegurando que decelere proporcionalmente a la severidad de la curva.
* **Kp (Proporcional):** Determina la frenada base. A medida que el vehículo detecta una desviación del centro, este componente reduce la velocidad de forma lineal. Permite que el coche negocie el ápice de la curva a una velocidad segura.
* **Kd (Derivativo):** Proporciona una capacidad de frenado reactivo ante cambios bruscos. Si el error aumenta repentinamente (entrada agresiva en curva), el término derivativo aumenta el esfuerzo de frenado inmediatamente, reduciendo la inercia antes de que el error sea crítico.
* **Ki (Integral):** Se omite deliberadamente para evitar el efecto de saturación (windup). Si se permitiera la acumulación del error durante una curva larga, el coche acabaría perdiendo demasiada velocidad o deteniéndose por completo.

### Configuración de Parámetros

Tras realizar las pruebas documentadas, se determinó que la siguiente configuración ofrece el mejor equilibrio entre velocidad y estabilidad para un control puramente reactivo:

| Parámetro | Kp | Kd | Vel Máx | Vel Mín | Tiempo (s) | mRMSE (px) | ZigZag |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Valor** | 0.005 | 0.08 | 11.0 | 2.0 | **59.0** | **108.0** | **0.198** |

> **Nota:** También es robusto a distintos mapas disponibles.

---

### Aproximación 2: Fusión Espacial y Frenada Predictiva (Look-ahead)

Para mitigar el retardo inercial y permitir velocidades punta mayores en las rectas, la segunda iteración desacopla la percepción espacial. Se evalúa simultáneamente el anclaje físico (presente) y un punto adelantado (futuro).

**Extracción del Punto Predictivo:**
Se aísla la fila de píxeles válidos más alta de la imagen detectada (la de menor coordenada Y), correspondiente a la mayor distancia en perspectiva, y se calcula su punto medio.

**Lógica de Control Desacoplada:**
La dirección y la velocidad se independizan lógicamente para evitar oscilaciones en la salida de las curvas y aceleraciones prematuras.

1.  **Dirección (Fusión Ponderada):** El vehículo se guía por un objetivo virtual que interpola el centroide y el punto lejano mediante un factor de peso. Esto proporciona un giro anticipado pero firmemente anclado a la trazada.
2.  **Velocidad (Feed-forward):** Se introduce un sesgo predictivo. La magnitud del error que alimenta al PID de frenada no depende solo de la inestabilidad actual, sino que suma la desviación geométrica que aporta el horizonte. Este esfuerzo de frenado se resta a la velocidad máxima, limitándose siempre por un tope mínimo de seguridad.

Esta formulación permite que el controlador reduzca la inercia lineal milisegundos antes de que el morro del chasis entre físicamente en la curva.


### Resultados de Rendimiento Versión Predictiva

Gracias al uso del punto de anticipación y el desacoplamiento de los controladores, se ha logrado incrementar la velocidad máxima sin perder la trazada. Se sacrifica una fracción de precisión posicional respecto al centro exacto de la línea, pero se mejora drásticamente la estabilidad direccional, obteniendo un avance sustancial en el tiempo de vuelta:

| Parámetro | Kp | Kd | Vel Máx | Vel Mín | Tiempo (s) | RMSE (px) | ZigZag |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Valor** | 0.005 | 0.08 | 15.0 | 2.0 | **48.0** | **130.5** | **0.145** |

---

### Trabajo Futuro: Optimización e Inteligencia Artificial

Para superar el límite de la sintonización manual, se proponen dos evoluciones que pasan de la ingeniería de control clásica a arquitecturas de aprendizaje automático.

- __Sintonización con Random Forest:__ Uso de un modelo de Random Forest para predecir y ajustar las constantes del controlador (Kp, Ki, Kd) idóneas para cada circuito en tiempo real.

- __Control End-to-End con Deep Reinforcement Learning:__ Sustitución total del PID por un agente entrenado. Una red neuronal convolucional (CNN) leería los píxeles y decidiría los comandos de aceleración y volante directamente. El modelo se entrenaría iterativamente mediante prueba y error, utilizando funciones de recompensa penalizadas por colisiones y guiadas por la minimización del MSE y el ZigZag.

---

[back](./)
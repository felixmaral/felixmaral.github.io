---
layout: default
title: Práctica 1 - Follow Line
description: Documentación técnica sobre las estrategias de control PID y visión artificial implementadas para el seguimiento de trayectoria.
---

## Documentación: P1 - Follow Line

El objetivo de esta práctica es desarrollar un sistema de control autónomo capaz de mantener un vehículo sobre una línea en un circuito cerrado. Para lograr la optimización del tiempo de vuelta, el desarrollo se ha estructurado iterativamente, evolucionando desde un modelo puramente reactivo hasta una arquitectura predictiva.

Antes de detallar las aproximaciones de control, es fundamental definir el marco de evaluación utilizado para cuantificar el rendimiento del algoritmo.

---

### Métricas de Evaluación del Desempeño

Para evitar una sintonización empírica o subjetiva de las constantes del controlador, se han implementado dos métricas matemáticas calculadas en tiempo real durante la ejecución. Estas evalúan tanto la precisión geométrica como la estabilidad dinámica del vehículo.

**1. Estabilidad de Trazada (RMSE)**
Evalúa la desviación promedio del vehículo respecto a la referencia ideal (el centro de la línea). Se utiliza el Error Cuadrático Medio Radicado (RMSE) para penalizar severamente las salidas de pista o desviaciones lejanas.

$$RMSE = \sqrt{\frac{1}{N} \sum_{i=1}^{N} e_i^2}$$

Donde $e_i$ es el error lateral medido en píxeles en el instante $i$, y $N$ es el número total de muestras.

**2. Oscilación y Esfuerzo de Control (Zigzag)**
Un RMSE bajo no garantiza un buen controlador si el vehículo mantiene la trayectoria a base de oscilaciones violentas. Para medir el balanceo en la dirección, se cuantifica la tasa de variación media de la señal de control ($W$).

$$Zigzag = \frac{1}{N-1} \sum_{i=2}^{N} |W_i - W_{i-1}|$$

Un valor elevado en esta métrica indica inestabilidad o un ajuste excesivo de la constante derivativa (ruido amplificado), mientras que un valor cercano a cero refleja una conducción suave.



---

### Aproximación 1: Control Reactivo por Centroide

La primera arquitectura implementada se basa en la localización del centro de masa de la segmentación de color. Es un enfoque puramente reactivo que evalúa el estado presente del vehículo.

**Formulación Matemática:**
A través de los momentos espaciales de la imagen binarizada ($M$), se extrae la coordenada horizontal del centroide ($c_x$):

$$c_x = \frac{M_{10}}{M_{00}}$$

El error lateral continuo se define respecto al centro óptico de la cámara ($C$):

$$e_w(t) = C - c_x(t)$$

Este error alimenta la ecuación del controlador PID discreto para calcular la velocidad angular ($W_k$):

$$W_k = K_{p_w} e_{w,k} + K_{d_w} (e_{w,k} - e_{w,k-1}) + K_{i_w} \sum_{j=0}^{k} e_{w,j}$$



**Análisis del control de giro ($W_k$):**
* **$K_{p_w}$ (Proporcional):** Es la respuesta principal al error. Define la agresividad con la que el coche busca el centro de la línea. Un valor alto reduce el error rápido pero introduce oscilaciones si no se amortigua correctamente.
* **$K_{d_w}$ (Derivativo):** Actúa como un amortiguador de la dirección. Al medir la velocidad de cambio del error, predice el sobreviraje y aplica un "contravolante" justo antes de cruzar la línea de referencia. Es el componente clave para estabilizar el balanceo y reducir la métrica de **Zigzag**.
* **$K_{i_w}$ (Integral):** Tiene como objetivo corregir desviaciones acumuladas en curvas de radio constante. En este escenario se mantiene en valores mínimos para evitar el fenómeno de inestabilidad por acumulación de error en cambios de dirección rápidos.

Para el control de la velocidad lineal ($V_k$), se utiliza el valor absoluto del error lateral. Esto genera un "esfuerzo de frenado" ($\Delta V$) que se resta a la velocidad máxima del vehículo, asegurando que decelere proporcionalmente a la severidad de la curva:

$$e_{v,k} = |e_{w,k}|$$

$$\Delta V_k = K_{p_v} e_{v,k} + K_{d_v} (e_{v,k} - e_{v,k-1}) + K_{i_v} \sum_{j=0}^{k} e_{v,j}$$

$$V_k = \max(V_{min}, V_{max} - \Delta V_k)$$



**Análisis del control de velocidad ($V_k$):**
* **$K_{p_v}$ (Proporcional):** Determina la frenada base. A medida que el vehículo detecta una desviación del centro (presencia de curva), este componente reduce la velocidad de forma lineal. Permite que el coche negocie el ápice de la curva a una velocidad segura.
* **$K_{d_v}$ (Derivativo):** Proporciona una capacidad de frenado reactivo ante cambios bruscos. Si el error aumenta repentinamente (entrada agresiva en curva), el término derivativo aumenta el esfuerzo de frenado inmediatamente, permitiendo que el coche reduzca su inercia antes de que el error lateral sea crítico.
* **$K_{i_v}$ (Integral):** Se omite deliberadamente ($0.0$) para evitar el efecto *windup*. Si se permitiera la acumulación del error durante el trazado de una curva larga, el coche acabaría perdiendo demasiada velocidad o deteniéndose por completo en medio del giro.

---

**Análisis de Resultados y Sintonización:**
Debido a que el centro de masa promedia toda la línea visible, el controlador sufre de "latencia espacial". La señal de error reacciona tarde a las curvas, requiriendo un ajuste meticuloso de las ganancias para evitar la salida de la vía.

> **[Espacio para Vídeo 1: Comportamiento Base]**
> *Descripción:* Ejecución del algoritmo reactivo con constantes conservadoras. Se observa la latencia en la entrada a la curva y la estabilización progresiva.

> **[Espacio para Vídeo 2: Impacto de la Constante Proporcional ($K_p$)]**
> *Descripción:* Comparativa métrica al incrementar $K_{p_w}$. Se evidencia una reducción en el RMSE, pero a costa de inducir un balanceo sostenido que degrada la estabilidad general y aumenta el Zigzag.

> **[Espacio para Vídeo 3: Amortiguación Derivativa ($K_d$)]**
> *Descripción:* Ajuste fino de $K_{d_w}$ frente a las oscilaciones. El vídeo muestra cómo un incremento controlado de la componente derivativa reduce drásticamente la métrica de Zigzag, estabilizando el vehículo frente a los cambios bruscos.

---

### Aproximación 2: Fusión Espacial y Frenada Predictiva (Look-ahead)

Para mitigar el retardo inercial y permitir velocidades punta mayores en las rectas, la segunda iteración desacopla la percepción espacial. Se evalúa simultáneamente el anclaje físico (presente) y un punto adelantado (futuro).



**Extracción del Punto Predictivo (Topmost):**
Se aísla la fila de píxeles válidos con la menor coordenada Y de la imagen, correspondiente a la mayor distancia en perspectiva.

$$c_{x,look} = \frac{1}{M} \sum x_j \quad \forall j \text{ tal que } y_j = \min(Y)$$

**Lógica de Control Desacoplada:**
La dirección y la velocidad se independizan matemáticamente para evitar oscilaciones en la salida de las curvas y aceleraciones prematuras.

1.  **Dirección (Fusión Ponderada):** El vehículo se guía por un objetivo virtual ($c_{x,target}$) que interpola el centroide y el punto lejano mediante un factor $\alpha$. Esto proporciona un giro anticipado pero firmemente anclado a la trazada.
    $$c_{x,target} = \alpha \cdot c_{x,look} + (1 - \alpha) \cdot c_{x,cm}$$

2.  **Velocidad (Feed-forward):** Se introduce un sesgo predictivo. La magnitud del error que alimenta al PID de frenada no depende solo de la inestabilidad actual con respecto a la referencia ($e_{cm}$), sino de la derivada geométrica que aporta el horizonte ($e_{look}$).
    $$e_{v,k} = |e_{cm,k}| + K_{anticipacion} \cdot |e_{look,k}|$$
    
    Este error predictivo alimenta un segundo controlador PID que calcula la reducción de velocidad ($\Delta V_k$), aplicándose a los motores de la siguiente manera:
    $$V_k = \max(V_{min}, V_{max} - PID(\Delta V_k))$$

Esta formulación permite que el controlador reduzca la inercia lineal milisegundos antes de que el morro del chasis entre en la geometría de la curva.

> **[Espacio para Vídeo 4: Ejecución Predictiva Avanzada]**
> *Descripción:* Demostración de la arquitectura Look-ahead con control desacoplado. Se aprecia la reducción predictiva de la velocidad instantes antes del vértice y la eliminación del balanceo durante el trazado interior, optimizando el tiempo global por vuelta.

---

### Trabajo Futuro: Optimización e Inteligencia Artificial

Para superar el límite de la sintonización manual, se proponen dos evoluciones que pasan de la ingeniería de control a la inteligencia pura.

#### 1. Sintonización con Random Forest (RF)
Uso de un modelo **Random Forest** para predecir las constantes ($K_p, K_i, K_d$) idóneo para cada circuito.

#### 2. Control End-to-End con RL (Deep Reinforcement Learning)
Sustitución total del PID por un agente entrenado. Una red neuronal (CNN) leería los píxeles y decidiría los comandos de gas y volante directamente. Se entrenaría iterativamente a base de prueba y error configurando unas funciones de recompensa guiadas por colisiones y las métricas MSE y ZigZag.

---

[back](./)
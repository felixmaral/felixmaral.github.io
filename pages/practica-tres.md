---
layout: default
title: "Práctica · Autolocalización Visual"
description: "Estimación de pose mediante PnP, Autolocalización con fusión odométrica, Navegación básica"
---

En esta práctica se desarrolla un sistema robusto de autolocalización global para un robot móvil utilizando balizas visuales. El pipeline combina la detección de marcadores, la resolución del problema de la perspectiva de *n* puntos (PnP) para la estimación de la pose de la cámara, transformaciones geométricas entre sistemas de referencia y una lógica híbrida que apoya la visión con estimaciones odométricas. Simultáneamente, el robot ejecuta un algoritmo de navegación reactiva para explorar el entorno y comprobar el funcionamiento de la autolocalización.

<p align="center">
  <img src="{{ site.baseurl }}/assets/img/loc_visual_result.png"
       alt="Resultado de la autolocalización y navegación"
       style="max-width: 100%; border-radius: 10px;">
</p>

### Navegación

Para que el robot explore el entorno y encuentre las balizas, se ha implementado un mecanismo de navegación reactiva basado en una máquina de estados finitos sencilla con dos estados: `RECTO` y `GIRO`.

El sistema procesa los datos del escáner láser (`HAL.getLaserData()`), segmentando las lecturas en tres sectores principales: frontal, izquierdo y derecho.

1.  **Estado RECTO**: El robot avanza con una velocidad lineal constante (`vel_lineal`). Si la lectura mínima del sector frontal cae por debajo del umbral de seguridad (`seguridad_frontal`), el robot se detiene y transita al estado `GIRO`.
2.  **Estado GIRO**: El robot gira sobre su eje vertical. La dirección de giro se decide dinámicamente evaluando qué sector lateral (izquierdo o derecho) presenta mayor espacio libre. El giro se mantiene hasta que el sector frontal vuelve a superar la distancia de seguridad.

**Experimentación:** Durante el desarrollo, se probaron distintas configuraciones de los parámetros para probar distintos resultados en la deambulación y así comprobar mejor el algoritmo de autolocalización, como objetivo de esta práctica. Posteriormente también se probaron distintos algoritmos de deambulación algo más complejos basados en los sensores y procesos aleatorios de giro.

### Transformaciones Geométricas

Para que la estimación de pose tenga sentido en el sistema global, es importante establecer las relaciones entre los distintos sistemas de coordenadas: el Mundo ($W$), la Cámara ($C$) y el Robot ($R$).

La cámara de OpenCV asume un sistema donde el eje X apunta a la derecha, el eje Y hacia abajo y el eje Z hacia adelante. El robot, sin embargo, utiliza X hacia adelante, Y a la izquierda y Z hacia arriba. Se realiza un cambio de base para compensar esta discrepancia.

Conociendo la transformación del robot respecto a la cámara ($T_{cr}$) y obteniendo la de la cámara respecto al mundo mediante visión ($T_{wc}$), la pose global del robot en el mundo se calcula componiendo las matrices de transformación homogénea:

$$
T_{wr} = T_{wc} \cdot T_{cr}
$$

### Estimación de Pose por Visión (PnP)

La autolocalización visual se basa en la correspondencia entre los puntos 3D de la baliza en el mundo y sus proyecciones 2D en el plano imagen, resolviendo el problema PnP mediante `cv2.solvePnP` en modo iterativo.

El proceso generaliza la ecuación de proyección geométrica:

$$
x \sim K [R \mid t] X
$$

Donde $X$ son las esquinas 3D del tag, $x$ son las esquinas 2D detectadas, y $K$ es la matriz de parámetros intrínsecos de la cámara. El algoritmo devuelve la rotación ($R$) y traslación ($t$) de la cámara respecto al marcador.

#### Múltiples Balizas
Cuando se detectan varios marcadores simultáneamente, el sistema mejora drásticamente la robustez agregando todas las correspondencias 3D-2D en un único sistema, forzando a `cv2.solvePnP` a encontrar una única pose de la cámara que minimice el error de reproyección conjunto de todas las balizas. Si la diferencia con el calculo de la baliza más cercana no difiere de un umbral, se pasa a calcular los siguientes frames calculando con la baliza más cercana (area de la detección)

### Odometría

La estimación visual pura puede sufrir de oclusiones o falsos positivos. Para dotar al sistema de memoria espacial y continuidad, se emplea la odometría del robot.

Cada vez que la visión reporta una pose válida y de alta confianza (basada en el error de reproyección y el salto geométrico), esta se guarda como un "ancla" ($T_{ancla}$). Si en instantes posteriores la visión es deficiente o nula, la pose actual ($T_t$) se predice componiendo el ancla con el incremento odométrico relativo desde que se tomó dicha ancla:

$$
T_{t} = T_{ancla} \cdot \left( T_{odom\_ancla}^{-1} \cdot T_{odom\_actual} \right)
$$

**Mecanismo de Selección:**
El flujo de ejecución decide la pose final ponderando las fuentes:
1.  Si hay solución Multi-Tag válida, tiene máxima prioridad por su estabilidad geométrica.
2.  Si la solución de un solo Tag es válida y no difiere excesivamente (`max_diff_hibrida`) de la solución multi-tag (si existe), se prioriza. Las validaciones incluyen comprobar que la estimación visual no supone un salto físicamente imposible respecto a la predicción odometría (`max_salto`, `max_salto_yaw`).
3.  En ausencia de detecciones visuales que superen los umbrales de validación, el sistema degrada de manera segura confiando en la predicción odometría.

## Parámetros de Configuración

| Parámetro | Valor | Función |
| :--- | :---: | :--- |
| `tam_tag` | 0.24 | Tamaño real del lado del AprilTag en metros. |
| `seguridad_frontal` | 2 | Umbral de distancia (metros) para activar la evasión de obstáculos. |
| `max_error` | 8.0 | Límite máximo del error de reproyección (píxeles) para aceptar una pose PnP. |
| `max_salto` | 2.0 | Distancia lineal máxima permitida entre la predicción y la medición visual. |
| `max_diff_hibrida` | 1.0 | Divergencia máxima aceptada entre la estimación de un tag y de múltiples tags. |

## Resultados y Observaciones

Mientras que la odometría acumula error con el tiempo, la visión actúa como un corrector que anula este error sistemático. A su vez, la odometría filtra los saltos espurios inherentes a la estimación  de marcadores lejanos.

A continuación se muestra el comportamiento del robot en el simulador, donde se aprecia como la estimacióninicial al estar alejado de las balizas es buena en orientación pero no tanto en distancia a la baliza. Tras avanzar se va corrigiendo la posición estimada debido a que aumenta la precisión del cálculo al utilizar detecciones más grandes. Cuando no se detectan balizas la estimación odométrica permite continuar con la estimación relativamente bien. En la primera imagen de esta documentación se puede observar como en el tramo final mantiene una estimación precisa solo con la estimación odométrica a partir de la ultima estimación visual.

<p align="center">
  <img src="{{ site.baseurl }}/assets/img/estimacion.png"
       alt="Resultado de la autolocalización y navegación"
       style="max-width: 100%; border-radius: 10px;">
</p>

---
layout: default
title: "Práctica 2 · Reconstrucción 3D por Visión Estéreo"
description: "Geometría epipolar, block matching con NCC y triangulación 3D"
---

En esta práctica se desarrolla un pipeline de reconstrucción 3D a partir de un par estéreo. El sistema combina preprocesado de imagen, detección de bordes como píxeles de interés, búsqueda de correspondencias sobre la geometría epipolar y triangulación proyectiva para generar una reconstrucción en forma de nube de puntos.

<p align="center">
  <img src="{{ site.baseurl }}/assets/img/image_3d.png"
       alt="Resultado final de la reconstrucción 3D"
       style="max-width: 100%; border-radius: 10px;">
</p>

Cada cámara se modela mediante una matriz de proyección compuesta por parámetros intrínsecos y extrínsecos. Esta formulación permite relacionar un punto 3D de la escena con su proyección sobre el plano imagen de cada cámara.

$$
P = K[R \mid t]
$$

$$
x \sim P X
$$


### Preprocesado

Este apartado en este contexto no es necesario ya que partimos de un simulador en el que no existen condiciones que generen ruido en las imágenes capturadas, pero son buenas prácticas en el contexto de la extracción precisa de bordes. Cada imagen se procesa para mejorar la calidad de los bordes y aumentar la estabilidad de las comparaciones locales:

- Se aplica CLAHE sobre el canal de luminancia para mejorar el contraste local.
- Después se usa un filtro bilateral para reducir ruido sin degradar contornos.
- Finalmente la imagen se convierte a escala de grises.

Este paso mejora la estabilidad del matching en zonas con iluminación irregular, textura poco uniforme y cambios locales de contraste.

### Extracción de bordes

Sobre las imágenes preprocesadas se aplica el detector de Canny. Los píxeles de borde de la imagen izquierda actúan como puntos candidatos, mientras que los bordes de la derecha restringen las zonas donde merece la pena evaluar correspondencias.

<p align="center">
  <img src="{{ site.baseurl }}/assets/img/bordes-3d.jpg"
       alt="Resultado final de la reconstrucción 3D"
       style="max-width: 100%; border-radius: 10px;">
</p>

Para reducir coste computacional, no se usan todos los bordes, sino un subconjunto submuestreado. Esta decisión permite disminuir el número de comparaciones sin alterar de forma significativa la estructura global de la nube reconstruida.

### Cálculo de la línea epipolar

Para cada borde candidato de la imagen izquierda:

1. Se retroproyecta el píxel a un rayo 3D con `HAL.backproject`.
2. Ese rayo se proyecta sobre la cámara derecha con `HAL.project`.
3. A partir de dos puntos proyectados del mismo rayo se obtiene la recta epipolar.

De esta manera, la búsqueda del homólogo deja de hacerse en toda la imagen derecha y queda restringida a una única trayectoria geométrica compatible con la escena. La restricción epipolar reduce el espacio de búsqueda de dos dimensiones a una dimensión.

$$
l' = F x
$$

En esta expresión, $$x$$ representa un punto en la imagen izquierda, $$l'$$ su recta epipolar en la imagen derecha y $$F$$ la matriz fundamental asociada al sistema estéreo.

### Búsqueda del homólogo

Una vez conocida la línea epipolar:

- Se extrae un parche centrado en el punto de la imagen izquierda.
- Se recorre la línea epipolar en la imagen derecha.
- Solo se evalúan posiciones que también sean borde.
- En cada candidato se compara el parche izquierdo con el derecho usando correlación normalizada NCC.
- Se conserva el candidato con mayor puntuación.
- Si la puntuación supera el umbral fijado, la correspondencia se acepta como homólogo válido.

Este criterio permite priorizar precisión frente a densidad, reduciendo falsos positivos.

$$
\text{NCC}(A,B) = \frac{\sum (A-\bar{A})(B-\bar{B})}{\sqrt{\sum (A-\bar{A})^2 \sum (B-\bar{B})^2}}
$$

### Triangulación

Con los pares de puntos homólogos válidos se aplica triangulación lineal mediante `cv2.triangulatePoints`. El resultado son coordenadas homogéneas 3D que después se normalizan y filtran por profundidad para eliminar puntos espurios o geométricamente inconsistentes.

$$
X_c = \text{triangulate}(P_L, P_R,\, x_L, x_R)
$$

$$
X_c = \begin{bmatrix} X \\ Y \\ Z \\ W \end{bmatrix}
\quad \Rightarrow \quad
\left(\frac{X}{W},\, \frac{Y}{W},\, \frac{Z}{W}\right)
$$

Por último, cada punto 3D conserva el color del píxel original para visualizar una nube coloreada en la GUI.

En la implementación, los puntos triangulados se obtienen inicialmente en el sistema de referencia definido por las cámaras. Para representarlos de forma coherente en el visor global, es necesario aplicar la transformación al sistema mundo mediante la extrínseca y su inversa.

$$
T_{wc} = \begin{bmatrix} R & t \\ 0 & 1 \end{bmatrix}
\qquad
T_{cw} = T_{wc}^{-1}
$$

$$
X_w = T_{cw}\, X_c
$$

Esta formulación es importante porque la posición de la cámara por sí sola no determina completamente la transformación. También es necesaria su orientación, ya que la reconstrucción depende tanto de la traslación como de la rotación.

## Parámetros seleccionados

| Parámetro | Valor | Función |
|---|---:|---|
| `CORR_THRESH` | 0.92 | Umbral mínimo de NCC para aceptar un match |
| `PATCH` | 18 | Tamaño del bloque usado en la comparación |
| `DISPARITY` | 90 | Alcance máximo de búsqueda sobre la epipolar |
| `SPARSE_STEP` | 3 | Submuestreo de bordes candidatos |

Estos parámetros controlan el equilibrio entre densidad, precisión y coste computacional. En particular, el tamaño del parche, el umbral de correlación y la disparidad máxima influyen directamente en la robustez del matching local.

## Resultados

El resultado final es una nube de puntos geométricamente coherente con el mundo simulado, suficiente para identificar la estructura espacial principal de la escena. La selección conservadora de correspondencias reduce el ruido y evita gran parte de los puntos erróneos.

A continuación se muestra una grabación de la ejecución del sistema durante la reconstrucción:

<div style="display:flex; justify-content:center; margin: 24px 0;">
  <iframe
    width="800"
    height="600"
    src="https://www.youtube.com/embed/jxtoJIxgQDs?si=Kb2VZ4MPm9Pqka6p"
    title="YouTube video player"
    frameborder="0"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
    referrerpolicy="strict-origin-when-cross-origin"
    allowfullscreen>
  </iframe>
</div>

## Observaciones

El comportamiento del sistema depende de forma directa del umbral de correlación y del tamaño del parche. Un umbral más bajo genera más puntos, pero también introduce más ruido. Un umbral alto produce una nube más limpia, aunque menos densa.

La geometría epipolar permite reducir drásticamente el espacio de búsqueda y hace viable la reconstrucción con coste moderado. Además, el uso de bordes submuestreados como puntos de interés reduce drásticamente el coste computacional.

Desde el punto de vista geométrico, la calidad final de la nube depende de tres factores principales: la validez de las correspondencias, la precisión de las matrices de proyección y la consistencia de la transformación entre coordenadas de cámara y coordenadas mundo.

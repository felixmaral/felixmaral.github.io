---
layout: default
title: "Práctica 4 · Conducción Autónoma con Deep Learning"
description: "Behavior Cloning, PilotNet, seguimiento de línea roja con red neuronal entrenada sobre dataset supervisado"
---

En esta práctica se aborda el mismo problema que en P1 —gobernar un coche de Fórmula 1 equipado con cámara frontal para que siga una línea roja en el circuito— pero mediante una aproximación de Deep Learning basada en **Behavior Cloning**. En lugar de programar explícitamente un controlador PID con procesado OpenCV, se recoge un dataset supervisado de un piloto experto, se entrena una red neuronal con ese dataset y, en tiempo de ejecución, la red infiere directamente la velocidad lineal (V) y la velocidad angular (W) a partir de la imagen de cámara.



### Dataset

El punto de partida es el dataset público de JDeRobot, grabado por un agente experto que recorre el circuito siguiendo satisfactoriamente la línea roja. Cada muestra del dataset es un par (imagen, (w, v)), donde **w** es la velocidad angular y **v** la velocidad lineal en ese instante.

**Análisis de la distribución:** Existe un balanceo de curvas (los dos picos menores son muy parecidos, en las curvas). El dataset presenta un fuerte sesgo, la distribución de **w** está muy concentrada en torno a cero, mientras que las curvas pronunciadas (valores de `|w| > 0.5`) son comparativamente escasas aunque con 2 picos balanceados. La distribución de **v** está casi íntegramente centrada en torno a 4.0, con muy pocos ejemplos en el rango [4, 7] (siendo 7 la velocidad máxima registrada). Este desequilibrio entre rectas y curvas, aun existiendo un balanceo de curva izq/dcha, penaliza la capacidad del modelo para generalizar en curvas.

**Particionado:** Se divide el dataset en tres splits —`train`, `val`, `test`— exportados como archivos CSV que registran la ruta relativa de imagen y los valores (w, v) correspondientes:

```
splits/
├── train.csv
├── val.csv
└── test.csv
```

**Nota**: Es importante tener en cuenta que los conjuntos de validación y test tienen un numero de valores (rectas, curvas) exactamente igual, para que las metricas sean realistas y generales.

<p align="center">
  <img src="{{ site.baseurl }}/assets/img/p4_dataset_distribution.png"
       alt="Distribución de valores w (velocidad angular) y v (velocidad lineal) en el dataset"
       style="max-width: 100%; border-radius: 10px;">
</p>

### Balanceo y Oversampling

Conocido el desbalanceo de rectas y curvas, se aplica una estrategia de **oversampling ×2** sobre las muestras con `|w| > 0.5` (umbral que separa rectas de curvas experimentalmente visto en el simulador). El mecanismo se implementa mediante `WeightedRandomSampler` de PyTorch, que asigna pesos inversamente proporcionales a la frecuencia de cada clase:

```
p_i = 1 / N_clase(i)
```

Con esto, cada época de entrenamiento presenta aproximadamente el mismo número de muestras de las tres franjas de interés: recta (`|w| ≤ 0.5`), curva suave y curva pronunciada. El ratio de peso curva/recta es ≈2×, lo que equivale a doblar la presencia efectiva de las curvas en cada batch.

### Preprocesado y Aumentado de Datos

El pipeline de preprocesado y aumentado se configura de forma modular mediante flags activables en tiempo de entrenamiento:

| Flag | Descripción |
| :--- | :--- |
| `--crop` | Recorta el 40 % superior de la imagen, eliminando el horizonte y el cielo para que la red se centre en el asfalto. |
| `--red_segment` | Aplica segmentación cromática en espacio HSV para aislar la línea roja y convertir la imagen a 1 canal. Reduce ruido de fondo. |
| `--augment` | Activa aumentado estocástico: volteo horizontal con inversión de **w**, variación aleatoria de brillo y proyección de sombras sintéticas. |
| `--oversample` | Activa el `WeightedRandomSampler` descrito anteriormente. |

El volteo horizontal se implementa de manera consistente: cuando una imagen se voltea, el signo de **w** también se invierte, de modo que el dato etiquetado sigue siendo válido. Esto dobla efectivamente el número de ejemplos de curva sin introducir sesgo.

### Arquitecturas Evaluadas

Se evaluaron cuatro arquitecturas en un grid search comparativo, todas con salida de dos neuronas lineales (w, v):

- **PilotNet**: Red convolucional ligera inspirada en el trabajo original de NVIDIA para conducción autónoma. Compuesta por 5 capas convolucionales seguidas de 4 capas fully-connected. Referencia clásica en behavior cloning.
- **MobileNetRegressor**: Backbone MobileNetV2 preentrenado en ImageNet con cabezal de regresión. Alta eficiencia computacional.
- **EfficientNetRegressor**: Backbone EfficientNet-B0 con cabezal de regresión. Mejor equilibrio entre capacidad y coste.
- **CustomCNNViT**: Arquitectura híbrida custom que combina un extractor convolucional con un módulo de atención tipo Vision Transformer para intentar capturar contexto global de la imagen.

### Pipeline de Entrenamiento

El ciclo de vida de cada experimento está encapsulado en la función `run_experiment(cfg)`, que recibe un `ExperimentConfig` con todos los hiperparámetros y flags de preprocesado:

1. **Carga de datos**: Se instancian los `DrivingDataset` de train y val con las transformaciones activas.
2. **Dataloader**: Si `oversample=True` se usa `WeightedRandomSampler`; en otro caso, `shuffle=True` estándar.
3. **Modelo**: Se instancia la arquitectura elegida y se mueve a GPU si está disponible.
4. **Optimizador y scheduler**: `AdamW` con `weight_decay=1e-5` y `ReduceLROnPlateau` que reduce el learning rate por un factor 0.5 si la pérdida de validación no mejora en 3 épocas.
5. **Función de pérdida**: `MSELoss` sobre el vector (w, v).
6. **Loop de entrenamiento**: Para cada época se ejecutan una fase de train con gradientes y una de validación en modo `eval`. Se registra la pérdida y el R² global y segmentado.
7. **Early-model**: Se guarda el `state_dict` del modelo que alcanza la menor pérdida de validación.
8. **Evaluación final**: El mejor modelo se evalúa sobre el split de test, calculando R² global y por franjas de **w**.

### Resultados del Grid Search

A continuación se presentan los resultados comparativos de las cuatro arquitecturas evaluadas, con entrada RGB y máscara binaria de la línea roja, entrenadas con distintas combinaciones de crop, aumentado de datos y oversampling:

<p align="center">
  <img src="{{ site.baseurl }}/assets/img/p4_grid_search.png"
       alt="Resultados del grid search: comparativa de 4 arquitecturas con métricas R² segmentadas"
       style="max-width: 100%; border-radius: 10px;">
</p>

**Interpretación cualitativa de los resultados.** La evaluación cuantitativa sobre el split de test no es suficiente por sí sola para seleccionar el mejor modelo. El dataset completo ha sido recogido sobre un **único circuito**, lo que implica que un modelo con suficiente capacidad puede obtener métricas muy altas en test simplemente memorizando las imágenes del trazado, sin haber aprendido a generalizar a nuevos circuitos. Esto se observa especialmente en los modelos sin aumentado de datos: sus R² sobre test son elevados, pero al ejecutarlos en otros circuitos muestran titubeos y pérdidas de línea frecuentes.

Las configuraciones que incluyen **crop + augmentación + segmentación roja** (`_crop_aug_redseg`) rompen esta dependencia del aspecto visual exacto del circuito entrenado: el volteo horizontal fuerza invarianza izquierda-derecha, las sombras sintéticas reducen la sensibilidad a cambios de iluminación y el recorte del horizonte elimina ruido para el modelo. El resultado es un modelo que **generaliza** en lugar de memorizar. Aprendiendo sobre la máscara binaria evitamos tener que depender de muchos mas datos y utilizar una caracteristica general en todos los circuitos.

El experimento seleccionado como mejor solución es **`EfficientNet_crop_aug_redseg`** con oversampling. Aunque no es el que mayor R² obtiene en test en valores absolutos, es el que presenta el comportamiento cualitativo más estable durante la conducción en varios circuitos: sin apenas oscilaciones en la trayectoria, muy reactivo a los giros, y con una velocidad prácticamente constante en torno a 4 m/s con pequeñas subidas espontáneas en las rectas largas, un patrón aprendido directamente del comportamiento del agente experto en el dataset. Los demás experimentos también completan el circuito correctamente, pero presentan mayor varianza en la trayectoria o reaccionan con ligero retraso en curvas pronunciadas.

### Inferencia en Unibotics

El script de inferencia (`E2E.py`) es el que se ejecuta en el simulador Unibotics. Al arrancar, lee `experiment_log.json` del directorio del experimento para saber qué arquitectura se usó y qué flags de preprocesado están activos (`crop`, `red_segment`). Después carga `model.onnx` con `onnxruntime` y consulta directamente la forma de entrada del modelo para determinar el número de canales y la resolución esperada, de modo que la configuración siempre es coherente con el modelo y no depende de que el JSON esté bien escrito.

El bucle principal ejecuta en cada iteración:

1. `HAL.getImage()` captura la imagen BGR de la cámara frontal.
2. La función `preprocess` aplica el mismo pipeline usado en entrenamiento: BGR a RGB, crop del 40 % superior si corresponde, máscara binaria de rojo en HSV si el modelo es de 1 canal, resize al tamaño de entrada del modelo, transposición HWC a CHW y normalización a [0, 1].
3. `session.run()` ejecuta la inferencia ONNX y devuelve dos valores: **w** (velocidad angular) y **v** (velocidad lineal).
4. `HAL.setW(w)` y `HAL.setV(v)` envían los comandos al robot.
5. `WebGUI.showImage()` muestra en el visor la imagen con un HUD superpuesto que indica la arquitectura, configuración activa y los valores de **w** y **v** inferidos en ese frame, además de una barra de steering en la parte inferior.

No hay ningún controlador PID ni lógica de decisión adicional. La política de conducción queda completamente en los pesos del modelo.

## Parámetros de Configuración

| Parámetro | Valor | Función |
| :--- | :---: | :--- |
| `epochs` | 10 | Número de épocas de entrenamiento. |
| `batch_size` | 128 | Tamaño de batch para train y val. |
| `lr` | 1e-4 | Learning rate inicial de AdamW. |
| `lr_factor` | 0.5 | Factor de reducción del scheduler. |
| `lr_patience` | 3 | Épocas sin mejora para activar el scheduler. |
| `weight_decay` | 1e-5 | Regularización L2 del optimizador. |
| `input_size` | 128×128 | Resolución de entrada a la red. |
| `oversample_thr` | 0.5 | Umbral `|w|` para el oversampling. |
| `crop_percent` | 0.4 | Fracción superior de imagen eliminada. |

## Resultados y Observaciones

El modelo seleccionado (`EfficientNet_crop_aug_redseg`) consigue que el coche complete varios circuitos de forma continuada manteniendo la línea roja con muy pocas oscilaciones. La combinación de las tres técnicas de preprocesado resulta sinérgica: el crop elimina el contexto visual irrelevante del horizonte, la segmentación de rojo reduce la entrada a la información más discriminativa para la tarea, y el aumentado fuerza al modelo a aprender la geometría de la línea en lugar de memorizar la textura exacta de un circuito concreto.

El oversampling es determinante para el comportamiento en curvas: sin él, el coche se comporta bien en rectas pero falla sistemáticamente en las curvas pronunciadas, ya que esas muestras están infrarrepresentadas en el dataset original. Con oversampling activo, la distribución de error es mucho más uniforme a lo largo del trazado.

La segmentación de rojo en un canal, lejos de ser una limitación, acelera la convergencia en EfficientNet al simplificar drásticamente el espacio de entrada. La arquitectura compensa la pérdida de los pesos ImageNet con la facilidad de la tarea reducida: detectar una región de color en un fondo negro.

A continuación se muestran las curvas de entrenamiento del experimento de referencia (`EXP_PilotNet_crop`), donde se aprecia la rápida convergencia de la loss y la evolución del R² para steering y velocidad:

<p align="center">
  <img src="{{ site.baseurl }}/assets/img/p4_training_curves.png"
       alt="Curvas de entrenamiento del experimento EXP_PilotNet_crop: MSE Loss, R²(w) y R²(v) sobre train y validación"
       style="max-width: 100%; border-radius: 10px;">
</p>

El mapa de activaciones **Grad-CAM** sobre la última capa convolucional confirma que la red atiende correctamente a la línea roja del circuito y no a regiones espurias del fondo:

<p align="center">
  <img src="{{ site.baseurl }}/assets/img/p4_gradcam.png"
       alt="Grad-CAM sobre PilotNet: la red activa intensamente sobre la línea roja del circuito para predecir el steering"
       style="max-width: 100%; border-radius: 10px;">
</p>

La siguiente gráfica muestra los valores reales frente a los predichos por el mejor modelo en el split de test. La alineación con la diagonal perfecta (y = x) confirma que el modelo aprende una relación lineal sólida tanto para el steering como para la velocidad, incluso en los regímenes de curva más pronunciados:

<p align="center">
  <img src="{{ site.baseurl }}/assets/img/p4_r2_scatter.png"
       alt="Scatter real vs predicho del experimento EXP_PilotNet_crop: steering (w) y velocidad (v) en train, val y test con R²≈0.97"
       style="max-width: 100%; border-radius: 10px;">
</p>

### Demostración en pista

<div style="display:flex; justify-content:center; margin: 24px 0;">
  <iframe
    width="800"
    height="450"
    src="https://www.youtube.com/embed/VIDEO_ID_AQUI"
    title="Coche de F1 siguiendo la línea roja · Práctica 4"
    frameborder="0"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
    referrerpolicy="strict-origin-when-cross-origin"
    allowfullscreen>
  </iframe>
</div>

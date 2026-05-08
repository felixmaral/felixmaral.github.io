import WebGUI
import HAL
import Frequency
import cv2
import numpy as np
import sys
import os
import json
import onnxruntime as ort


EXPERIMENT_DIR = os.path.dirname(os.path.abspath(__file__))
FREQ_HZ = 10

# Carga configuración del experimento
_log_path   = os.path.join(EXPERIMENT_DIR, "experiment_log.json")
_model_path = os.path.join(EXPERIMENT_DIR, "model.onnx")

if not os.path.exists(_log_path):
    print(f"[ERROR] No se encuentra experiment_log.json en: {EXPERIMENT_DIR}")
    sys.exit(1)
if not os.path.exists(_model_path):
    print(f"[ERROR] No se encuentra model.onnx en: {EXPERIMENT_DIR}")
    sys.exit(1)

with open(_log_path) as f:
    _log = json.load(f)

_exp_info    = _log["experiment_info"]
_hyp         = _log.get("hyperparameters", {})
ARCHITECTURE = _exp_info["architecture"]
USE_REDSEG   = _hyp.get("red_segment", _hyp.get("redsegment", False))
CROP_PERCENT = 0.4 if _hyp.get("crop", False) else 0.0

# Carga el modelo ONNX
try:
    session    = ort.InferenceSession(_model_path, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
except Exception as e:
    print(f"[ERROR] No se pudo cargar el modelo: {e}")
    sys.exit(1)

# Los canales del modelo mandan sobre el JSON (evita inconsistencias)
_onnx_shape = session.get_inputs()[0].shape  # (1, C, H, W)
CHANNELS    = _onnx_shape[1]
INPUT_SIZE  = (_onnx_shape[2], _onnx_shape[3])
USE_REDSEG  = (CHANNELS == 1)

print(f"[INIT] {ARCHITECTURE} | canales={CHANNELS} crop={CROP_PERCENT:.0%} redseg={USE_REDSEG}")


def _crop(img):
    cut = int(img.shape[0] * CROP_PERCENT)
    return img[cut:, :]


def _redseg(img):
    # Máscara binaria de píxeles rojos en HSV
    hsv   = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    mask1 = cv2.inRange(hsv, np.array([0,   70, 50]), np.array([10,  255, 255]))
    mask2 = cv2.inRange(hsv, np.array([170, 70, 50]), np.array([180, 255, 255]))
    mask  = (mask1 | mask2).astype(np.float32) / 255.0
    return np.expand_dims(mask, axis=-1)


def preprocess(bgr):
    img = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    if CROP_PERCENT > 0.0:
        img = _crop(img)
    if USE_REDSEG:
        img = _redseg(img)
    img = cv2.resize(img, (INPUT_SIZE[1], INPUT_SIZE[0]))
    if img.ndim == 2:
        img = np.expand_dims(img, axis=-1)
    img = np.transpose(img, (2, 0, 1)).astype(np.float32)
    if img.max() > 1.0:
        img /= 255.0
    return img[np.newaxis, ...]


def draw_debug(bgr, w, v):
    debug    = bgr.copy()
    h, width = debug.shape[:2]

    lines = [
        (f"{ARCHITECTURE}",                      (200, 200, 200), 0.45, 1),
        (f"ch={CHANNELS} redseg={USE_REDSEG}",   (200, 200, 200), 0.45, 1),
        (f"crop={CROP_PERCENT:.0%}",              (200, 200, 200), 0.45, 1),
        (f"w: {w:+.4f}",                          (0, 255, 100),   0.65, 2),
        (f"v: {v:+.4f}",                          (0, 200, 255),   0.65, 2),
    ]

    margin = 12
    line_h = 26
    box_h  = len(lines) * line_h + margin * 2
    box_w  = max(
        cv2.getTextSize(t, cv2.FONT_HERSHEY_SIMPLEX, s, th)[0][0]
        for t, _, s, th in lines
    ) + margin * 2

    x0, y0 = width - box_w - margin, margin
    overlay = debug.copy()
    cv2.rectangle(overlay, (x0, y0), (x0 + box_w, y0 + box_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, debug, 0.5, 0, debug)

    for i, (text, color, scale, thick) in enumerate(lines):
        cv2.putText(debug, text, (x0 + margin, y0 + margin + (i + 1) * line_h),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick)

    # Barra de steering en la parte inferior
    bar_cx  = width // 2
    bar_y   = h - 20
    bar_len = int(np.clip(w, -1.0, 1.0) * 100)
    cv2.line(debug, (bar_cx, bar_y), (bar_cx + bar_len, bar_y), (0, 255, 100), 4)
    cv2.circle(debug, (bar_cx, bar_y), 5, (255, 255, 255), -1)

    return debug


# Loop reactivo principal
frame_count = 0
none_count  = 0

while True:
    bgr = HAL.getImage()

    if bgr is None:
        none_count += 1
        Frequency.tick(FREQ_HZ)
        continue

    frame_count += 1

    tensor  = preprocess(bgr)
    outputs = session.run(None, {input_name: tensor})
    w = float(outputs[0][0][0])
    v = float(outputs[0][0][1])

    HAL.setW(w)
    HAL.setV(v)

    WebGUI.showImage(draw_debug(bgr, w, v))
    Frequency.tick(FREQ_HZ)

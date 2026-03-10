import HAL
import WebGUI
import Frequency
import cv2
import numpy as np

# FÉLIX MARTÍNEZ ALONSO
# PRÁCTICA 1 - PRIMERA APROXIMACIÓN - Control Reactivo

def calculate_metrics(error_data, w_data):
    """
    Calculates controller performance metrics.
    Returns RMSE (stability) and Zigzag (control effort).
    """
    rmse = 0.0
    zigzag = 0.0

    if len(error_data) > 0:
        rmse = np.sqrt(np.mean(np.square(error_data)))

    if len(w_data) > 1:
        w_diffs = np.abs(np.diff(w_data))
        zigzag = np.mean(w_diffs)

    return rmse, zigzag

def draw_telemetry(img, current_error, current_v, current_w, error_history, w_history, kp, kd, ki):
    """
    Overlays real-time telemetry and accumulated metrics on the image.
    """
    rmse, zigzag = calculate_metrics(error_history, w_history)

    lines = [
        f"Accum ZigZag: {zigzag:.3f}",
        f"Accum RMSE: {rmse:.1f}",
        f"Error: {current_error:.1f}",
        f"Inst Vel: {current_v:.2f}",
        f"Turn: {current_w:.3f}"
    ]

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    thickness = 1

    # Side telemetry rendering
    color_telemetry = (0, 0, 255)
    x_offset = img.shape[1] - 180
    y_offset = 80

    for line in lines:
        cv2.putText(img, line, (x_offset, y_offset), font, font_scale, color_telemetry, thickness)
        y_offset += 25

    # PID constants rendering
    color_pid = (255, 0, 0)
    pid_text = f"Kp: {kp} | Kd: {kd} | Ki: {ki}"
    x_center = int(img.shape[1] / 2) - 100
    y_center = 30

    cv2.putText(img, pid_text, (x_center, y_center), font, font_scale, color_pid, thickness)

# Steering PID controller constants
Kp_w = 0.005
Kd_w = 0.08
Ki_w = 0.0

# Speed PID controller constants
Kp_v = 0.04
Kd_v = 0.02
Ki_v = 0.0

MAX_SPEED = 11.0
MIN_SPEED = 2.0

# Internal system state variables
prev_error_w = 0.0
accum_error_w = 0.0
prev_error_v = 0.0
accum_error_v = 0.0

# Historical memory logs
log_errors = []
log_w = []

while True:
    img = HAL.getImage()
    if img is None:
        continue

    error = 0.0
    v = 0.0
    w = 0.0

    # Red line HSV segmentation
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower1 = np.array([0, 100, 100])
    upper1 = np.array([10, 255, 255])
    lower2 = np.array([160, 100, 100])
    upper2 = np.array([180, 255, 255])

    mask = cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2)
    M = cv2.moments(mask)

    if M['m00'] > 0:
        # Lateral error calculation
        cx = int(M['m10'] / M['m00'])
        cy = int(M['m01'] / M['m00'])

        cv2.circle(img, (cx, cy), 5, (0, 255, 0), -1)

        center = img.shape[1] / 2
        error = center - cx

        # Lateral guidance PID execution
        accum_error_w += error
        p_w = Kp_w * error
        d_w = Kd_w * (error - prev_error_w)
        i_w = Ki_w * accum_error_w
        w = p_w + d_w + i_w
        prev_error_w = error

        # Longitudinal speed control PID execution
        speed_error = abs(error)
        accum_error_v += speed_error
        p_v = Kp_v * speed_error
        d_v = Kd_v * (speed_error - prev_error_v)
        i_v = Ki_v * accum_error_v
        prev_error_v = speed_error

        v = MAX_SPEED - (p_v + d_v + i_v)
        v = max(MIN_SPEED, min(MAX_SPEED, v))

        HAL.setV(v)
        HAL.setW(w)

        # Metrics logs update
        log_errors.append(error)
        log_w.append(w)

    else:
        # Emergency routine on trace loss
        v = 1.5
        w = prev_error_w * Kp_w * 0.5
        HAL.setV(v)
        HAL.setW(w)

    # Telemetry data injection into video stream
    draw_telemetry(img, error, v, w, log_errors, log_w, Kp_w, Kd_w, Ki_w)

    WebGUI.showImage(img)
    Frequency.tick()
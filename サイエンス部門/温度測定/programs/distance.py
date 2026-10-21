import time
from machine import Pin

# --- ピン設定 ---
trig = Pin(14, Pin.OUT)
echo = Pin(15, Pin.IN)

trig.value(0)
time.sleep_us(5)


def get_distance():
    """超音波センサーで距離(cm)を1回計測して返す関数"""
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)

    timeout_start = time.ticks_us()
    while echo.value() == 0:
        if time.ticks_diff(time.ticks_us(), timeout_start) > 30000:
            return None

    signal_start = time.ticks_us()

    while echo.value() == 1:
        if time.ticks_diff(time.ticks_us(), signal_start) > 30000:
            return None

    signal_end = time.ticks_us()

    duration = time.ticks_diff(signal_end, signal_start)
    distance = (duration * 0.0343) / 2

    return distance


def get_stable_distance(samples=5):
    """複数回計測してエラー値を除外した平均距離(cm)を返す"""
    valid_samples = []
    for _ in range(samples):
        d = get_distance()
        if d is not None:
            valid_samples.append(d)
        time.sleep(0.05)

    if not valid_samples:
        return None
    return sum(valid_samples) / len(valid_samples)
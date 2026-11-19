import time
from machine import Pin
from motor import StopRequested

trig = Pin(14, Pin.OUT)
echo = Pin(15, Pin.IN)
trig.value(0)
time.sleep_us(5)


def _check_stop(stop_check):
    if stop_check is not None and stop_check():
        raise StopRequested("USB STOP command received")


def get_distance(stop_check=None):
    """超音波センサーで距離(cm)を1回計測。STOP要求にも対応。"""
    clear_start = time.ticks_us()
    while echo.value() == 1:
        _check_stop(stop_check)
        if time.ticks_diff(time.ticks_us(), clear_start) > 10000:
            return None

    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)

    timeout_start = time.ticks_us()
    while echo.value() == 0:
        _check_stop(stop_check)
        if time.ticks_diff(time.ticks_us(), timeout_start) > 30000:
            return None

    signal_start = time.ticks_us()
    while echo.value() == 1:
        _check_stop(stop_check)
        if time.ticks_diff(time.ticks_us(), signal_start) > 45000:
            return None

    signal_end = time.ticks_us()
    duration = time.ticks_diff(signal_end, signal_start)
    distance = (duration * 0.0343) / 2
    if 2.0 <= distance <= 400.0:
        return distance
    return None


def get_stable_distance(samples=7, stop_check=None):
    """複数回測定し、有効値の中央値を返す。STOP要求時は中断。"""
    valid_samples = []
    for _ in range(samples):
        _check_stop(stop_check)
        value = get_distance(stop_check=stop_check)
        if value is not None:
            valid_samples.append(value)
        # 60ms待機中もSTOPを確認
        for _ in range(6):
            _check_stop(stop_check)
            time.sleep_ms(10)

    if not valid_samples:
        return None
    valid_samples.sort()
    return valid_samples[len(valid_samples) // 2]


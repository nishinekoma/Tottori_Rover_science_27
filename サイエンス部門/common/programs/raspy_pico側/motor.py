import time
from machine import I2C, Pin

I2C_ID = 0
I2C_SDA = 0
I2C_SCL = 1
I2C_FREQ = 100000
PCA_ADDRESS = 0x40
PWM_FREQ = 50
SHAFT_CHANNEL = 0
SAND_CHANNEL = 4  # 今回の動作シーケンスには含めないが、STOP時は出力停止
GATE_CHANNEL = 8
SPEED_CM_PER_SEC = 12.4

# SG90の初期指令値。必ず実機で安全な端点を確認して調整する。
GATE_OPEN_PULSE_US = 500
GATE_CLOSED_PULSE_US = 2500
CONTROL_INTERVAL_MS = 20


class StopRequested(Exception):
    pass


class PCA9685:
    def __init__(self, i2c_bus, address=PCA_ADDRESS):
        self.i2c = i2c_bus
        self.address = address
        self.i2c.writeto_mem(self.address, 0x00, b"\x00")

    def set_freq(self, freq_hz):
        prescale = int(25000000.0 / 4096.0 / freq_hz - 1.0 + 0.5)
        oldmode = self.i2c.readfrom_mem(self.address, 0x00, 1)[0]
        newmode = (oldmode & 0x7F) | 0x10
        self.i2c.writeto_mem(self.address, 0x00, bytes([newmode]))
        self.i2c.writeto_mem(self.address, 0xFE, bytes([prescale]))
        self.i2c.writeto_mem(self.address, 0x00, bytes([oldmode]))
        time.sleep_ms(5)
        self.i2c.writeto_mem(self.address, 0x00, bytes([oldmode | 0xA1]))
        time.sleep_ms(5)

    def set_pwm(self, channel, on_time, off_time):
        data = bytes((
            on_time & 0xFF,
            (on_time >> 8) & 0x0F,
            off_time & 0xFF,
            (off_time >> 8) & 0x1F,
        ))
        self.i2c.writeto_mem(self.address, 0x06 + 4 * channel, data)

    def set_pulse_us(self, channel, pulse_us):
        count = int(pulse_us * 4096.0 / 20000.0 + 0.5)
        self.set_pwm(channel, 0, count)

    def spin(self, channel, direction="right", speed=100):
        speed = max(0, min(100, speed))
        offset = int(150 * (speed / 100.0))
        pwm_val = 300 + offset if direction == "left" else 300 - offset
        self.set_pwm(channel, 0, pwm_val)

    def force_stop(self, channel):
        # PCA9685 FULL_OFF bit
        self.set_pwm(channel, 0, 4096)

    def disable_all_motors(self):
        self.force_stop(SHAFT_CHANNEL)
        self.force_stop(SAND_CHANNEL)
        self.force_stop(GATE_CHANNEL)


def create_pca():
    i2c = I2C(I2C_ID, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=I2C_FREQ)
    if PCA_ADDRESS not in i2c.scan():
        raise OSError("PCA9685 (0x40) が見つかりません")
    pca = PCA9685(i2c, PCA_ADDRESS)
    pca.set_freq(PWM_FREQ)
    return pca


def _check_stop(stop_check):
    if stop_check is not None and stop_check():
        raise StopRequested("USB STOP command received")


def _sleep_interruptible(seconds, stop_check):
    remaining_ms = int(seconds * 1000)
    while remaining_ms > 0:
        _check_stop(stop_check)
        wait_ms = min(CONTROL_INTERVAL_MS, remaining_ms)
        time.sleep_ms(wait_ms)
        remaining_ms -= wait_ms
    _check_stop(stop_check)


def set_gate_open(pca):
    pca.set_pulse_us(GATE_CHANNEL, GATE_OPEN_PULSE_US)


def set_gate_closed(pca):
    pca.set_pulse_us(GATE_CHANNEL, GATE_CLOSED_PULSE_US)


def stop_all_outputs(pca=None):
    if pca is None:
        pca = create_pca()
    pca.disable_all_motors()


def move_arm_by_distance(
    distance_cm, direction="right", speed=100, margin_cm=8.0,
    initial_offset_cm=9.0, before_end_callback=None,
    close_before_end_sec=2.0, stop_check=None,
):
    """CH0を距離に応じた時間だけ動かし、終了前コールバックを1回実行する。"""
    actual_move_cm = distance_cm + margin_cm - initial_offset_cm
    if actual_move_cm <= 0:
        _check_stop(stop_check)
        if before_end_callback is not None:
            before_end_callback()
        return 0.0

    run_time = actual_move_cm / SPEED_CM_PER_SEC
    pca = create_pca()
    pca.force_stop(SHAFT_CHANNEL)
    callback_done = False
    try:
        _check_stop(stop_check)
        if before_end_callback is not None and run_time <= close_before_end_sec:
            before_end_callback()
            callback_done = True

        pca.spin(SHAFT_CHANNEL, direction=direction, speed=speed)
        start_ms = time.ticks_ms()
        total_ms = int(run_time * 1000)
        while True:
            _check_stop(stop_check)
            elapsed_ms = time.ticks_diff(time.ticks_ms(), start_ms)
            remaining_ms = total_ms - elapsed_ms
            if (not callback_done and before_end_callback is not None
                    and remaining_ms <= int(close_before_end_sec * 1000)):
                _check_stop(stop_check)
                before_end_callback()
                callback_done = True
            if remaining_ms <= 0:
                break
            time.sleep_ms(min(CONTROL_INTERVAL_MS, remaining_ms))
        _check_stop(stop_check)
        return actual_move_cm
    finally:
        pca.force_stop(SHAFT_CHANNEL)


def retract_arm_simple(move_cm, direction="left", speed=100, stop_check=None):
    if move_cm <= 0:
        return True
    run_time = move_cm / SPEED_CM_PER_SEC
    pca = create_pca()
    try:
        _check_stop(stop_check)
        pca.spin(SHAFT_CHAN NEL, direction=direction, speed=speed)
        _sleep_interruptible(run_time, stop_check)
        return True
    finally:
        pca.force_stop(SHAFT_CHANNEL)

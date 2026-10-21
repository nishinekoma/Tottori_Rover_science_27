import time
from machine import I2C, Pin

I2C_SDA = 0
I2C_SCL = 1
MOTOR_CHANNEL = 0
SPEED_CM_PER_SEC = 12.4  # 1秒間に進む距離(cm)


class PCA9685:

    def __init__(self, i2c_bus, address=0x40):
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
        time.sleep_us(500)
        self.i2c.writeto_mem(self.address, 0x00, bytes([oldmode | 0xA1]))

    def set_pwm(self, channel, on_time, off_time):
        data = bytearray(
            [
                on_time & 0xFF,
                (on_time >> 8) & 0xFF,
                off_time & 0xFF,
                (off_time >> 8) & 0xFF,
            ]
        )
        self.i2c.writeto_mem(self.address, 0x06 + 4 * channel, data)

    def spin(self, channel, direction="right", speed=100):
        offset = int(150 * (speed / 100.0))
        if direction == "left":
            pwm_val = 300 + offset
        else:
            pwm_val = 300 - offset
        self.set_pwm(channel, 0, pwm_val)

    def force_stop(self, channel):
        self.set_pwm(channel, 0, 4096)


def move_arm_by_distance(
    distance_cm,
    direction="right",
    speed=100,
    margin_cm=8.0,
    initial_offset_cm=9.0,
):
    """目標距離まで展開し、実際に動かした距離(cm)を返します。"""
    target_total_cm = distance_cm + margin_cm
    actual_move_cm = target_total_cm - initial_offset_cm

    if actual_move_cm <= 0:
        return 0.0

    run_time = actual_move_cm / SPEED_CM_PER_SEC

    i2c = I2C(0, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100000)
    devices = i2c.scan()
    if not devices:
        print("[Motor Error] PCA9685が見つかりません。")
        return False

    pca = PCA9685(i2c, address=0x40)
    pca.set_freq(50)
    pca.force_stop(MOTOR_CHANNEL)
    time.sleep(0.5)

    try:
        pca.spin(channel=MOTOR_CHANNEL, direction=direction, speed=speed)
        time.sleep(run_time)
    finally:
        pca.force_stop(MOTOR_CHANNEL)

    return actual_move_cm


def retract_arm_simple(move_cm, direction="left", speed=100):
    """展開した距離分だけ巻き戻します。"""
    if move_cm <= 0:
        return True

    run_time = move_cm / SPEED_CM_PER_SEC

    i2c = I2C(0, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100000)
    pca = PCA9685(i2c, address=0x40)
    pca.set_freq(50)

    try:
        pca.spin(channel=MOTOR_CHANNEL, direction=direction, speed=speed)
        time.sleep(run_time)
    finally:
        pca.force_stop(MOTOR_CHANNEL)

    return True
"""test.py"""
def set_servo_angle(pca, channel, angle):
    """GWS Micro 2BBMG 用の角度制御関数 (50Hz駆動)
    angle: 0度 〜 180度
    """
    if angle < 0:
        angle = 0
    if angle > 180:
        angle = 180

    min_pulse = 102
    max_pulse = 491
    pulse = int(min_pulse + (max_pulse - min_pulse) * (angle / 180.0))

    pca.set_pwm(channel, 0, pulse)
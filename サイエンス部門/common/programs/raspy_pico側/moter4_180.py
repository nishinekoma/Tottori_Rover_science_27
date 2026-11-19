import time
from machine import I2C, Pin

# TowerPro MG996R Digital High Torque
# PCA9685 CH4 / 50Hz / Raspberry Pi Pico 2 W
#
# 動作: 0度 -> 180度 -> 0度 を2往復
# 既存のパルス幅設定を維持

I2C_ID = 0
SDA_PIN = 0
SCL_PIN = 1
I2C_FREQ = 100000

PCA_ADDR = 0x40
PWM_FREQ = 50
SERVO_CH = 4

PULSE_0_DEG_US = 571
PULSE_180_DEG_US = 2411

HOLD_SECONDS = 1.5
CYCLES = 2

START_MS = time.ticks_ms()


def log(message):
    elapsed = time.ticks_diff(time.ticks_ms(), START_MS)
    print("[{:>7} ms] {}".format(elapsed, message))


class PCA9685:
    def __init__(self, i2c, address):
        self.i2c = i2c
        self.address = address

    def read8(self, reg):
        return self.i2c.readfrom_mem(self.address, reg, 1)[0]

    def write8(self, reg, value):
        self.i2c.writeto_mem(
            self.address, reg, bytes([value & 0xFF])
        )

    def set_freq(self, freq_hz):
        prescale = int(
            25000000 / (4096 * freq_hz) - 1 + 0.5
        )

        # 内部クロックを使用して50Hzに設定
        self.write8(0x00, 0x30)
        time.sleep_ms(5)

        self.write8(0xFE, prescale)

        self.write8(0x00, 0x20)
        time.sleep_ms(5)

        self.write8(0x00, 0xA0)
        time.sleep_ms(5)

        return prescale

    def set_pulse_us(self, channel, pulse_us):
        count = int(pulse_us * 4096 / 20000 + 0.5)
        reg = 0x06 + 4 * channel

        data = bytes((
            0,
            0,
            count & 0xFF,
            (count >> 8) & 0x0F
        ))

        self.i2c.writeto_mem(self.address, reg, data)
        return count


def move_to(pca, angle_label, pulse_us):
    count = pca.set_pulse_us(SERVO_CH, pulse_us)

    log("CH{} | {} deg | {} us | count={}".format(
        SERVO_CH, angle_label, pulse_us, count
    ))

    time.sleep(HOLD_SECONDS)


def main():
    try:
        log("MG996R LEFT DIRECTION 0-180-0 x2 test start")

        i2c = I2C(
            I2C_ID,
            sda=Pin(SDA_PIN),
            scl=Pin(SCL_PIN),
            freq=I2C_FREQ
        )

        devices = i2c.scan()

        log("I2C devices: {}".format(
            ["0x{:02X}".format(x) for x in devices]
        ))

        if PCA_ADDR not in devices:
            log("[ERROR] PCA9685 0x40 not found")
            return

        pca = PCA9685(i2c, PCA_ADDR)

        prescale = pca.set_freq(PWM_FREQ)

        log("PCA9685: {}Hz / PRESCALE={}".format(
            PWM_FREQ, prescale
        ))

        log("Servo channel: CH{}".format(SERVO_CH))

        for cycle in range(1, CYCLES + 1):
            log("=== Cycle {}/{} ===".format(cycle, CYCLES))

            # 左方向へ動かす側の角度指令
            move_to(pca, 0, PULSE_0_DEG_US)
            move_to(pca, 180, PULSE_180_DEG_US)
            move_to(pca, 0, PULSE_0_DEG_US)

        log("=== Completed: 2 round trips. Servo remains at 0 deg. ===")

    except Exception as e:
        log("[ERROR] {}: {}".format(type(e).__name__, e))


if __name__ == "__main__":
    main()

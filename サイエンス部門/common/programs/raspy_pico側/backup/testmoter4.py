
from machine import I2C, Pin
import time

# ========================================
# PCA9685設定
# ========================================
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=400000)

PCA_ADDR = 0x40
CH = 4
FREQ = 50

# ========================================
# 調査用設定
# ========================================
STEP_US = 10
STEP_LARGE_US = 50

MIN_PULSE = 300
MAX_PULSE = 3000

# ========================================
# PCA9685制御関数
# ========================================
def write_reg(reg, value):
    i2c.writeto_mem(PCA_ADDR, reg, bytes([value]))


def init_pca():
    prescale = int(25000000 / (4096 * FREQ) - 1)

    write_reg(0x00, 0x10)
    write_reg(0xFE, prescale)
    write_reg(0x00, 0x20)

    time.sleep_ms(10)
    write_reg(0x00, 0xA1)


def set_pulse_us(pulse_us):
    ticks = int(pulse_us * 4096 / 20000)
    reg = 0x06 + 4 * CH

    i2c.writeto_mem(
        PCA_ADDR,
        reg,
        bytes([
            0,
            0,
            ticks & 0xFF,
            (ticks >> 8) & 0x0F
        ])
    )


def stop_signal():
    reg = 0x06 + 4 * CH

    i2c.writeto_mem(
        PCA_ADDR,
        reg,
        bytes([0, 0, 0, 0x10])
    )


# ========================================
# 開始パルス幅の入力
# ========================================
print("CH4 GWS Micro 2BBMG パルス幅調整")
print("--------------------------------")

while True:
    try:
        pulse = int(input("開始パルス幅を入力してください (us): "))

        if MIN_PULSE <= pulse <= MAX_PULSE:
            break

        print("入力範囲は", MIN_PULSE, "～", MAX_PULSE, "usです")

    except ValueError:
        print("数値を入力してください")


# ========================================
# 初期化・開始位置へ移動
# ========================================
init_pca()
set_pulse_us(pulse)

time.sleep_ms(300)

print("--------------------------------")
print("現在:", pulse, "us")
print("+  : 10us増加")
print("-  : 10us減少")
print("++ : 50us増加")
print("-- : 50us減少")
print("数値入力: 指定したパルス幅に移動")
print("stop : PWM信号停止")
print("exit : 終了")
print("--------------------------------")


# ========================================
# パルス幅調整
# ========================================
try:
    while True:

        cmd = input("> ").strip().lower()

        if cmd == "exit":
            break

        elif cmd == "stop":
            stop_signal()
            print("CH4 PWM停止")
            continue

        elif cmd == "+":
            pulse += STEP_US

        elif cmd == "-":
            pulse -= STEP_US

        elif cmd == "++":
            pulse += STEP_LARGE_US

        elif cmd == "--":
            pulse -= STEP_LARGE_US

        else:
            try:
                pulse = int(cmd)
            except ValueError:
                print("入力を確認してください")
                continue

        # 範囲チェック
        if pulse < MIN_PULSE:
            pulse = MIN_PULSE
            print("下限:", MIN_PULSE, "us")

        elif pulse > MAX_PULSE:
            pulse = MAX_PULSE
            print("上限:", MAX_PULSE, "us")

        set_pulse_us(pulse)

        print("CH4:", pulse, "us")
        time.sleep_ms(300)

finally:
    stop_signal()
    print("CH4 PWM停止・終了")


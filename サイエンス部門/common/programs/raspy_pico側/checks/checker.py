# checker.py
# Pico 2 W + PCA9685 モーター系統総合診断
# I2C0: GP0=SDA, GP1=SCL
# PCA9685: 0x40
# 外部サーボ電源: 6V想定

import time
from machine import I2C, Pin

# ===== 設定 =====
I2C_ID = 0
SDA_PIN = 0
SCL_PIN = 1
I2C_FREQ = 100000
PCA_ADDR = 0x40

PWM_FREQ = 50
OSC_CLOCK = 25000000

SHAFT_CH = 0
SAND_CH = 4
GATE_CH = 8

MG996R_0_US = 571
MG996R_90_US = 1491
MG996R_180_US = 2411

SG90_OPEN_US = 2500
SG90_CLOSE_US = 500

MODE1_REG = 0x00
MODE2_REG = 0x01
PRESCALE_REG = 0xFE
LED0_ON_L = 0x06

# ===== I2C初期化 =====
i2c = I2C(
    I2C_ID,
    sda=Pin(SDA_PIN),
    scl=Pin(SCL_PIN),
    freq=I2C_FREQ
)

def log(message):
    print("[CHECK] " + str(message))

def read8(reg):
    return i2c.readfrom_mem(PCA_ADDR, reg, 1)[0]

def write8(reg, value):
    i2c.writeto_mem(PCA_ADDR, reg, bytes([value & 0xFF]))

def channel_reg(ch):
    return LED0_ON_L + 4 * ch

def pulse_to_count(pulse_us):
    return int(pulse_us * 4096 * PWM_FREQ / 1000000 + 0.5)

def set_pulse_us(ch, pulse_us):
    count = pulse_to_count(pulse_us)
    reg = channel_reg(ch)

    data = bytes([
        0,
        0,
        count & 0xFF,
        (count >> 8) & 0x0F
    ])

    i2c.writeto_mem(PCA_ADDR, reg, data)
    return count

def full_off(ch):
    reg = channel_reg(ch)
    i2c.writeto_mem(
        PCA_ADDR,
        reg,
        bytes([0, 0, 0, 0x10])
    )

def read_channel(ch):
    raw = i2c.readfrom_mem(
        PCA_ADDR,
        channel_reg(ch),
        4
    )

    on_count = raw[0] | ((raw[1] & 0x0F) << 8)
    off_count = raw[2] | ((raw[3] & 0x0F) << 8)

    full_on = bool(raw[1] & 0x10)
    full_off_flag = bool(raw[3] & 0x10)

    return raw, on_count, off_count, full_on, full_off_flag

# ===== A. I2C診断 =====
def check_i2c():
    log("===== A. I2C診断 =====")

    devices = i2c.scan()
    log("I2C scan = {}".format(
        [hex(x) for x in devices]
    ))

    if PCA_ADDR not in devices:
        log("NG: PCA9685が見つかりません")
        return False

    log("OK: PCA9685を検出しました")
    return True

# ===== B. PCA9685設定診断 =====
def configure_pca9685():
    log("===== B. PCA9685設定診断 =====")

    mode_before = read8(MODE1_REG)
    mode2 = read8(MODE2_REG)
    prescale_before = read8(PRESCALE_REG)

    log("MODE1 before = 0x{:02X}".format(mode_before))
    log("MODE2 = 0x{:02X}".format(mode2))
    log("PRESCALE before = {}".format(prescale_before))

    if mode_before & 0x40:
        log("注意: EXTCLK=1")
    if mode_before & 0x10:
        log("注意: SLEEP=1")

    # 内部クロックを使用して50Hzに設定
    # AI=1, SLEEP=1, EXTCLK=0
    write8(MODE1_REG, 0x30)
    time.sleep_ms(5)

    prescale = int(
        OSC_CLOCK / (4096 * PWM_FREQ) - 1 + 0.5
    )

    write8(PRESCALE_REG, prescale)

    # スリープ解除
    write8(MODE1_REG, 0x20)
    time.sleep_ms(5)

    # RESTART + AI
    write8(MODE1_REG, 0xA0)
    time.sleep_ms(5)

    mode_after = read8(MODE1_REG)
    prescale_after = read8(PRESCALE_REG)

    log("MODE1 after = 0x{:02X}".format(mode_after))
    log("PRESCALE after = {}".format(prescale_after))
    log("PRESCALE expected = {}".format(prescale))

    if mode_after & 0x50:
        log("NG: SLEEPまたはEXTCLKが有効です")
        return False

    if prescale_after != prescale:
        log("NG: PRESCALEが一致しません")
        return False

    log("OK: PCA9685設定完了")
    return True

# ===== C. PWMレジスタ診断 =====
def check_pwm_channel(ch, pulse_us):
    count = set_pulse_us(ch, pulse_us)

    raw, on_count, off_count, full_on, full_off_flag = read_channel(ch)

    log(
        "CH{} raw={} ON={} OFF={} FULL_ON={} FULL_OFF={}".format(
            ch,
            [hex(x) for x in raw],
            on_count,
            off_count,
            full_on,
            full_off_flag
        )
    )

    if (
        full_on
        or full_off_flag
        or on_count != 0
        or off_count != count
    ):
        log("NG: CH{} PWM読み戻し不一致".format(ch))
        return False

    log("OK: CH{} PWMレジスタ".format(ch))
    return True

def check_all_pwm():
    log("===== C. PWMレジスタ診断 =====")

    tests = [
        (SHAFT_CH, 1500),
        (SAND_CH, MG996R_90_US),
        (GATE_CH, 1500)
    ]

    result = True

    for ch, pulse in tests:
        if not check_pwm_channel(ch, pulse):
            result = False

        full_off(ch)

        raw, on_count, off_count, full_on, full_off_flag = read_channel(ch)

        log(
            "CH{} FULL_OFF確認: {}".format(
                ch,
                full_off_flag
            )
        )

        if not full_off_flag:
            result = False

    return result

# ===== D. GWS連続回転サーボ =====
def test_shaft():
    log("===== D. CH0 GWSサーボ試験 =====")

    reg = channel_reg(SHAFT_CH)

    # 既存motor.pyの設定に合わせる
    tests = [
        ("right", 225),
        ("left", 375)
    ]

    for direction, count in tests:
        data = bytes([
            0,
            0,
            count & 0xFF,
            (count >> 8) & 0x0F
        ])

        i2c.writeto_mem(PCA_ADDR, reg, data)

        log("CH0 {} count={}".format(
            direction,
            count
        ))

        time.sleep_ms(500)
        full_off(SHAFT_CH)
        time.sleep_ms(500)

    log("CH0の回転を目視確認してください")

# ===== E. MG996R =====
def test_mg996r():
    log("===== E. CH4 MG996R試験 =====")

    tests = [
        (0, MG996R_0_US),
        (90, MG996R_90_US),
        (180, MG996R_180_US)
    ]

    for angle, pulse in tests:
        count = set_pulse_us(SAND_CH, pulse)

        log("CH4 {}度: {}us count={}".format(
            angle,
            pulse,
            count
        ))

        time.sleep_ms(800)

    full_off(SAND_CH)

    log("MG996Rの動作を目視確認してください")

# ===== F. SG90 =====
def test_gate():
    log("===== F. CH8 SG90試験 =====")

    count = set_pulse_us(
        GATE_CH,
        SG90_OPEN_US
    )

    log("CH8 OPEN: {}us count={}".format(
        SG90_OPEN_US,
        count
    ))

    time.sleep_ms(800)

    count = set_pulse_us(
        GATE_CH,
        SG90_CLOSE_US
    )

    log("CH8 CLOSE: {}us count={}".format(
        SG90_CLOSE_US,
        count
    ))

    time.sleep_ms(800)

    full_off(GATE_CH)

    log("SG90の開閉を目視確認してください")

# ===== メイン処理 =====
def main():
    all_ok = True

    log("======================================")
    log(" Pico 2 W モーター系統 総合診断")
    log(" 外部サーボ電源: 6V想定")
    log("======================================")

    try:
        if not check_i2c():
            return

        if not configure_pca9685():
            return

        if not check_all_pwm():
            return

        log("===== A～C 自動診断完了 =====")
        log("レジスタ・通信設定に問題は見つかりませんでした")

        input(
            "実機動作試験を開始します。"
            "安全確認後 Enter。中止は Ctrl+C: "
        )

        test_shaft()
        test_mg996r()
        test_gate()

    except KeyboardInterrupt:
        log("中断されました")
        all_ok = False

    except Exception as e:
        log("診断中にエラー: {}".format(e))
        all_ok = False

    finally:
        for ch in (SHAFT_CH, SAND_CH, GATE_CH):
            try:
                full_off(ch)
            except Exception:
                pass

        log("全チャンネル FULL_OFF")
        log("診断終了")

main()

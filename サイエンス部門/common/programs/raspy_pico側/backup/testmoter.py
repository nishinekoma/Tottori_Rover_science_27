
import time
from machine import I2C, Pin

# ==========================================
# 1. 基本設定
# ==========================================

# I2C設定（Pico 2 W）
I2C_SDA = 0
I2C_SCL = 1
I2C_FREQ = 100000

# PCA9685
PCA_ADDRESS = 0x40
PWM_FREQ = 50

# 外部サーボ電源の設定電圧
# 注意：実測値ではなく、電源装置の設定値
SERVO_SUPPLY_VOLTAGE = 5.0

# チャンネル割り当て
SHAFT_CHANNEL = 0       # GWS S35 STD：360度連続回転
MICRO_CHANNEL = 4       # GWS Micro 2BBMG
SV90_CHANNEL = 8        # SV90

# サーボの名称
SERVO_NAMES = {
    SHAFT_CHANNEL: "GWS S35 STD（連続回転）",
    MICRO_CHANNEL: "GWS Micro 2BBMG",
    SV90_CHANNEL: "SV90"
}


# ==========================================
# 2. 動作時間設定
# ==========================================

# 連続回転サーボ
CONTINUOUS_TEST_SECONDS = 5

# 位置サーボの移動待ち時間
POSITION_WAIT_SECONDS = 1.0

# 同時動作時間
SIMULTANEOUS_TEST_SECONDS = 5


# ==========================================
# 3. パルス幅設定
# ==========================================

# 位置サーボ
POSITION_MIN_US = 1000
POSITION_MAX_US = 2000

# 連続回転サーボ
CONTINUOUS_FORWARD_US = 1000
CONTINUOUS_STOP_US = 1500
CONTINUOUS_REVERSE_US = 2000


# ==========================================
# 4. ログ機能
# ==========================================

START_TIME = time.ticks_ms()


def log(message):
    elapsed = time.ticks_diff(
        time.ticks_ms(), START_TIME
    )
    print("[{:>7} ms] {}".format(elapsed, message))


def log_servo_info():

    log("========== サーボ電源情報 ==========")

    log("外部サーボ電源設定値：{} V".format(
        SERVO_SUPPLY_VOLTAGE
    ))

    log("※実測電圧ではありません")
    log("※3台とも同じV+電源ラインから給電")
    log("------------------------------------")

    for channel in sorted(SERVO_NAMES):

        log(
            "CH{} | {} | 電源設定値：{} V".format(
                channel,
                SERVO_NAMES[channel],
                SERVO_SUPPLY_VOLTAGE
            )
        )

    log("====================================")


# ==========================================
# 5. PCA9685制御クラス
# ==========================================

class PCA9685:

    def __init__(self, i2c_bus, address=0x40):

        self.i2c = i2c_bus
        self.address = address

        self.i2c.writeto_mem(
            self.address, 0x00, b"\x00"
        )

    def set_freq(self, freq_hz):

        prescale = int(
            25000000.0 / 4096.0 / freq_hz - 1.0 + 0.5
        )

        oldmode = self.i2c.readfrom_mem(
            self.address, 0x00, 1
        )[0]

        newmode = (oldmode & 0x7F) | 0x10

        self.i2c.writeto_mem(
            self.address, 0x00, bytes([newmode])
        )

        self.i2c.writeto_mem(
            self.address, 0xFE, bytes([prescale])
        )

        self.i2c.writeto_mem(
            self.address, 0x00, bytes([oldmode])
        )

        time.sleep_ms(1)

        self.i2c.writeto_mem(
            self.address, 0x00, bytes([oldmode | 0xA1])
        )

    def set_pwm(self, channel, on_time, off_time):

        data = bytearray([
            on_time & 0xFF,
            (on_time >> 8) & 0xFF,
            off_time & 0xFF,
            (off_time >> 8) & 0xFF
        ])

        self.i2c.writeto_mem(
            self.address,
            0x06 + 4 * channel,
            data
        )

    def set_pulse_us(self, channel, pulse_us):

        # 50Hz：1周期 = 20,000us
        count = int(pulse_us * 4096 / 20000)

        self.set_pwm(channel, 0, count)

    def force_stop(self, channel):

        # PCA9685のFull OFF機能を使用
        self.set_pwm(channel, 0, 4096)


# ==========================================
# 6. サーボ制御
# ==========================================

def set_position_servo(pca, channel, angle):

    angle = max(0, min(180, angle))

    pulse_us = int(
        POSITION_MIN_US
        + (POSITION_MAX_US - POSITION_MIN_US)
        * angle / 180
    )

    pca.set_pulse_us(channel, pulse_us)

    log(
        "CH{} | {} | 角度={}度 | パルス={}us".format(
            channel,
            SERVO_NAMES[channel],
            angle,
            pulse_us
        )
    )


def set_continuous_servo(pca, channel, direction):

    if direction == "forward":
        pulse = CONTINUOUS_FORWARD_US

    elif direction == "reverse":
        pulse = CONTINUOUS_REVERSE_US

    else:
        pulse = CONTINUOUS_STOP_US

    pca.set_pulse_us(channel, pulse)

    log(
        "CH{} | {} | 回転指令={} | パルス={}us".format(
            channel,
            SERVO_NAMES[channel],
            direction,
            pulse
        )
    )


# ==========================================
# 7. 停止処理
# ==========================================

def stop_servo(pca, channel):

    name = SERVO_NAMES[channel]

    if channel == SHAFT_CHANNEL:

        # 連続回転サーボには停止パルスを送る
        set_continuous_servo(
            pca, channel, "stop"
        )

        # 停止パルスを少し維持する
        time.sleep_ms(300)

    # PWM出力OFF
    pca.force_stop(channel)

    log(
        "CH{} | {} | PWM出力OFF".format(
            channel, name
        )
    )


def stop_all_servos(pca):

    log("========== 全サーボ停止処理 ==========")

    for channel in [
        SHAFT_CHANNEL,
        MICRO_CHANNEL,
        SV90_CHANNEL
    ]:
        stop_servo(pca, channel)

    log("全チャンネルの停止処理完了")
    log("======================================")


# ==========================================
# 8. TEST 1-1：シャフト用サーボ
# ==========================================

def test_shaft(pca):

    channel = SHAFT_CHANNEL

    log("========== TEST 1-1：シャフト用 ==========")

    # 正方向
    log("正方向に{}秒回転".format(
        CONTINUOUS_TEST_SECONDS
    ))

    set_continuous_servo(
        pca, channel, "forward"
    )

    time.sleep(CONTINUOUS_TEST_SECONDS)

    stop_servo(pca, channel)
    time.sleep(0.5)

    # 逆方向
    log("逆方向に{}秒回転".format(
        CONTINUOUS_TEST_SECONDS
    ))

    set_continuous_servo(
        pca, channel, "reverse"
    )

    time.sleep(CONTINUOUS_TEST_SECONDS)

    stop_servo(pca, channel)

    log("TEST 1-1 終了")


# ==========================================
# 9. TEST 1-2：位置サーボ
# ==========================================

def test_position_servo(pca, channel):

    name = SERVO_NAMES[channel]

    log("========== TEST 1：{} ==========".format(
        name
    ))

    # 0度 → 180度 → 0度 → 180度
    angles = [0, 180, 0, 180]

    for angle in angles:

        set_position_servo(
            pca, channel, angle
        )

        time.sleep(POSITION_WAIT_SECONDS)

    # 初期位置（0度）に戻す
    log("CH{} | 初期位置（0度）に戻します".format(channel))

    set_position_servo(
        pca, channel, 0
    )

    time.sleep(POSITION_WAIT_SECONDS)

    # PWM出力OFF
    stop_servo(pca, channel)

    log("CH{} テスト終了".format(channel))


# ==========================================
# 10. TEST 2：CH0 + CH8 同時動作
# ==========================================

def test_simultaneous(pca):

    log("========== TEST 2：CH0 + CH8 同時動作 ==========")

    log("CH0正方向回転 + CH8角度変更")

    # CH0を正方向へ
    set_continuous_servo(
        pca, SHAFT_CHANNEL, "forward"
    )

    # CH8を0度へ
    set_position_servo(
        pca, SV90_CHANNEL, 0
    )

    start_time = time.ticks_ms()

    angles = [180, 0, 180, 0]

    for angle in angles:

        elapsed = time.ticks_diff(
            time.ticks_ms(), start_time
        )

        if elapsed >= SIMULTANEOUS_TEST_SECONDS * 1000:
            break

        set_position_servo(
            pca, SV90_CHANNEL, angle
        )

        time.sleep(POSITION_WAIT_SECONDS)

    # 残り時間を計算
    elapsed = time.ticks_diff(
        time.ticks_ms(), start_time
    )

    remaining = (
        SIMULTANEOUS_TEST_SECONDS * 1000 - elapsed
    )

    if remaining > 0:
        time.sleep_ms(remaining)

    # CH0を停止
    stop_servo(pca, SHAFT_CHANNEL)

    # CH8を初期位置（0度）に戻す
    log("CH8 | 初期位置（0度）に戻します")

    set_position_servo(
        pca, SV90_CHANNEL, 0
    )

    time.sleep(POSITION_WAIT_SECONDS)

    # CH8のPWM出力OFF
    stop_servo(pca, SV90_CHANNEL)

    log("TEST 2 終了")


# ==========================================
# 11. メイン処理
# ==========================================

def main():

    log("======================================")
    log(" サーボモーター動作テスト開始")
    log("======================================")

    log_servo_info()

    pca = None

    try:

        log("I2C初期化中...")

        i2c = I2C(
            0,
            sda=Pin(I2C_SDA),
            scl=Pin(I2C_SCL),
            freq=I2C_FREQ
        )

        devices = i2c.scan()

        if PCA_ADDRESS not in devices:

            log("[ERROR] PCA9685が見つかりません")

            log("検出されたI2Cアドレス：{}".format(
                devices
            ))

            return

        log("PCA9685検出：0x{:02X}".format(
            PCA_ADDRESS
        ))

        pca = PCA9685(i2c, PCA_ADDRESS)

        pca.set_freq(PWM_FREQ)

        log("PWM周波数：{} Hz".format(PWM_FREQ))

        # ----------------------------------
        # 初期停止
        # ----------------------------------

        log("初期停止処理")

        stop_all_servos(pca)

        time.sleep(0.5)

        # ----------------------------------
        # TEST 1：個別動作
        # ----------------------------------

        log("######## TEST 1：個別動作 ########")

        # CH0：連続回転
        test_shaft(pca)

        # CH4：GWS Micro 2BBMG
        test_position_servo(
            pca, MICRO_CHANNEL
        )

        # CH8：SV90
        test_position_servo(
            pca, SV90_CHANNEL
        )

        # ----------------------------------
        # TEST 2：同時動作
        # ----------------------------------

        log("######## TEST 2：同時動作 ########")

        test_simultaneous(pca)

        log("全テスト完了")

    except Exception as e:

        log("[ERROR] {}".format(e))

    finally:

        # ----------------------------------
        # 最終停止処理
        # ----------------------------------

        if pca is not None:

            try:
                stop_all_servos(pca)

            except Exception as e:
                log("[STOP ERROR] {}".format(e))

        log("サーボモーター動作テスト終了")


# ==========================================
# 12. 実行
# ==========================================

if __name__ == "__main__":
    main()


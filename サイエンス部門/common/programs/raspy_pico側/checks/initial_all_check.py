# 初期値チェック.py
# Pico 2 W用：配線・初期設定・センサーを事前確認してから main.py を実行する
#
# 重要：
# - main.py / motor.py / distance.py / temperature.py は変更しません。
# - 異常が1つでもあれば main.py は実行せず停止します。
# - 配線図.txtに記載された「物理ピン番号」と「GP番号」の不一致も検出対象です。

import time
import re
from machine import Pin, I2C

# ============================================================
# 配線図・現在のmain.pyに基づく期待値
# ============================================================

I2C_ID = 0
I2C_SDA_GP = 0
I2C_SCL_GP = 1
I2C_FREQ = 100000
PCA_ADDRESS = 0x40

TRIG_GP = 19
ECHO_GP = 15
TEMP_DATA_GP = 16

SHAFT_CHANNEL = 0
SAND_CHANNEL = 4
GATE_CHANNEL = 8

MAIN_FILE = "main.py"
MOTOR_FILE = "motor.py"
DISTANCE_FILE = "distance.py"
TEMPERATURE_FILE = "temperature.py"

# main.pyで現在使用している設定値
EXPECTED_MAIN_VALUES = {
    "DISTANCE_SAMPLES": 5,
    "SHAFT_SPEED": 100,
    "MARGIN_CM": 2.0,
    "INITIAL_OFFSET_CM": 18.0,
    "GATE_OPEN_WAIT_SEC": 1.0,
    "SAND_WAIT_BEFORE_SEC": 1.0,
    "SAND_WAIT_AFTER_SEC": 1.0,
    "GATE_CLOSE_HOLD_SEC": 0.5,
    "GATE_CLOSE_BEFORE_RETRACT_END_SEC": 2.0,
    "RETRACT_EXTRA_SECONDS": 4.0,
    "TEMP_TOLERANCE": 0.01,
    "TEMP_STABLE_SEC": 15.0,
    "TEMP_MAX_WAIT_SEC": 180,
    "TEMP_IGNORE_SEC": 1.0,
}

# motor.pyで現在使用している設定値
EXPECTED_MOTOR_VALUES = {
    "I2C_ID": 0,
    "I2C_SDA": 0,
    "I2C_SCL": 1,
    "I2C_FREQ": 100000,
    "PCA_ADDRESS": 0x40,
    "PWM_FREQ": 50,
    "SHAFT_CHANNEL": 0,
    "SAND_CHANNEL": 4,
    "GATE_CHANNEL": 8,
    "SPEED_CM_PER_SEC": 5.25,
    "GATE_OPEN_PULSE_US": 2500,
    "GATE_CLOSED_PULSE_US": 500,
    "SAND_0_DEG_PULSE_US": 571,
    "SAND_180_DEG_PULSE_US": 2411,
}

errors = []
warnings = []

def log(message):
    print(message)

def fail(message):
    errors.append(message)
    print("[NG] " + message)

def ok(message):
    print("[OK] " + message)

def read_file(path):
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as exc:
        fail("{}を読み込めません: {}".format(path, exc))
        return None

def find_assignment(source, name):
    # 例：NAME = 12 / NAME = 12.5
    pattern = r"(?m)^\s*" + re.escape(name) + r"\s*=\s*([^#\r\n]+)"
    match = re.search(pattern, source)
    if not match:
        return None
    value = match.group(1).strip()
    try:
        return eval(value, {}, {})
    except Exception:
        return value

def check_values(label, source, expected_values):
    log("")
    log("[" + label + "] 設定値確認")
    if source is None:
        return

    for name, expected in expected_values.items():
        actual = find_assignment(source, name)
        if actual is None:
            fail("{}: {} の設定が見つかりません".format(label, name))
        elif actual != expected:
            fail("{}: {} が不一致（現在={} / 期待={}）".format(
                label, name, actual, expected
            ))
        else:
            ok("{}: {} = {}".format(label, name, actual))

def check_pin_mapping():
    log("")
    log("[配線図] 物理ピン番号とGP番号の照合")

    # Raspberry Pi Pico 2 Wの物理ピン配置
    # 物理19=GP14、物理20=GP15、物理21=GP16、物理25=GP19
    physical_to_gp = {
        1: 0,
        2: 1,
        19: 14,
        20: 15,
        21: 16,
        25: 19,
        36: "3V3(OUT)",
        38: "GND",
        39: "VSYS",
    }

    # 配線図の記述：
    # 「超音波trig -- rasp pin19 ... GP19」
    diagram_trig_physical = 19
    actual_gp_at_diagram_pin = physical_to_gp[diagram_trig_physical]

    if actual_gp_at_diagram_pin != TRIG_GP:
        fail(
            "超音波TRIGの配線図に不一致があります。"
            "配線図は物理ピン19ですが、物理ピン19はGP14です。"
            "現在のdistance.py想定GP19に接続するなら物理ピン25です。"
        )
        log("       選択肢A：TRIG線を物理ピン25（GP19）へ移す")
        log("       選択肢B：TRIG線を物理ピン19（GP14）に残し、"
            "distance.pyのTRIG設定をGP14へ変更する")
    else:
        ok("TRIGの物理ピンとGP番号が一致")

    # ECHOは物理20=GP15という配線図記述と整合
    if physical_to_gp[20] == ECHO_GP:
        ok("ECHO：物理ピン20 = GP15（分圧回路経由）")
    else:
        fail("ECHOの物理ピン番号とGP番号が不一致")

    if physical_to_gp[21] == TEMP_DATA_GP:
        ok("温度DATA：物理ピン21 = GP16")
    else:
        fail("温度DATAの物理ピン番号とGP番号が不一致")

    if physical_to_gp[1] == I2C_SDA_GP and physical_to_gp[2] == I2C_SCL_GP:
        ok("PCA9685 I2C：物理1=GP0(SDA)、物理2=GP1(SCL)")
    else:
        fail("PCA9685 I2Cの物理ピン番号とGP番号が不一致")

    ok("PCA9685電源：物理36=3.3V(OUT)、物理38=GND")
    ok("超音波電源：配線図記載の物理39=VSYS")
    warnings.append(
        "超音波VCCは物理39(VSYS)接続の記載。"
        "センサーの定格電圧と実際の電圧は別途確認してください。"
    )

def check_i2c():
    log("")
    log("[ハードウェア] PCA9685 I2C確認")
    try:
        i2c = I2C(
            I2C_ID,
            sda=Pin(I2C_SDA_GP),
            scl=Pin(I2C_SCL_GP),
            freq=I2C_FREQ
        )
        devices = i2c.scan()
        log("I2C scan: {}".format(
            ["0x{:02X}".format(x) for x in devices]
        ))

        if PCA_ADDRESS not in devices:
            fail("PCA9685 0x40が見つかりません")
            return

        ok("PCA9685 0x40を検出")

        mode1 = i2c.readfrom_mem(PCA_ADDRESS, 0x00, 1)[0]
        prescale = i2c.readfrom_mem(PCA_ADDRESS, 0xFE, 1)[0]

        log("PCA9685 MODE1=0x{:02X}, PRESCALE={}".format(
            mode1, prescale
        ))

        if mode1 & 0x10:
            fail("PCA9685がSLEEP状態です")
        elif mode1 & 0x40:
            fail("PCA9685でEXTCLKが有効です")
        else:
            ok("PCA9685のSLEEP/EXTCLK状態は正常")

        # 25MHz内部クロック、50Hz設定の期待値は121
        if prescale != 121:
            fail("PCA9685 PRESCALEが121ではありません")
        else:
            ok("PCA9685 50Hz設定（PRESCALE=121）")

    except Exception as exc:
        fail("I2C確認中に例外: {}".format(exc))

def check_distance_sensor():
    log("")
    log("[センサー] 超音波センサー確認")
    try:
        from distance import get_stable_distance
        log("TRIG想定: GP{}".format(TRIG_GP))
        log("ECHO想定: GP{}（分圧回路経由）".format(ECHO_GP))
        log("安定距離測定を5サンプルで実行します")

        distance = get_stable_distance(samples=5)

        if distance is None:
            fail("超音波センサーから距離を取得できません")
        elif distance <= 0 or distance > 400:
            fail("距離値が想定範囲外です: {}".format(distance))
        else:
            ok("距離測定成功: {:.2f} cm".format(distance))
    except Exception as exc:
        fail("超音波センサー確認中に例外: {}".format(exc))

def check_temperature_sensor():
    log("")
    log("[センサー] 温度センサー確認")
    log("配線図のDATAは物理ピン21 = GP16")
    try:
        import onewire
        import ds18x20

        pin = Pin(TEMP_DATA_GP)
        bus = ds18x20.DS18X20(onewire.OneWire(pin))
        roms = bus.scan()

        log("DS18B20検出数: {}".format(len(roms)))

        if not roms:
            fail("GP16でDS18B20が検出されません")
        else:
            ok("DS18B20を検出")
            bus.convert_temp()
            time.sleep_ms(750)
            for index, rom in enumerate(roms):
                temp = bus.read_temp(rom)
                log("温度センサー{}: {:.3f} °C".format(index + 1, temp))
                if temp < -55 or temp > 125:
                    fail("温度値がDS18B20の範囲外です")
    except ImportError:
        fail("onewire / ds18x20モジュールを読み込めません")
    except Exception as exc:
        fail("温度センサー確認中に例外: {}".format(exc))

def main():
    log("")
    log("========================================")
    log("       初期値・配線チェック開始")
    log("========================================")

    main_source = read_file(MAIN_FILE)
    motor_source = read_file(MOTOR_FILE)
    distance_source = read_file(DISTANCE_FILE)
    temperature_source = read_file(TEMPERATURE_FILE)

    check_values("main.py", main_source, EXPECTED_MAIN_VALUES)
    check_values("motor.py", motor_source, EXPECTED_MOTOR_VALUES)

    log("")
    log("[distance.py] ピン設定の確認")
    if distance_source is not None:
        if "19" not in distance_source or "15" not in distance_source:
            fail("distance.pyにGP19/TRIGまたはGP15/ECHOの設定が見つかりません。内容を確認してください")
        else:
            ok("distance.pyにGP19/GP15の番号が記載されています（定義方法の詳細は目視確認が必要）")

    log("")
    log("[temperature.py] ピン設定の確認")
    if temperature_source is not None:
        if "16" not in temperature_source:
            fail("temperature.pyにGP16の設定が見つかりません")
        else:
            ok("temperature.pyにGP16の番号が記載されています（定義方法の詳細は目視確認が必要）")

    check_pin_mapping()
    check_i2c()

    # センサー試験は配線の不一致がない場合に限り実施
    if not errors:
        check_distance_sensor()
        check_temperature_sensor()
    else:
        log("")
        log("[SKIP] 配線・設定の不一致があるためセンサー試験をスキップ")

    log("")
    log("========================================")
    log("       初期チェック結果")
    log("========================================")

    for warning in warnings:
        log("[WARNING] " + warning)

    if errors:
        log("")
        log("[STOP] 異常が{}件あります。main.pyは実行しません。".format(len(errors)))
        for item in errors:
            log(" - " + item)
        log("")
        log("配線または設定を修正してから、もう一度実行してください。")
        return

    log("[PASS] 事前チェックはすべて通過しました")
    log("")
    log("これから main.py を実行します。")
    log("")

    try:
        with open(MAIN_FILE, "r") as f:
            main_code = f.read()
        exec(main_code, {"__name__": "__main__"})
    except Exception as exc:
        log("[MAIN ERROR] main.py実行中に例外: {}".format(exc))

main()

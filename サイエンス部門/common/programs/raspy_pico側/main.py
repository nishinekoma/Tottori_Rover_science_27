
import time

from motor import (
    create_pca,
    set_gate_open,
    set_gate_closed,
    set_sand_pulse,
    move_arm_by_distance,
    retract_arm_with_gate_close,
    stop_all_outputs,
    SAND_0_DEG_PULSE_US,
    SAND_180_DEG_PULSE_US,
    SAND_CHANNEL,
    GATE_CHANNEL,
)

from distance import get_stable_distance
from temperature import measure_until_stable


# ===== 動作設定 =====
DISTANCE_SAMPLES = 5

SHAFT_DIRECTION_OUT = "right"
SHAFT_DIRECTION_RETURN = "left"
SHAFT_SPEED = 100

MARGIN_CM = 2.0
INITIAL_OFFSET_CM = 18.0 #debug車２０デフォ

GATE_OPEN_WAIT_SEC = 1.0

SAND_WAIT_BEFORE_SEC = 1.0
SAND_WAIT_AFTER_SEC = 1.0

GATE_CLOSE_HOLD_SEC = 0.5
GATE_CLOSE_BEFORE_RETRACT_END_SEC = 2.0

RETRACT_EXTRA_SECONDS = 4.0

TEMP_TOLERANCE = 0.01
TEMP_STABLE_SEC = 15.0
TEMP_MAX_WAIT_SEC = 180
TEMP_IGNORE_SEC = 1.0

LOG_FILE = "log_result.csv"

START_TICKS = time.ticks_ms()


# ===== ログ処理 =====
def log_event(**kwargs):
    elapsed = (
        time.ticks_diff(
            time.ticks_ms(),
            START_TICKS
        ) / 1000.0
    )

    fields = [
        str(kwargs.get("phase", "")),
        str(kwargs.get("distance", "")),
        str(kwargs.get("temp", "")),
        str(kwargs.get("detail", "")),
    ]

    fields = [
        v.replace(",", " ").replace("\n", " ")
        for v in fields
    ]

    line = "{:.2f},{},{},{},{}\n".format(
        elapsed,
        fields[0],
        fields[1],
        fields[2],
        fields[3]
    )

    print("[LOG] " + line.strip())

    try:
        with open(LOG_FILE, "a") as f:
            f.write(line)

    except Exception as exc:
        print(
            "[LOG Error] CSV保存失敗: {}".format(exc)
        )


def init_log_file():
    try:
        with open(LOG_FILE, "w") as f:
            f.write(
                "elapsed_sec,phase,distance_cm,temp_c,detail\n"
            )

        print(
            "[LOG] {} を作成しました".format(LOG_FILE)
        )

    except Exception as exc:
        print(
            "[LOG Error] CSV初期化失敗: {}".format(exc)
        )


# ===== メインシーケンス =====
def run_sequence():
    pca = None
    shaft_move_cm = 0.0
    gate_closed = False

    try:
        print("\n=== Pico 2 W 単体動作開始 ===")

        log_event(
            phase="開始",
            detail="Thonny Runで単体実行"
        )

        # 1. PCA9685初期化
        pca = create_pca()
        pca.disable_all_motors()

        print("[1] PCA9685初期化完了")

        log_event(
            phase="初期化完了"
        )

        # 2. 砂採取機構を180度にする
        print("[2] 砂採取機構: 2411usを指令")

        set_sand_pulse(
            pca,
            SAND_180_DEG_PULSE_US
        )

        log_event(
            phase="砂採取機構180度指令",
            detail="CH4 2411us"
        )

        # 3. 距離測定
        print("[3] 距離測定")

        distance_cm = get_stable_distance(
            samples=DISTANCE_SAMPLES
        )

        if distance_cm is None:
            raise RuntimeError(
                "距離を取得できませんでした"
            )

        print(
            "[Distance] {:.2f} cm".format(distance_cm)
        )

        log_event(
            phase="距離測定完了",
            distance="{:.2f}".format(distance_cm)
        )

        shaft_move_cm = (
            distance_cm
            + MARGIN_CM
            - INITIAL_OFFSET_CM
        )

        if shaft_move_cm <= 0:
            raise RuntimeError(
                "算出シャフト移動距離が0以下です: {:.2f} cm".format(
                    shaft_move_cm
                )
            )

        # 4. ゲートを開く
        print("[4] 開閉機構を開きます")

        set_gate_open(pca)

        log_event(
            phase="ゲート開",
            detail="CH8"
        )

        time.sleep(GATE_OPEN_WAIT_SEC)

        # 5. シャフト伸長
        print(
            "[5] シャフト伸長: {:.2f} cm相当".format(
                shaft_move_cm
            )
        )

        log_event(
            phase="シャフト伸長開始",
            distance="{:.2f}".format(shaft_move_cm)
        )

        move_arm_by_distance(
            distance_cm=distance_cm,
            direction=SHAFT_DIRECTION_OUT,
            speed=SHAFT_SPEED,
            margin_cm=MARGIN_CM,
            initial_offset_cm=INITIAL_OFFSET_CM,
            pca=pca
        )

        print("[5] シャフト伸長完了")

        log_event(
            phase="シャフト伸長完了"
        )

        # 6. 温度測定
        print("[6] 土壌温度測定")

        log_event(
            phase="温度測定開始"
        )

        temperature = None

        try:
            temperature = measure_until_stable(
                tolerance=TEMP_TOLERANCE,
                stable_duration_sec=TEMP_STABLE_SEC,
                max_wait_sec=TEMP_MAX_WAIT_SEC,
                ignore_sec=TEMP_IGNORE_SEC,
                log_func=log_event
            )

        except Exception as exc:
            print(
                "[Temperature Warning] 温度測定エラー: {}".format(
                    exc
                )
            )

            log_event(
                phase="温度測定失敗",
                detail="例外: {}".format(exc)
            )

        if temperature is None:
            print(
                "[Temperature Warning] 温度なしで続行します"
            )

            log_event(
                phase="温度測定失敗",
                detail="温度なしで続行"
            )

        else:
            print(
                "[Temperature] {:.3f} °C".format(
                    temperature
                )
            )

            log_event(
                phase="温度測定完了",
                temp="{:.3f}".format(temperature)
            )

        # 7. 温度測定後に1秒待機
        print("[7] 砂採取動作前に1秒待機")

        time.sleep(SAND_WAIT_BEFORE_SEC)

        # 8. 砂採取機構を0度に戻す
        print("[8] 砂採取機構: 571usを指令")

        set_sand_pulse(
            pca,
            SAND_0_DEG_PULSE_US
        )

        log_event(
            phase="砂採取機構0度指令",
            detail="CH4 571us"
        )

        # 9. 砂採取動作後に1秒待機
        print("[9] シャフト格納前に1秒待機")

        time.sleep(SAND_WAIT_AFTER_SEC)

        # 10. シャフト格納終了2秒前にゲートを閉じる
        def close_gate():
            nonlocal gate_closed

            print("[Gate] シャフト格納終了2秒前：ゲートを閉じます")

            set_gate_closed(pca)
            gate_closed = True

            log_event(
                phase="ゲート閉指令",
                detail="シャフト格納終了2秒前"
            )

        print("[10] シャフト格納開始")

        log_event(
            phase="シャフト格納開始",
            distance="{:.2f}".format(shaft_move_cm)
        )

        retract_time = retract_arm_with_gate_close(
            move_cm=shaft_move_cm,
            extra_seconds=RETRACT_EXTRA_SECONDS,
            close_gate_before_end_sec=GATE_CLOSE_BEFORE_RETRACT_END_SEC,
            direction=SHAFT_DIRECTION_RETURN,
            speed=SHAFT_SPEED,
            gate_close_callback=close_gate,
            pca=pca
        )

        print(
            "[10] シャフト格納完了: {:.2f}秒".format(
                retract_time
            )
        )

        log_event(
            phase="シャフト格納完了",
            detail="実動作時間 {:.2f}s".format(
                retract_time
            )
        )

        # 念のため、コールバックが実行されなかった場合は閉じる
        if not gate_closed:
            print("[Gate] ゲートを閉じます")

            set_gate_closed(pca)
            gate_closed = True

            log_event(
                phase="ゲート閉指令",
                detail="格納完了後の安全処理"
            )

        # ゲートは閉じた状態で0.5秒保持
        time.sleep(GATE_CLOSE_HOLD_SEC)

        pca.force_stop(GATE_CHANNEL)

        print("[Gate] CH8 PWM停止")

        log_event(
            phase="ゲートPWM停止"
        )

        # 砂採取サーボのPWM停止
        pca.force_stop(SAND_CHANNEL)

        print("[Sand] CH4 PWM停止")

        log_event(
            phase="砂採取サーボPWM停止"
        )

        print("=== 全シーケンス完了 ===")

        log_event(
            phase="完了"
        )

    except KeyboardInterrupt:
        print("[中断] Thonnyから実行を中断しました")

        log_event(
            phase="中断",
            detail="KeyboardInterrupt"
        )

    except Exception as exc:
        print(
            "[ERROR] {}".format(exc)
        )

        log_event(
            phase="エラー",
            detail=str(exc)
        )

    finally:
        if pca is not None:
            try:
                stop_all_outputs(pca)

                print(
                    "[安全処理] CH0/CH4/CH8のPWM出力を停止しました"
                )

            except Exception as exc:
                print(
                    "[安全処理エラー] {}".format(exc)
                )

        log_event(
            phase="終了処理"
        )


def main():
    global START_TICKS

    START_TICKS = time.ticks_ms()

    init_log_file()

    run_sequence()


main()


import machine
import time
from distance import get_stable_distance
from motor import move_arm_by_distance, retract_arm_simple
from temperature import measure_until_stable

LOG_FILE = "log_result.csv"
START_TICKS = time.ticks_ms()

# === UART設定 (UART1, 物理Pin6=GP4(TX), 物理Pin7=GP5(RX), ボーレート115200) ===
uart = machine.UART(1, baudrate=115200, tx=machine.Pin(4), rx=machine.Pin(5))

def send_to_pi5(msg):
    """Raspberry Pi 5 へ文字列を送信し、Picoのコンソールにも出力する"""
    print(msg)
    try:
        uart.write(f"{msg}\n".encode('utf-8'))
    except:
        pass

def log_event(phase, dist_measured="", moved_cm="", margin_cm="", temp="", detail=""):
    """Pico内部CSVへの保存と、Pi 5へのリアルタイム行送信"""
    elapsed_sec = time.ticks_diff(time.ticks_ms(), START_TICKS) / 1000.0
    dt = machine.RTC().datetime()
    time_str = f"{dt[4]:02d}:{dt[5]:02d}:{dt[6]:02d}"

    line = f'"{elapsed_sec:.2f}","{time_str}","{phase}","{dist_measured}","{moved_cm}","{margin_cm}","{temp}","{detail}"\n'
    
    # 1. Pico内ローカル保存
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line)
    except Exception as e:
        send_to_pi5(f"[Log Error] 書き込み失敗: {e}")

    # 2. Pi 5 へも同じ行データを送信
    send_to_pi5(f"[LOG]{line.strip()}")

def init_log_file():
    """BOM付きUTF-8で初期化"""
    header = '"経過時間(秒)","時刻(時:分:秒)","フェーズ","測定距離(cm)","移動量(cm)","予備分(cm)","温度(℃)","詳細"\n'
    file_exists = False
    try:
        with open(LOG_FILE, "r") as f:
            if len(f.read(10)) > 0:
                file_exists = True
    except OSError:
        pass

    if not file_exists:
        with open(LOG_FILE, "wb") as f:
            f.write(b"\xef\xbb\xbf")
        with open(LOG_FILE, "a") as f:
            f.write(header)
    else:
        with open(LOG_FILE, "a") as f:
            f.write('\n"---","---","新規テスト開始(START)","---","---","---","---","---"\n')
            f.write(header)


def run_sequence():
    """Pi 5からSTARTを受信したときに走る探査シーケンス"""
    global START_TICKS
    START_TICKS = time.ticks_ms()
    
    actual_moved_cm = 0.0
    error_reason = None

    send_to_pi5("==========================================")
    send_to_pi5("   鳥取ローバー 科学探査班 結合テスト (UART駆動)")
    send_to_pi5("==========================================")

    init_log_file()
    log_event(phase="シーケンス開始", detail="テスト開始")

    try:
        # 1. 地面からの距離測定
        send_to_pi5("\n【Step 1】 超音波センサーで距離を計測中...")
        dist = get_stable_distance(samples=5)
        if dist is None:
            error_reason = "超音波距離取得失敗"
            log_event(phase="超音波エラー", detail=error_reason)
            return

        send_to_pi5(f">> 地面までの測定距離: {dist:.1f} cm")
        log_event(phase="超音波計測完了", dist_measured=f"{dist:.1f}", detail="地面検知成功")

        # 2. モーター展開動作
        margin = 8.0
        initial_offset = 9.0
        send_to_pi5("\n【Step 2】 アームを展開します...")
        log_event(phase="モーター展開開始", dist_measured=f"{dist:.1f}", margin_cm=f"{margin:.1f}", detail=f"目標=(測定+{margin})-初期{initial_offset}")

        ret = move_arm_by_distance(
            distance_cm=dist, direction="right", speed=100, margin_cm=margin, initial_offset_cm=initial_offset
        )

        if ret is False:
            error_reason = "モーター展開失敗"
            log_event(phase="モーターエラー", detail=error_reason)
            return
        
        actual_moved_cm = ret
        send_to_pi5(f">> モーター展開完了: 実際に動かした距離 = {actual_moved_cm:.1f} cm")
        log_event(phase="モーター展開完了", moved_cm=f"{actual_moved_cm:.1f}", margin_cm=f"{margin:.1f}", detail="土壌到達位置まで展開完了")

        # 3. 温度測定 (10秒無視 ＋ 10秒間同じ温度かつ0.01以内)
        send_to_pi5("\n【Step 3】 土壌温度の測定開始 (10秒維持・0.01℃以内)...")
        final_temp = measure_until_stable(
            tolerance=0.01, stable_duration_sec=10.0, max_wait_sec=180, ignore_sec=10.0, log_func=log_event
        )

        # 4. モーター引き戻し
        send_to_pi5("\n【Step 4】 アームを巻き戻します...")
        if actual_moved_cm > 0:
            log_event(phase="モーター格納開始", moved_cm=f"{actual_moved_cm:.1f}", detail="引き戻し開始")
            retract_arm_simple(move_cm=actual_moved_cm, direction="left", speed=100)
            log_event(phase="モーター格納完了", moved_cm=f"{actual_moved_cm:.1f}", detail="初期位置へ復元完了")
            actual_moved_cm = 0.0
        else:
            send_to_pi5("展開量0のためスキップ")

        # 5. 測定結果ログ
        send_to_pi5("\n==========================================")
        if final_temp is not None:
            send_to_pi5(f"【テスト成功】 確定土壌温度: {final_temp:.3f} °C")
            log_event(phase="全シーケンス完了", dist_measured=f"{dist:.1f}", moved_cm=f"{ret:.1f}", temp=f"{final_temp:.3f}", detail="正常完了")
        else:
            error_reason = "温度未収束タイムアウト"
            send_to_pi5("【テスト失敗】 温度が収束しませんでした")
            log_event(phase="全シーケンス終了", detail=error_reason)
        send_to_pi5("==========================================")

    except Exception as e:
        error_reason = f"プログラム例外: {e}"
        send_to_pi5(f"[CRITICAL ERROR] {error_reason}")
        log_event(phase="致命的エラー", detail=str(e))

    finally:
        # 万が一途中でエラーになっても、アームが出ていれば緊急巻き戻し
        if actual_moved_cm > 0:
            send_to_pi5("[Safety] エラー中断のため、展開アームを緊急巻き戻しします...")
            try:
                retract_arm_simple(move_cm=actual_moved_cm, direction="left", speed=100)
            except:
                pass

        # 正常・エラー問わず、Pi 5へ終了シグナルを必ず送信
        if error_reason:
            send_to_pi5(f"SEQUENCE_ERROR: {error_reason}")
        else:
            send_to_pi5("SEQUENCE_FINISHED")


def main():
    print("UARTコマンド待機中... (Pi 5からの 'START' を待ち受けます)")
    while True:
        if uart.any():
            cmd = uart.readline().decode('utf-8', errors='ignore').strip()
            if cmd == "START":
                run_sequence()
                print("\nUARTコマンド待機状態に戻ります...")
        time.sleep(0.1)


if __name__ == "__main__":
    main()
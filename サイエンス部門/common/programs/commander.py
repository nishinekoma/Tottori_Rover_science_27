import serial
import time
import os

SERIAL_PORT = '/dev/ttyAMA4'
BAUDRATE = 115200
SAVE_CSV_FILE = 'pico_log_result.csv'

TOTAL_TIMEOUT_SEC = 210.0   # 全体タイムアウト
NO_DATA_TIMEOUT_SEC = 35.0  # 通信途絶タイムアウト

def run_science_mission():
    """
    Picoへ開始コマンドを送り、シーケンス監視・ログ保存を行う。
    成功時 True、失敗/タイムアウト時 False を返す。
    """
    print(f"[{SERIAL_PORT}] Picoへ接続中...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
    except Exception as e:
        print(f"[Error] シリアルポートオープン失敗: {e}")
        return False

    # コマンド送信
    ser.write(b'START\n')
    print(">> Picoへ 'START' コマンドを送信しました。")

    # CSVヘッダー準備 (新規時のみBOM付きで作成)
    if not os.path.exists(SAVE_CSV_FILE):
        with open(SAVE_CSV_FILE, "wb") as f:
            f.write(b"\xef\xbb\xbf")
        with open(SAVE_CSV_FILE, "a", encoding="utf-8") as f:
            f.write('"経過時間(秒)","時刻(時:分:秒)","フェーズ","測定距離(cm)","移動量(cm)","予備分(cm)","温度(℃)","詳細"\n')

    start_time = time.time()
    last_recv_time = time.time()
    success = False

    try:
        while True:
            now = time.time()

            # タイムアウト監視
            if (now - start_time) > TOTAL_TIMEOUT_SEC:
                print(f"\n[Warning] 全体タイムアウト ({TOTAL_TIMEOUT_SEC}s) 到達。シーケンスを中断します。")
                break
            if (now - last_recv_time) > NO_DATA_TIMEOUT_SEC:
                print(f"\n[Warning] 通信途絶タイムアウト ({NO_DATA_TIMEOUT_SEC}s)。シーケンスを中断します。")
                break

            # データ受信処理
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='replace').strip()
                last_recv_time = time.time()

                if not line:
                    continue

                if line == "SEQUENCE_FINISHED":
                    print("\n>> 【Pico 正常完了】を受信しました。")
                    success = True
                    break
                elif line.startswith("SEQUENCE_ERROR:"):
                    print(f"\n>> 【Pico エラー終了】を受信しました: {line}")
                    success = False
                    break
                elif line.startswith("[LOG]"):
                    csv_row = line.replace("[LOG]", "")
                    with open(SAVE_CSV_FILE, "a", encoding="utf-8") as f:
                        f.write(csv_row + "\n")
                else:
                    print(f"[Pico] {line}")

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n>> 手動中断されました。")
    finally:
        ser.close()

    return success

if __name__ == '__main__':
    result = run_science_mission()
    print(f">> 科学探査シーケンス結果: {result}")
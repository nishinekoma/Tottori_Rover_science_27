import os
import time
import serial

SERIAL_PORT = "/dev/ttyAMA4"
BAUDRATE = 9600
SAVE_CSV_FILE = "pico_log_result.csv"

TOTAL_TIMEOUT_SEC = 210.0  # シーケンス全体の最大許容時間（秒）
NO_DATA_TIMEOUT_SEC = 35.0  # 応答途絶タイムアウト（秒）
MAX_START_RETRIES = 5  # STARTコマンドの最大送信試行回数


def run_science_mission():
  print(f"[{SERIAL_PORT}] Picoへ接続中 (ボーレート: {BAUDRATE})...")
  try:
    ser = serial.Serial(
        port=SERIAL_PORT, baudrate=BAUDRATE, timeout=0.5, write_timeout=1.0
    )
  except Exception as e:
    print(f"[Error] シリアルポートオープン失敗: {e}")
    return False

  # 受信バッファのクリア
  ser.reset_input_buffer()
  ser.reset_output_buffer()
  time.sleep(0.3)

  # CSVヘッダーの初期化
  if not os.path.exists(SAVE_CSV_FILE):
    with open(SAVE_CSV_FILE, "wb") as f:
      f.write(b"\xef\xbb\xbf")
    with open(SAVE_CSV_FILE, "a", encoding="utf-8") as f:
      f.write(
          '"経過時間(秒)","時刻(時:分:秒)","フェーズ","測定距離(cm)","移動量(cm)","予備分(cm)","温度(℃)","詳細"\n'
      )

  # START コマンド送信
  connected = False
  print(">> Picoへ 'START' コマンドを送信中...")

  for attempt in range(1, MAX_START_RETRIES + 1):
    ser.write(b"START\r\n")
    ser.flush()
    print(
        f"   [試行 {attempt}/{MAX_START_RETRIES}] 'START' 送信。Picoの応答待機..."
    )

    wait_start = time.time()
    while time.time() - wait_start < 1.5:
      if ser.in_waiting > 0:
        connected = True
        break
      time.sleep(0.05)

    if connected:
      print(">> Picoからの応答を受信！探査ログの受信を開始します。\n")
      break

  if not connected:
    print("\n[Error] Picoが 'START' に反応しませんでした。")
    ser.close()
    return False

  start_time = time.time()
  last_recv_time = time.time()
  success = False

  try:
    while True:
      now = time.time()

      if (now - start_time) > TOTAL_TIMEOUT_SEC:
        print(
            f"\n[Warning] 全体タイムアウト ({TOTAL_TIMEOUT_SEC}s)"
            " 到達。シーケンスを中断します。"
        )
        break
      if (now - last_recv_time) > NO_DATA_TIMEOUT_SEC:
        print(
            f"\n[Warning] 通信途絶タイムアウト ({NO_DATA_TIMEOUT_SEC}s)。シーケンスを中断します。"
        )
        break

      if ser.in_waiting > 0:
        raw_line = ser.readline()
        last_recv_time = time.time()

        if not raw_line:
          continue

        line = raw_line.decode("utf-8", errors="replace").strip()

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
          print(f"[探査ログ] {csv_row}")
        else:
          print(f"[Pico] {line}")

      time.sleep(0.01)

  except KeyboardInterrupt:
    print("\n>> 手動中断 (Ctrl+C) されました。")
  finally:
    ser.close()
    print(">> シリアルポートを閉じました。")

  return success


if __name__ == "__main__":
  result = run_science_mission()
  print(f">> 科学探査シーケンス結果: {result}")
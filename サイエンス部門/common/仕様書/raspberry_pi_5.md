# Raspberry Pi 5 結合・通信仕様書 (科学探査班)

本ドキュメントは、Raspberry Pi 5(メイン)とPico W(サブ: 昇降・温度測定)のUART通信による結合仕様をまとめたものです。

## 1. 物理配線仕様 (UART4 クロス接続)
Pi 5のUART4を使用します。TX/RXは交差(クロス)させ、GNDは必ず接続してください。

* **Pi 5 Pin 32 (GPIO 12 / TXD4)** -> Pico Pin 7 (GP5 / RX)
* **Pi 5 Pin 33 (GPIO 13 / RXD4)** -> Pico Pin 6 (GP4 / TX)
* **Pi 5 Pin 14 (GND)** -> Pico Pin 8 (GND) ※基準電位合わせに必須
* **Pi 5 Pin 2 (5V)** -> Pico Pin 39 (VSYS) ※Pi 5から給電する場合

## 2. Pi 5 OS設定 (UART4有効化)
初期状態では無効なため、有効化が必要です。

1. `sudo nano /boot/firmware/config.txt` を実行
2. 末尾に `dtoverlay=uart4` を追記して保存
3. `sudo reboot` で再起動
4. `ls -l /dev/ttyAMA4` でデバイスファイルが存在することを確認

## 3. 通信プロトコル
* **ポート設定**: `/dev/ttyAMA4`
* **通信規格**: `115200 bps`, `8N1` (データ8bit, パリティなし, ストップ1bit)
* **改行コード**: `\n` (LF)

### 送受信コマンド仕様
* **[Pi 5 -> Pico] 開始コマンド**: 
  * `START\n` を送信すると、Picoが自律シーケンスを開始します。
* **[Pico -> Pi 5] 受信データ**:
  * **通常文字**: `[Pico] 〇〇...` (コンソール表示用)
  * **ログ行**: `[LOG]"経過時間","時刻","フェーズ","距離","移動量","予備分","温度","詳細"` 
    * ※ `[LOG]` を除去し、ローカルのCSVファイルに追記してください。
  * **正常終了**: `SEQUENCE_FINISHED\n` (検知後、次タスクへ移行)
  * **異常終了**: `SEQUENCE_ERROR: <エラー理由>\n` (検知後、次タスクへ移行)

## 4. Pi 5側 実装要件 (フリーズ防止策)
ローバーのメイン処理がPicoのトラブルで停止しないよう、以下のハンドリングを実装してください。

1. **終了シグナル検知**: `SEQUENCE_FINISHED` または `SEQUENCE_ERROR` を受信次第、通信ループを抜ける。
2. **CSVローカル保存**: `[LOG]` で始まる行を検知し、Pi 5側に `pico_log_result.csv` として保存(UTF-8推奨)。
3. **二重タイムアウト (フェイルセーフ)**:
   * **全体最大タイムアウト (210秒)**: Picoの最大稼働時間を超えたら強制終了。
   * **無通信タイムアウト (35秒)**: Picoからのデータ送信が途絶えたら回線切断と判断し強制終了。

---
## 参考: Python実装例 (`commander.py`)
`pyserial`ライブラリ (`pip install pyserial`) を使用した実装例です。メイン処理のサブ関数として組み込んでください。

```python
import serial
import time
import os

SERIAL_PORT = '/dev/ttyAMA4'
BAUDRATE = 115200
SAVE_CSV_FILE = 'pico_log_result.csv'
TOTAL_TIMEOUT_SEC = 210.0
NO_DATA_TIMEOUT_SEC = 35.0

def run_science_mission():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
    except Exception as e:
        print(f"[Error] ポートエラー: {e}")
        return False

    ser.write(b'START\n')

    # CSVヘッダー準備
    if not os.path.exists(SAVE_CSV_FILE):
        with open(SAVE_CSV_FILE, "wb") as f:
            f.write(b"\xef\xbb\xbf") # UTF-8 BOM
        with open(SAVE_CSV_FILE, "a", encoding="utf-8") as f:
            f.write('"経過時間(秒)","時刻(時:分:秒)","フェーズ","測定距離(cm)","移動量(cm)","予備分(cm)","温度(℃)","詳細"\n')

    start_time = last_recv_time = time.time()
    success = False

    try:
        while True:
            now = time.time()
            if (now - start_time) > TOTAL_TIMEOUT_SEC or (now - last_recv_time) > NO_DATA_TIMEOUT_SEC:
                print("\n[Warning] タイムアウトにより通信中断")
                break

            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='replace').strip()
                last_recv_time = time.time()
                if not line: continue

                if line == "SEQUENCE_FINISHED":
                    success = True
                    break
                elif line.startswith("SEQUENCE_ERROR:"):
                    print(f"\n[Pico Error] {line}")
                    break
                elif line.startswith("[LOG]"):
                    with open(SAVE_CSV_FILE, "a", encoding="utf-8") as f:
                        f.write(line.replace("[LOG]", "") + "\n")
                else:
                    print(f"[Pico] {line}")
            time.sleep(0.01)
    finally:
        ser.close()

    return success

if __name__ == '__main__':
    run_science_mission()
from distance import get_stable_distance
import machine
from motor import move_arm_by_distance, retract_arm_simple
from temperature import measure_until_stable
import time

LOG_FILE = "log_result.csv"
START_TICKS = time.ticks_ms()


def log_event(
    phase,
    dist_measured="",
    moved_cm="",
    margin_cm="",
    temp="",
    detail="",
):
    """Excelの列ズレを防ぐため各セルをクォートして追記する"""
    elapsed_sec = time.ticks_diff(time.ticks_ms(), START_TICKS) / 1000.0

    # Pico内蔵RTCから時刻を取得
    dt = machine.RTC().datetime()
    time_str = f"{dt[4]:02d}:{dt[5]:02d}:{dt[6]:02d}"

    # カンマ区切りの列ズレ防止のためダブルクォーテーションで囲む
    line = f'"{elapsed_sec:.2f}","{time_str}","{phase}","{dist_measured}","{moved_cm}","{margin_cm}","{temp}","{detail}"\n'

    try:
        with open(LOG_FILE, "a") as f:
            f.write(line)
    except Exception as e:
        print(f"[Log Error] 書き込み失敗: {e}")


def init_log_file():
    """Excelの文字化けを防ぐため UTF-8 BOM を付与して初期化する"""
    header = '"経過時間(秒)","時刻(時:分:秒)","フェーズ","測定距離(cm)","移動量(cm)","予備分(cm)","温度(℃)","詳細"\n'
    try:
        file_exists = False
        try:
            with open(LOG_FILE, "r") as f:
                content = f.read(10)
                if len(content) > 0:
                    file_exists = True
        except OSError:
            file_exists = False

        if not file_exists:
            # 新規作成時: UTF-8 BOM (\xef\xbb\xbf) を先頭に書き込むことでExcel文字化けを完全防止
            with open(LOG_FILE, "wb") as f:
                f.write(b"\xef\xbb\xbf")
            with open(LOG_FILE, "a") as f:
                f.write(header)
        else:
            with open(LOG_FILE, "a") as f:
                f.write(
                    '\n"---","---","新規テスト開始(START)","---","---","---","---","---"\n'
                )
                f.write(header)
    except Exception as e:
        print(f"[Log Init Error] {e}")


def main():
    # ==========================================
    # 【追加】PC接続時のUSB認識を妨げないための待機時間
    print("起動待機中... 3秒後にテストを開始します。")
    print("※プログラムを編集・停止する場合は、今のうちにThonnyのSTOPボタン(赤色)を押してください。")
    time.sleep(6)
    # ==========================================

    print("==========================================")
    print("   鳥取ローバー 科学探査班 結合テスト")
    print("==========================================")

    init_log_file()
    log_event(phase="シーケンス開始", detail="テスト開始")

    # 1. 地面からの距離測定
    print("\n【Step 1】 超音波センサーで距離を計測中...")
    dist = get_stable_distance(samples=5)

    if dist is None:
        print("エラー: 距離測定に失敗しました。")
        log_event(phase="超音波エラー", detail="距離取得失敗")
        return

    print(f">> 地面までの測定距離: {dist:.1f} cm")
    log_event(
        phase="超音波計測完了",
        dist_measured=f"{dist:.1f}",
        detail="地面検知成功",
    )

    # 2. モーター展開動作
    margin = 8.0
    initial_offset = 9.0

    print("\n【Step 2】 アームを展開します...")
    log_event(
        phase="モーター展開開始",
        dist_measured=f"{dist:.1f}",
        margin_cm=f"{margin:.1f}",
        detail=f"目標=(測定+{margin})-初期{initial_offset}",
    )

    actual_moved_cm = move_arm_by_distance(
        distance_cm=dist,
        direction="right",
        speed=100,
        margin_cm=margin,
        initial_offset_cm=initial_offset,
    )

    if actual_moved_cm is False:
        print("エラー: モーター駆動に失敗しました。")
        log_event(phase="モーターエラー", detail="展開失敗")
        return

    print(f">> モーター展開完了: 実際に動かした距離 = {actual_moved_cm:.1f} cm")
    log_event(
        phase="モーター展開完了",
        moved_cm=f"{actual_moved_cm:.1f}",
        margin_cm=f"{margin:.1f}",
        detail="土壌到達位置まで展開完了",
    )

    # 3. 温度測定 (10秒無視 ＋ 10秒間同じ温度かつ0.01以内)
    print("\n【Step 3】 土壌温度の測定開始 (10秒維持・0.01℃以内)...")
    final_temp = measure_until_stable(
        tolerance=0.01,  # 0.01℃以内の変動
        stable_duration_sec=10.0,  # 10秒間キープ
        max_wait_sec=180,
        ignore_sec=10.0,  # 最初の10秒無視
        log_func=log_event,
    )

    # 4. モーターを移動した分戻す
    print("\n【Step 4】 アームを巻き戻します...")
    if actual_moved_cm > 0:
        log_event(
            phase="モーター格納開始",
            moved_cm=f"{actual_moved_cm:.1f}",
            detail="引き戻し開始",
        )
        retract_arm_simple(move_cm=actual_moved_cm, direction="left", speed=100)
        log_event(
            phase="モーター格納完了",
            moved_cm=f"{actual_moved_cm:.1f}",
            detail="初期位置へ復元完了",
        )
    else:
        print("展開量0のためスキップ")

    # 5. 最終結果出力
    print("\n==========================================")
    if final_temp is not None:
        print(f"【テスト成功】 確定土壌温度: {final_temp:.3f} °C")
        log_event(
            phase="全シーケンス完了",
            dist_measured=f"{dist:.1f}",
            moved_cm=f"{actual_moved_cm:.1f}",
            temp=f"{final_temp:.3f}",
            detail="正常完了",
        )
    else:
        print("【テスト失敗】 温度が収束しませんでした")
        log_event(phase="全シーケンス終了", detail="温度未収束")
    print("==========================================")


if __name__ == "__main__":
    main()
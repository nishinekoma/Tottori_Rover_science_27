import ds18x20
import machine
import onewire
import time


def measure_until_stable(
    tolerance=0.01,
    stable_duration_sec=10.0,
    max_wait_sec=180,
    ignore_sec=10.0,
    log_func=None,
):
    """開始10秒間は判定を無視し、その後「10秒間連続して変動幅が0.01℃以内」になったら収束判定とします。"""
    gp_pin = machine.Pin(16)
    ds_sensor = ds18x20.DS18X20(onewire.OneWire(gp_pin))

    roms = ds_sensor.scan()
    if not roms:
        print("[Temp Error] 温度センサーが見つかりません。")
        if log_func:
            log_func(phase="温度エラー", detail="センサー未検出")
        return None

    rom = roms[0]
    print(f"[Temp] センサー認識: {roms}")
    print(
        f"[Temp] 測定開始 (最初の{ignore_sec}s無視 -> 以降{stable_duration_sec}秒間 差分{tolerance}℃以内)"
    )

    history = []
    start_time = time.time()

    while (time.time() - start_time) < max_wait_sec:
        elapsed = time.time() - start_time

        # 温度変換 (約750ms待機)
        ds_sensor.convert_temp()
        time.sleep_ms(750)

        temp = ds_sensor.read_temp(rom)
        history.append((elapsed, temp))

        # 【条件1】最初の10秒間は無効期間として無視
        if elapsed < ignore_sec:
            detail_msg = f"初期安定待ち (経過: {elapsed:.1f}s)"
            print(f"[Temp] {elapsed:.1f}s | {temp:.3f} °C (無効期間)")
            if log_func:
                log_func(
                    phase="温度測定中",
                    temp=f"{temp:.3f}",
                    detail=detail_msg,
                )
            time.sleep(0.5)
            continue

        # 【条件2】直近10秒間のデータを抽出して変動チェック
        recent_data = [
            t
            for (t_elapsed, t) in history
            if (elapsed - t_elapsed) <= stable_duration_sec
        ]
        valid_duration = (
            elapsed - history[-len(recent_data)][0] if recent_data else 0
        )

        diff = max(recent_data) - min(recent_data)
        detail_msg = f"10秒変動幅: {diff:.3f}℃"
        print(f"[Temp] {elapsed:.1f}s | {temp:.3f} °C ({detail_msg})")

        if log_func:
            log_func(
                phase="温度測定中", temp=f"{temp:.3f}", detail=detail_msg
            )

        # 10秒分のデータが溜まり、かつ最大・最小差が 0.01℃ 以内なら収束！
        if valid_duration >= stable_duration_sec and diff <= tolerance:
            print(
                f"[Temp] ★収束達成！ ({stable_duration_sec}秒間 変動幅: {diff:.3f}℃ <= {tolerance}℃)"
            )
            if log_func:
                log_func(
                    phase="温度収束達成",
                    temp=f"{temp:.3f}",
                    detail=f"安定確定(変動幅:{diff:.3f}℃)",
                )
            return temp

        time.sleep(0.5)

    print("[Temp Warning] 制限時間内に収束しませんでした。")
    if log_func:
        log_func(
            phase="温度タイムアウト",
            temp=f"{history[-1][1]:.3f}" if history else "",
            detail="最大時間到達",
        )
    return history[-1][1] if history else None
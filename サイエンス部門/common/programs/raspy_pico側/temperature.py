import ds18x20
import machine
import onewire
import time
from motor import StopRequested


def _sleep_interruptible_ms(duration_ms, stop_check):
    remaining = duration_ms
    while remaining > 0:
        if stop_check is not None and stop_check():
            raise StopRequested("STOP requested")
        interval = min(25, remaining)
        time.sleep_ms(interval)
        remaining -= interval

    if stop_check is not None and stop_check():
        raise StopRequested("STOP requested")


def measure_until_stable(
    tolerance=0.01,
    stable_duration_sec=10.0,
    max_wait_sec=180,
    ignore_sec=1.0,
    log_func=None,
    stop_check=None,
):
    """温度が指定時間以上安定したら測定を終了する。"""

    gp_pin = machine.Pin(16)
    ds_sensor = ds18x20.DS18X20(onewire.OneWire(gp_pin))
    roms = ds_sensor.scan()

    if not roms:
        print("[Temp Error] 温度センサーが見つかりません。")
        if log_func:
            log_func(
                phase="温度エラー",
                detail="センサー未検出"
            )
        return None

    rom = roms[0]
    print("[Temp] センサー認識: {}".format(roms))

    history = []
    start_ms = time.ticks_ms()
    max_wait_ms = int(max_wait_sec * 1000)

    # 測定間隔のずれを考慮して、安定判定用の履歴を12秒保持する
    window_sec = stable_duration_sec + 2.0

    while time.ticks_diff(time.ticks_ms(), start_ms) < max_wait_ms:

        if stop_check is not None and stop_check():
            raise StopRequested("STOP requested")

        ds_sensor.convert_temp()
        _sleep_interruptible_ms(750, stop_check)

        temp = ds_sensor.read_temp(rom)

        # 測定時刻を取得
        elapsed = time.ticks_diff(
            time.ticks_ms(), start_ms
        ) / 1000.0

        # 異常値チェック
        if temp is None or temp != temp:
            print("[Temp Warning] 不正な温度値を受信しました")
            _sleep_interruptible_ms(500, stop_check)
            continue

        history.append((elapsed, temp))

        # 初期安定待ち
        if elapsed < ignore_sec:
            detail = "初期安定待ち (経過: {:.1f}s)".format(elapsed)

            print(
                "[Temp] {:.1f}s | {:.3f} °C (無効期間)".format(
                    elapsed, temp
                )
            )

            if log_func:
                log_func(
                    phase="温度測定中",
                    temp="{:.3f}".format(temp),
                    detail=detail
                )

            _sleep_interruptible_ms(500, stop_check)
            continue

        # 直近12秒以内の測定値を取得
        recent = [
            (t, value)
            for t, value in history
            if elapsed - t <= window_sec
        ]

        if recent:
            valid_duration = elapsed - recent[0][0]
            values = [value for _, value in recent]
            diff = max(values) - min(values)
        else:
            valid_duration = 0.0
            diff = float("inf")

        detail = (
            "変動幅: {:.3f}℃ / 判定時間: {:.1f}s"
        ).format(diff, valid_duration)

        print(
            "[Temp] {:.1f}s | {:.3f} °C ({})".format(
                elapsed, temp, detail
            )
        )

        if log_func:
            log_func(
                phase="温度測定中",
                temp="{:.3f}".format(temp),
                detail=detail
            )

        # 10秒以上の測定履歴があり、変動幅が許容範囲内なら終了
        if (
            valid_duration >= stable_duration_sec
            and diff <= tolerance
        ):
            print("[Temp] 温度収束を確認しました。")

            if log_func:
                log_func(
                    phase="温度収束達成",
                    temp="{:.3f}".format(temp),
                    detail="安定確定(変動幅:{:.3f}℃)".format(diff)
                )

            return temp

        _sleep_interruptible_ms(500, stop_check)

    # 最大待機時間に到達
    print("[Temp Warning] 制限時間内に収束しませんでした。")

    last_temp = history[-1][1] if history else None

    if log_func:
        log_func(
            phase="温度タイムアウト",
            temp="{:.3f}".format(last_temp) if last_temp is not None else "",
            detail="最大時間到達"
        )

    return last_temp

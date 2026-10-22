import time
from machine import Pin

# --- ピン設定 ---
trig = Pin(14, Pin.OUT)
echo = Pin(15, Pin.IN)

trig.value(0)
time.sleep_us(5)


def get_distance():
  """超音波センサーで距離(cm)を1回計測（残響クリア＆タイムアウト対策版）"""
  # 1. 前回の残響対策：Echoが0に落ち着くまで最大10ms待機
  clear_start = time.ticks_us()
  while echo.value() == 1:
    if time.ticks_diff(time.ticks_us(), clear_start) > 10000:
      return None  # ピンが戻らない場合はスキップ

  # 2. トリガーパルス送信 (10µs)
  trig.value(0)
  time.sleep_us(2)
  trig.value(1)
  time.sleep_us(10)
  trig.value(0)

  # 3. Echoの立ち上がり待ち (最大30ms)
  timeout_start = time.ticks_us()
  while echo.value() == 0:
    if time.ticks_diff(time.ticks_us(), timeout_start) > 30000:
      return None

  signal_start = time.ticks_us()

  # 4. Echoの立ち下がり待ち (最大45ms: 約7.7m相当まで許容)
  while echo.value() == 1:
    if time.ticks_diff(time.ticks_us(), signal_start) > 45000:
      return None

  signal_end = time.ticks_us()

  duration = time.ticks_diff(signal_end, signal_start)
  distance = (duration * 0.0343) / 2

  # 物理的な有効範囲（2cm〜400cm）外はノイズとして除外
  if 2.0 <= distance <= 400.0:
    return distance
  return None


def get_stable_distance(samples=7):
  """複数回計測し、有効値の中央値（または平均）を返す"""
  valid_samples = []

  for _ in range(samples):
    d = get_distance()
    if d is not None:
      valid_samples.append(d)
    time.sleep(0.06)  # 残響減衰のため60ms間隔

  if not valid_samples:
    return None

  # 外れ値を除去するためソートして中央値を採用
  valid_samples.sort()
  return valid_samples[len(valid_samples) // 2]
import time
from motor import create_pca, SHAFT_CHANNEL

# CH0（シャフト用）を1秒だけ動かすテスト
DIRECTION = "right"  # 逆方向を試す場合は "left"
SPEED = 100
RUN_TIME_SEC = 1.0

pca = None

try:
    print("PCA9685初期化")
    pca = create_pca()

    print("CH0を{}方向・速度{}で{}秒動かします".format(
        DIRECTION, SPEED, RUN_TIME_SEC
    ))

    pca.force_stop(SHAFT_CHANNEL)
    pca.spin(SHAFT_CHANNEL, direction=DIRECTION, speed=SPEED)
    time.sleep_ms(int(RUN_TIME_SEC * 1000))

    print("1秒経過。モーター停止")

finally:
    if pca is not None:
        pca.force_stop(SHAFT_CHANNEL)
        print("CH0停止完了")


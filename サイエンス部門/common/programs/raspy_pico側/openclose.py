import time
from motor import (
    create_pca,
    set_gate_open,
    set_gate_closed,
    GATE_CHANNEL,
)

# "open" で開く / "close" で閉じる
#ACTION = "open"
ACTION = "close"
pca = None
try:
    print("PCA9685初期化")
    pca = create_pca()
    if ACTION == "open":
        print("開閉機構を開きます")
        set_gate_open(pca)
        print("開いた位置の保持指令を継続します。")
    elif ACTION == "close":
        print("開閉機構を閉じます")
        try:
            set_gate_closed(pca)
            time.sleep(0.1)
        finally:
            pca.force_stop(GATE_CHANNEL)
        print("0.5秒後にCH8のPWM出力を停止しました。")
    else:
        raise ValueError('ACTIONは "open" または "close" を指定してください。')
except Exception as exc:
    print("[ERROR] {}".format(exc))
    raise

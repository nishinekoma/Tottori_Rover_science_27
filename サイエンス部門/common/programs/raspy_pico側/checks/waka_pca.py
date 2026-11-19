from machine import I2C, Pin
import time

i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=100000)

addr = 0x40

def read_reg(reg):
    return i2c.readfrom_mem(addr, reg, 1)[0]

def write_reg(reg, value):
    i2c.writeto_mem(addr, reg, bytes([value]))

print("=== PCA9685 Wake Up ===")

# 現在の状態
mode1 = read_reg(0x00)
print("MODE1 before =", hex(mode1))

# SLEEP状態を維持して50HzのPRESCALEを設定
write_reg(0x00, 0x11)
time.sleep_ms(5)
write_reg(0xFE, 121)

# SLEEP解除（内部クロック使用、ALLCALL有効）
write_reg(0x00, 0x01)
time.sleep_ms(5)

# 設定確認
mode1 = read_reg(0x00)
prescale = read_reg(0xFE)

print("MODE1 after =", hex(mode1))
print("PRESCALE =", prescale)
print("EXTCLK =", (mode1 >> 6) & 1)
print("SLEEP =", (mode1 >> 4) & 1)

if (mode1 & 0x50) == 0 and prescale == 121:
    print("OK: PCA9685 50Hz設定完了")
else:
    print("NG: 設定を確認してください")

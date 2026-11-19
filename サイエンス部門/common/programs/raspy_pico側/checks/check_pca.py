from machine import I2C, Pin
import time

i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=100000)

PCA_ADDR = 0x40

print("=== PCA9685 Software Reset ===")

devices = i2c.scan()
print("I2C devices:", [hex(x) for x in devices])

if PCA_ADDR not in devices:
    print("ERROR: PCA9685 not found")
else:
    # PCA9685 Software Reset command
    # General Call address 0x00, reset command 0x06
    print("Sending software reset...")
    i2c.writeto(0x00, b"\x06")

    time.sleep_ms(100)

    mode1 = i2c.readfrom_mem(PCA_ADDR, 0x00, 1)[0]
    mode2 = i2c.readfrom_mem(PCA_ADDR, 0x01, 1)[0]
    prescale = i2c.readfrom_mem(PCA_ADDR, 0xFE, 1)[0]

    print("MODE1 =", hex(mode1))
    print("MODE2 =", hex(mode2))
    print("PRESCALE =", prescale)
    print("EXTCLK =", (mode1 >> 6) & 1)
    print("SLEEP =", (mode1 >> 4) & 1)

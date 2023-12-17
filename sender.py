"""
A simple Python script to send messages to a sever over Bluetooth
using PyBluez (with Python 2).
"""

import bluetooth
import random
import time
import smbus

bus = smbus.SMBus(1)

ADC_ADDRESS = 0x4b

serverMACAddress = 'D8:3A:DD:3C:D9:91'
port = 4
s = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
s.connect((serverMACAddress, port))

while True:
    data = bus.read_i2c_block_data(ADC_ADDRESS, 0)
    #data = [random.randrange(0,255)]
    print(data[0])
    s.send(str(data[0]))

    time.sleep(0.25)
#sock.close()

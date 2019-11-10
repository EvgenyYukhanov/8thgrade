# Leaks detection with ESP8266
# Device Side
## Devices
1. ESP8266
2. DHT22 sensor
3. Homemade leak detector - two wires connected to ADC
## Language
Micropython 1.11
## Tools
### picocom
sudo dnf install picocom
sudo picocom /dev/ttyUSB0 -b 115200
Note:
Ctrl-A Ctrl-X to disconnect
### ampy (Adafruit Micropython Toolkit)
sudo python3 -m pip install adafruit-ampy

sudo ampy -p /dev/ttyUSB0 -b 115200 ls

sudo ampy -p /dev/ttyUSB0 -b 115200 put main.py
# Server Side
- ec2
- python3
- Cloud9 (very cool for prototyping)
- KMS (Key Management Service for secrets decryption)
# Security
ESP8266 Micropython doesn't support certificates verification, so we are open to MITM attack.
## Mitigation
### Sign device messages
Used poor-man signing - sha1(message+device_secret)
### Prevent replay attacks
Since ESP8266 has no clock, we are using a ticket issues by the service as a part of the message and signature. Server rotates the tickets once per minute.

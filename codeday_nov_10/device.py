import machine
import dht
import time
import network
import socket
import hashlib
import binascii
import ussl

# Read config
WIFI_AP, WIFI_PASSWORD, DEVICE_SECRET, HOST = open('config').readline().split()
# the last ticket issued by the server
last_ticket = "unknown"
# the wifi connection
wifi = None


def connect_wifi(ap, password):
    """Connects/reconnects WIFI"""
    global wifi
    if wifi and wifi.isconnected:
        return True

    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    wifi.connect(ap, password)
    wifi.ifconfig()
    for attempt in range(100):
        if wifi.isconnected():
            return True
        time.sleep(0.1)
    return False


def simple_sign(message, secret):
    """naive signing"""
    plain_text = (secret + message).encode()
    signature = hashlib.sha1(plain_text)
    return binascii.hexlify(signature.digest()).decode('utf-8')


def post_msg(host, port, message):
    """Sings and posts the message to specified host and port"""
    global last_ticket

    # attach the last known ticket and the signature
    msg_and_ticket = '{0} {1}'.format(message, last_ticket)
    body = '{0} {1}'.format(msg_and_ticket, simple_sign(msg_and_ticket, DEVICE_SECRET)).encode()

    # connect WIFI if required
    if not connect_wifi(WIFI_AP, WIFI_PASSWORD):
        # skip this measurement
        return

    # establish connection
    s = socket.socket()
    s.settimeout(2.0)
    s.connect(socket.getaddrinfo(host, port)[0][-1])
    s = ussl.wrap_socket(s)

    # Example of a request
    # POST / HTTP/1.1
    # Content-Length: 5
    #
    # <message> <last_ticket> <signature>
    s.write(b'POST / HTTP/1.1\r\n')
    s.write('Content-Length: {0}\r\n'.format(len(body)).encode())
    s.write(b'\r\n')
    s.write(body)

    # read response to find X-Ticket header
    rsp = s.read(1024)
    s.close()
    lines = rsp.decode('utf-8').split('\r\n')
    for l in lines:
        if l.startswith('X-Ticket:'):
            last_ticket = l.split(': ')[-1]


# DHT22 sensor is on PIN4 (D2)
dht_sensor = dht.DHT22(machine.Pin(4))
# Analog->Digital converter is on A0
adc = machine.ADC(0)

while True:
    time.sleep(1)
    try:
        dht_sensor.measure()
        post_msg(HOST, 11917, "{0} {1} {2}".format(dht_sensor.humidity(), dht_sensor.temperature(), adc.read()))
    except:
        pass

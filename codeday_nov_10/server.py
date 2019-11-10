from http.server import HTTPServer, BaseHTTPRequestHandler
import slack
import boto3
import hashlib
import binascii
import base64
import uuid
import time
import ssl

DEVICE_SECRET = (
        'AQICAHhAMXl8LQyZj4coXAr+By+EfV5Vk/L7SPsw489b5rB39wHpt58Ygp2PTIDx5gE5GE3jAAAA' +
        'gzCBgAYJKoZIhvcNAQcGoHMwcQIBADBsBgkqhkiG9w0BBwEwHgYJYIZIAWUDBAEuMBEEDKptWKhZ' +
        'hYzo7N1vRAIBEIA/IUJDGESxaJvhbvWmAEokJMPjZ5oWsiub7kQEVtp9kY5+hzttM78Vz6WPfdb7' +
        'okL9dRvGuYlSloKD3aAbnDRB'
)

SLACK_TOKEN = (
        'AQICAHhAMXl8LQyZj4coXAr+By+EfV5Vk/L7SPsw489b5rB39wGANj2NfrRVIMvweQDGpTdRAAAA' +
        'rjCBqwYJKoZIhvcNAQcGoIGdMIGaAgEAMIGUBgkqhkiG9w0BBwEwHgYJYIZIAWUDBAEuMBEEDK9S' +
        '5olYIKZTcnQpSgIBEIBnf4ABkMJqoRcKEuraraExb0eqUN5x1CXGzxciOLlaKGNN02xaY/QYXxbN' +
        'jdancwMfasomYWiT6OnXrLzNotxvvLGW109FyoZby+OFHMHo5y/1CFp/7PGd8ckroJiEcJNWBwen' +
        'JVxiXQ=='
)

# a KMS client to decrypt secrets
kms = boto3.client('kms', region_name='us-west-2')


def decrypt(cipher64):
    """decrypts a message in base64 format"""
    cipher = base64.decodebytes(cipher64.encode())
    return kms.decrypt(CiphertextBlob=cipher)['Plaintext']


def simple_sign(message, secret):
    """naive signing"""
    plain_text = (secret + message).encode()
    signature = hashlib.sha1(plain_text)
    return binascii.hexlify(signature.digest()).decode('utf-8')


# slack token to be able to send slack messages to our channel
slack_token = decrypt(SLACK_TOKEN).decode('utf-8')
client = slack.WebClient(token=slack_token)

# device secret for signing requests
device_secret = decrypt(DEVICE_SECRET).decode('utf-8')

# we will give device a new ticket every minute to avoid replay attack
last_ticket = uuid.uuid4().hex
last_ticket_refresh_time = time.monotonic()


def refresh_ticket():
    """refreshes device ticket every minute"""
    global last_ticket, last_ticket_refresh_time
    if time.monotonic() - last_ticket_refresh_time > 60:
        last_ticket_refresh_time = time.monotonic()
        last_ticket = uuid.uuid4().hex


def has_valid_signature(msg, secret):
    """check if the message has a valid signature

    msg is in "humidity temperature leak ticket signature" format
    """
    humidity, temperature, leak, ticket, signature = msg.split()
    if ticket != last_ticket:
        return False
    msg = "{0} {1} {2} {3}".format(humidity, temperature, leak, ticket)
    expected = simple_sign(msg, secret)
    return expected == signature


class Listener(BaseHTTPRequestHandler):
    """Web server implementation"""

    def do_POST(self):
        # refresh the ticket if required
        refresh_ticket()

        # read the body
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length).decode('utf-8')

        # expected body format is "humidity temperature leak ticket signature"
        try:
            humidity, temperature, leak, _, _ = body.split()
        except:
            self.send_response(400)
            self.end_headers()
            return

        if not has_valid_signature(body, device_secret):
            self.send_response(401)
            self.send_header('X-Ticket', last_ticket)
            self.end_headers()
            return

        leak = int(leak)
        humidity = float(humidity)
        if leak > 100 or humidity > 90:
            client.chat_postMessage(channel='#home',
                                    text='Temp:{0} Hum:{1} Leak:{2}'.format(temperature, humidity, leak))
        self.send_response(200)
        self.end_headers()


httpd = HTTPServer(('', 11917), Listener)

# encrypt traffic using tls
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain('cert.pem', 'key.pem')
httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

httpd.serve_forever()

# test_data.py
import socket
import json
import time

HOST = "127.0.0.1"
PORT = 6000

sample_data = {
    "avg_temperature": 24.7,
    "avg_humidity": 61.2,
    "anomalies": [
        {
            "sensor_id": "sensor7",
            "type": "temperature_spike",
            "value": 150.0,
            "timestamp": "2025-05-16T23:05:00Z"
        }
    ],
    "timestamp": "2025-05-16T23:05:00Z"
}

def send_test_packet():
    with socket.create_connection((HOST, PORT)) as sock:
        message = json.dumps(sample_data) + "\n"
        sock.sendall(message.encode("utf-8"))
        print("[INFO] Sample data sent")

if __name__ == "__main__":
    send_test_packet()

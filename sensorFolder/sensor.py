import socket
import json
import time
import argparse
import logging
import random
import sys
import os
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# generates data in order to send to drone
def generate_sensor_data(sensor_id):
    # 5% chance of temperature anomaly
    if random.random() < 0.05:
        temperature = round(random.uniform(150.0, 1000.0), 2)
    else: # normal data
        temperature = round(random.uniform(-100.0, 100.0), 2)

    # 5% chance of humidity anomaly
    if random.random() < 0.05:
        humidity = round(random.uniform(-150.0, -1000.0), 2)
    else: # normal data
        humidity = round(random.uniform(0.0, 100.0), 2)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "sensor_id": sensor_id,
        "temperature": temperature,
        "humidity": humidity,
        "timestamp": timestamp
    }

# establishes connection between the sensor node and the drone
def connect_to_drone(ip, port, retry_interval):
    while True:
        try:
            sock = socket.create_connection((ip, port))
            logging.info(f"Connected to Drone at {ip}:{port}")
            return sock
        except (ConnectionRefusedError, socket.error) as e:
            logging.warning(f"Connection failed: {e}. Retrying in {retry_interval} seconds...")
            time.sleep(retry_interval)

def main():
    parser = argparse.ArgumentParser(description="Sensor Node Client")
    parser.add_argument("--drone_ip", type=str, required=True, help="Drone server IP address")                       # required IP adress of drone
    parser.add_argument("--drone_port", type=int, required=True, help="Drone server port")                           # required port of drone
    parser.add_argument("--interval", type=int, default=2, help="Interval between sensor data sends (seconds)")      # default is 2 secs
    parser.add_argument("--sensor_id", type=str, default="sensor1", help="Unique Sensor ID")                         # default is sensor1
    parser.add_argument("--reconnect_interval", type=int, default=5, help="Reconnect interval on failure (seconds)") # default is 5 secs
    parser.add_argument("--simulate_crash_after", type=int, default=None, help="(Optional) Seconds before simulating crash")
    parser.add_argument("--restart_delay", type=int, default=None, help="(Optional) Seconds to wait before restart")
    
    args = parser.parse_args()
    start_time = time.time()
    sock = connect_to_drone(args.drone_ip, args.drone_port, args.reconnect_interval)

    
    while True:
        try: # connection is established
            # simulate crash if parameters are set
            if args.simulate_crash_after is not None and (time.time() - start_time) > args.simulate_crash_after:
                logging.warning("A crash occurring now. Shutting down sensor...")
                try:
                    sock.close()
                except Exception:
                    pass
                if args.restart_delay is not None:
                    time.sleep(args.restart_delay)
                    logging.info("Restarting sensor after crash.")
                    os.execv(sys.executable, ['python'] + sys.argv)
                else:
                    logging.warning("Restart delay after crash is not specified. Exiting.")
                    sys.exit(0)
                
            data = generate_sensor_data(args.sensor_id)
            message = json.dumps(data)
            sock.sendall((message + '\n').encode('utf-8'))
            logging.info(f"Sent data: {message}")
            time.sleep(args.interval)
        except (BrokenPipeError, ConnectionResetError, socket.error): # connection could not be established
            logging.warning("Lost connection to Drone. Attempting to reconnect...")
            try:
                sock.close()
            except Exception:
                pass
            sock = connect_to_drone(args.drone_ip, args.drone_port, args.reconnect_interval)
                
if __name__ == "__main__":
    main()
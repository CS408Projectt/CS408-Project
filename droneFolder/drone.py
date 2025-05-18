import socket
import threading
import tkinter as tk
from tkinter import scrolledtext
from tkinter import ttk
import json
from datetime import datetime
import re
from collections import deque
import statistics
import time

HOST = "0.0.0.0"
PORT = 5647
FORWARD_HOST = "0.0.0.0"
FORWARD_PORT = 6000

N = 5
T = 1
agg_queue = deque()
forward_queue = deque()
remainingBattery = 100
status = "active"
battery_threshold = 20

# Global persistent socket
forward_socket = None

# GUI Setup
root = tk.Tk()
root.title("Drone")

top_frame = tk.Frame(root)
top_frame.pack(side="top", fill="x")

slider_label = tk.Label(top_frame, text="Battery Threshold:")
slider_label.pack(side="left", padx=(10, 2), pady=5)

# Container for slider and labels beneath it
slider_container = tk.Frame(top_frame)
slider_container.pack(side="left", padx=(0, 10))

threshold_var = tk.IntVar(value=battery_threshold)
threshold_slider = ttk.Scale(slider_container, from_=10, to=50, orient="horizontal", length=200,
                             command=lambda val: threshold_var.set(round(float(val))))
threshold_slider.pack()

# Value labels beneath the slider
slider_label_frame = tk.Frame(slider_container)
slider_label_frame.pack(fill="x")

for i, val in enumerate(range(10, 51, 10)):
    label = tk.Label(slider_label_frame, text=str(val), anchor="center")
    label.grid(row=0, column=i, sticky="nsew")
    slider_label_frame.grid_columnconfigure(i, weight=1)

battery_label_var = tk.StringVar()
status_label_var = tk.StringVar()
battery_label = tk.Label(top_frame, textvariable=battery_label_var)
status_label = tk.Label(top_frame, textvariable=status_label_var)
battery_label.pack(side="right", padx=10)
status_label.pack(side="right", padx=10)

frame1 = tk.LabelFrame(root, text="Real-Time Data View")
frame1.pack(fill="both", expand=True, padx=10, pady=5)

frame2 = tk.LabelFrame(root, text="Logging Panel")
frame2.pack(fill="both", expand=True, padx=10, pady=5)

frame3 = tk.LabelFrame(root, text="Aggregated Results and Anomalies")
frame3.pack(fill="both", expand=True, padx=10, pady=5)

real_time_text = scrolledtext.ScrolledText(frame1, height=15)
real_time_text.pack(fill="both", expand=True)

log_text = scrolledtext.ScrolledText(frame2, height=10)
log_text.pack(fill="both", expand=True)

agg_text = scrolledtext.ScrolledText(frame3, height=8)
agg_text.pack(fill="both", expand=True)

def log_to_real_time(msg):
    real_time_text.insert(tk.END, msg + "\n")
    real_time_text.see(tk.END)

def log_to_log_panel(msg):
    log_text.insert(tk.END, msg + "\n")
    log_text.see(tk.END)

def log_to_agg_panel(msg):
    agg_text.insert(tk.END, msg + "\n")
    agg_text.see(tk.END)

def update_labels():
    battery_label_var.set(f"Battery Level: {remainingBattery}%")
    display_status = {
        "active": "Active",
        "returningToBase": "Returning to Base",
        "charging": "Charging"
    }
    status_label_var.set(f"Status: {display_status.get(status, status)}")
    root.after(500, update_labels)

def is_valid_time(s):
    try:
        datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
        return True
    except ValueError:
        return False

def is_valid_humidity(n): return 0 <= n <= 100
def is_valid_temperature(n): return -100 <= n <= 100
def is_valid_sensor_id(s): return bool(re.fullmatch(r"sensor\d+", s))

def processData(message):
    return (
        isinstance(message.get("sensor_id"), str) and is_valid_sensor_id(message["sensor_id"]) and
        isinstance(message.get("temperature"), (int, float)) and is_valid_temperature(message["temperature"]) and
        isinstance(message.get("humidity"), (int, float)) and is_valid_humidity(message["humidity"]) and
        isinstance(message.get("timestamp"), str) and is_valid_time(message["timestamp"])
    )

def setup_forward_socket():
    global forward_socket
    while True:
        try:
            forward_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            forward_socket.connect((FORWARD_HOST, FORWARD_PORT))
            log_to_log_panel("Connected to forwarding server at 0.0.0.0:6000.")
            break
        except Exception as e:
            log_to_log_panel(f"Retrying connection to forwarding server... ({e})")
            time.sleep(2)

def forward_data_to_host(data_dict):
    global forward_socket
    try:
        forward_socket.sendall((json.dumps(data_dict) + "\n").encode())
    except Exception as e:
        log_to_log_panel(f"Failed to send data: {e}")

def process_one_message(message, sensor_id):
    global status
    anomalyOccurred = not processData(message)
    message["anomaly"] = anomalyOccurred
    try:
        ts = datetime.strptime(message["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
        formatted = f"{message['sensor_id']} reporting: {message['temperature']}°C, {message['humidity']}%, {ts.time()}, {ts.date()}"
        if anomalyOccurred:
            log_to_real_time(formatted + ", Anomaly detected")
            log_to_log_panel("Anomaly occurred")
            time_str = ts.time()
            if not is_valid_temperature(message["temperature"]):
                log_to_agg_panel(f"Anomaly occurred. The sensor with ID {sensor_id} reported an out of range temperature value at {time_str}.")
            if not is_valid_humidity(message["humidity"]):
                log_to_agg_panel(f"Anomaly occurred. The sensor with ID {sensor_id} reported an out of range humidity value at {time_str}.")
        else:
            log_to_real_time(formatted)
            agg_queue.append(message)
            if len(agg_queue) >= N:
                samples = [agg_queue.popleft() for _ in range(N)]
                mean_temp = statistics.mean([d["temperature"] for d in samples])
                mean_hum = statistics.mean([d["humidity"] for d in samples])
                agg_message = f"At the last {N} readings: Average humidity is {mean_hum:.1f}%, Average temperature is {mean_temp:.1f}°C."
                log_to_agg_panel(agg_message)
                if status == "active":
                    forward_data_to_host({"meanTemperature": mean_temp, "meanHumidity": mean_hum})
                else:
                    forward_queue.append({"meanTemperature": mean_temp, "meanHumidity": mean_hum})
                    
        if status == "active":
            forward_data_to_host(message)
        else:
            forward_queue.append(message)

    except Exception:
        pass

def client_connection(conn, addr):
    sensor_id = None
    with conn:
        try:
            first_data = conn.recv(1024)
            if not first_data:
                return
            message = json.loads(first_data.decode())
            sensor_id = message.get("sensor_id", "unknown")
            log_to_log_panel(f"Sensor with ID {sensor_id} connected.")
            process_one_message(message, sensor_id)
        except Exception:
            return

        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                message = json.loads(data.decode())
                process_one_message(message, sensor_id)
            except Exception:
                break

    if sensor_id:
        log_to_log_panel(f"Sensor with ID {sensor_id} disconnected.")

def batterySimulation():
    global remainingBattery, status, battery_threshold
    while True:
        battery_threshold = threshold_var.get()
        if status == "active":
            if remainingBattery > battery_threshold:
                remainingBattery -= 1
            else:
                status = "returningToBase"
                log_to_log_panel("Battery has fallen below the threshold, returning to base..")
                time.sleep(10)
                status = "charging"
        elif status == "charging":
            if remainingBattery < 100:
                remainingBattery += 1
            else:
                status = "active"
                log_to_log_panel("Battery full. Returning to active mode.")
                while forward_queue:
                    forward_data_to_host(forward_queue.popleft())
        time.sleep(T)

def server_thread():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server is running on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=client_connection, args=(conn, addr), daemon=True).start()

setup_forward_socket()
threading.Thread(target=server_thread, daemon=True).start()
threading.Thread(target=batterySimulation, daemon=True).start()
update_labels()
root.mainloop()

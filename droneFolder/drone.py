
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
N = 5
T = 1
anomaly_queue = deque()

remainingBattery = 100
status = "active"
battery_threshold = 20

root = tk.Tk()
root.title("Sensor Server")

top_frame = tk.Frame(root)
top_frame.pack(side="top", fill="x")

slider_label = tk.Label(top_frame, text="Battery Threshold:")
slider_label.pack(side="left", padx=(10, 2), pady=5)

threshold_var = tk.IntVar(value=battery_threshold)
threshold_slider = ttk.Scale(top_frame, from_=10, to=50, orient="horizontal",
                             command=lambda val: threshold_var.set(round(float(val))))
threshold_slider.pack(side="left", padx=(0, 10))

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

def process_one_message(message, sensor_id):
    anomalyOccurred = not processData(message)
    try:
        ts = datetime.strptime(message["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
        formatted = f"{message['sensor_id']} reporting: {message['temperature']}°C, {message['humidity']}%, {ts.time()}, {ts.date()}"
        if anomalyOccurred:
            log_to_real_time(formatted + ", Anomaly detected")
            log_to_log_panel("Anomaly occurred")
            try:
                time_str = ts.time()
                if not is_valid_temperature(message["temperature"]):
                    log_to_agg_panel(f"Anomaly occurred. The sensor with ID {sensor_id} reported an out of range temperature value at {time_str}.")
                if not is_valid_humidity(message["humidity"]):
                    log_to_agg_panel(f"Anomaly occurred. The sensor with ID {sensor_id} reported an out of range humidity value at {time_str}.")
            except Exception:
                pass
        else:
            log_to_real_time(formatted)
            anomaly_queue.append(message)
            if len(anomaly_queue) >= N:
                samples = [anomaly_queue.popleft() for _ in range(N)]
                mean_temp = statistics.mean([d["temperature"] for d in samples])
                mean_hum = statistics.mean([d["humidity"] for d in samples])
                agg_message = f"At the last {N} readings: Average humidity is {mean_hum:.1f}%, Average temperature is {mean_temp:.1f}°C."
                log_to_agg_panel(agg_message)
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
        time.sleep(T)

def server_thread():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server is running on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=client_connection, args=(conn, addr), daemon=True).start()

threading.Thread(target=server_thread, daemon=True).start()
threading.Thread(target=batterySimulation, daemon=True).start()
update_labels()
root.mainloop()

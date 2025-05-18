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

# Below are code for the GUI Setup
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

# Helper functions for processData
def is_valid_time(s):
    try:
        datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
        return True
    except ValueError:
        return False


def is_valid_humidity(n): return 0 <= n <= 100
def is_valid_temperature(n): return -100 <= n <= 100
def is_valid_sensor_id(s): return bool(re.fullmatch(r"sensor\d+", s))

# This function returns true if there are no anomalies in the sensor data, and false otherwise.
def processData(message):
    return (
        isinstance(message.get("sensor_id"), str) and is_valid_sensor_id(message["sensor_id"]) and
        isinstance(message.get("temperature"), (int, float)) and is_valid_temperature(message["temperature"]) and
        isinstance(message.get("humidity"), (int, float)) and is_valid_humidity(message["humidity"]) and
        isinstance(message.get("timestamp"), str) and is_valid_time(message["timestamp"])
    )

# This function creates a socket for communication between the drone and the central server
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

# This function sends the input data to the central server
def forward_data_to_host(data_dict):
    global forward_socket
    try:
        forward_socket.sendall((json.dumps(data_dict) + "\n").encode())
    except Exception as e:
        log_to_log_panel(f"Failed to send data: {e}")

# This function completes processing the data received from the sensor nodes
def process_one_message(message, sensor_id):
    global status
    anomalyOccurred = not processData(message) 
    message["anomaly"] = anomalyOccurred    # Add an additional field to the data received from a sensor node, indicating whether there is an anomaly in the data
    try:
        ts = datetime.strptime(message["timestamp"], "%Y-%m-%dT%H:%M:%SZ")  # Convert the string formatted timestamp to a datetime object
        formatted = f"{message['sensor_id']} reporting: {message['temperature']}°C, {message['humidity']}%, {ts.time()}, {ts.date()}"   # Format the data in a readable way
        if anomalyOccurred: # If an anomaly is present in the data, log it to the real time and log panels, then specify the type of anomaly in the aggregate panel
            log_to_real_time(formatted + ", Anomaly detected")
            log_to_log_panel("Anomaly occurred")
            time_str = ts.time()
            if not is_valid_temperature(message["temperature"]):
                log_to_agg_panel(f"Anomaly occurred. The sensor with ID {sensor_id} reported an out of range temperature value at {time_str}.")
            if not is_valid_humidity(message["humidity"]):
                log_to_agg_panel(f"Anomaly occurred. The sensor with ID {sensor_id} reported an out of range humidity value at {time_str}.")
        else:   # If no anomaly is present;
            log_to_real_time(formatted) # Log it to the real time panel
            agg_queue.append(message)   # Add the data to the queue for mean temperature and humidity calculations
            if len(agg_queue) >= N:     # If the queue reached N elements;
                samples = [agg_queue.popleft() for _ in range(N)]   # Pop N elements
                mean_temp = statistics.mean([d["temperature"] for d in samples])    # Calculate mean temperature
                mean_hum = statistics.mean([d["humidity"] for d in samples])    # Calculate mean humidity
                agg_message = f"At the last {N} readings: Average humidity is {mean_hum:.1f}%, Average temperature is {mean_temp:.1f}°C."
                log_to_agg_panel(agg_message)   # Log the mean values to the aggregate panel
                forward_data_to_host({"meanTemperature": mean_temp, "meanHumidity": mean_hum})  # Forward this information to the central server

        if status == "active":  # If the status is active, forward the data to the central server
            forward_data_to_host(message)
        else:   # Otherwise, enqueue it to forward_queue. Once the status is set back to active, the data in the queue will be immediately sent to the central server.
            forward_queue.append(message)

    except Exception:
        pass

# This function handles the connection between a sensor node and the drone
def client_connection(conn, addr):
    sensor_id = None
    with conn:
        try:    # The "Sensor with ID {sensor_id} connected." message is logged once the sensor node sends its first data. So we handle the first data and the rest separately
            first_data = conn.recv(1024)    # Wait for the sensor node to send data
            if not first_data:
                return
            message = json.loads(first_data.decode())   # Parse the data
            sensor_id = message.get("sensor_id", "unknown")    
            log_to_log_panel(f"Sensor with ID {sensor_id} connected.") 
            process_one_message(message, sensor_id) 
        except Exception:
            return

        while True: # Once the first data part is handled, keep on listening for data from the sensor node in an infinite loop
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
        battery_threshold = threshold_var.get() ## Fetch the threshold value set by the user
        if status == "active":  ## While the status active, decrease the battery level by 1%
            if remainingBattery > battery_threshold:
                remainingBattery -= 1
            else:   ## Once the threshold is reached
                status = "returningToBase"  ## Set the status to Returning To Base
                log_to_log_panel("Battery has fallen below the threshold, returning to base..")
                time.sleep(10)  ## Simulate the time it takes for the drone to return to the base
                status = "charging"     ## Once this time is over, set the status to Charging
        elif status == "charging":  ## While the status is charging;
            if remainingBattery < 100:  ## Increase the battery by 1% until it reaches 100%
                remainingBattery += 1
            else:   ## Once battery is restored;
                status = "active"   # Set the status to Active
                log_to_log_panel("Battery full. Returning to active mode.") # Log the necessary message
                while forward_queue:    # Forward the data that was collected while the drone was not active
                    forward_data_to_host(forward_queue.popleft())
        time.sleep(T)

def server_thread():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))  
        s.listen()  # Listen for connections
        print(f"Server is running on {HOST}:{PORT}")
        while True: # Accept client connections (sensor nodes) and start a client_connection thread for each sensor node
            conn, addr = s.accept() 
            threading.Thread(target=client_connection, args=(conn, addr), daemon=True).start()

setup_forward_socket()
threading.Thread(target=server_thread, daemon=True).start()
threading.Thread(target=batterySimulation, daemon=True).start()
update_labels()
root.mainloop()

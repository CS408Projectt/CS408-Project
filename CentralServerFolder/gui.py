import tkinter as tk
from tkinter import scrolledtext
import queue

def start_gui(data_queue, log_queue):
    root = tk.Tk()
    root.title("Central Server – Environmental Monitor")

    # --- Aggregated Data Panel ---
    # Displays the most recent average temperature, humidity, and timestamp
    latest_frame = tk.LabelFrame(root, text="Latest Aggregated Data")
    latest_frame.pack(fill="x", padx=10, pady=5)

    temp_var = tk.StringVar(value="-- °C")
    hum_var = tk.StringVar(value="-- %")
    ts_var = tk.StringVar(value="Last Update: --")

    # Labels for displaying the latest average temperature and humidity
    tk.Label(latest_frame, text="Avg Temperature:").grid(row=0, column=0, sticky="e", padx=5)
    tk.Label(latest_frame, textvariable=temp_var).grid(row=0, column=1, sticky="w")

    tk.Label(latest_frame, text="Avg Humidity:").grid(row=0, column=2, sticky="e", padx=5)
    tk.Label(latest_frame, textvariable=hum_var).grid(row=0, column=3, sticky="w")

    tk.Label(latest_frame, textvariable=ts_var).grid(row=1, column=0, columnspan=4, pady=3)

    # --- Anomalies Panel ---
    # Shows sensor readings flagged as anomalies by the drone
    anomaly_frame = tk.LabelFrame(root, text="Anomalies Detected")
    anomaly_frame.pack(fill="both", expand=True, padx=10, pady=5)

    anomaly_box = scrolledtext.ScrolledText(anomaly_frame, height=8)
    anomaly_box.pack(fill="both", expand=True)

    # --- Logs Panel ---
    # Provides a scrollable list of logs including system messages, events, and data entries
    log_frame = tk.LabelFrame(root, text="Logs")
    log_frame.pack(fill="both", expand=True, padx=10, pady=5)

    log_box = scrolledtext.ScrolledText(log_frame, height=10)
    log_box.pack(fill="both", expand=True)

    # --- GUI Update Function ---
    # Periodically pulls new items from data_queue and log_queue
    def update_gui():
        while not data_queue.empty():
            data = data_queue.get()

            # Handle average data
            if "meanTemperature" in data and "meanHumidity" in data:
                temp_var.set(f"{data['meanTemperature']} °C")
                hum_var.set(f"{data['meanHumidity']} %")
                ts_var.set("Last Update: Aggregated Reading")
                log_box.insert(tk.END, f"[INFO] Received aggregated data: Temp = {data['meanTemperature']}°C, Hum = {data['meanHumidity']}%\n")
                log_box.see(tk.END)

            # Handle anomaly or normal message
            elif "anomaly" in data:
                
                if data["anomaly"]: # if flagged as anomaly
                    anomaly_log = (
                        f"[{data.get('timestamp', '--')}] Anomaly from {data.get('sensor_id', 'unknown')} – "
                        f"Temp: {data.get('temperature', '--')}°C, Hum: {data.get('humidity', '--')}%"
                    )
                    anomaly_box.insert(tk.END, anomaly_log + "\n")
                    anomaly_box.see(tk.END)
                    log_box.insert(tk.END, f"[ANOMALY] {anomaly_log}\n")
                    log_box.see(tk.END)
               
                else:  # if normal data
                    log_box.insert(tk.END, f"[INFO] Normal reading received: {data}\n")
                    log_box.see(tk.END)

           
            # Fallback for unknown formats
            else:
                log_box.insert(tk.END, f"[WARNING] Unrecognized data format: {data}\n")
                log_box.see(tk.END)
        
        # --- Handle system logs pushed via log_queue ---
        while not log_queue.empty():
            log_box.insert(tk.END, log_queue.get() + "\n")
            log_box.see(tk.END)


        # Schedule next GUI update
        root.after(1000, update_gui)

    root.after(1000, update_gui)
    root.mainloop()

import socket
import threading
import json
import queue
from gui import start_gui

host = "0.0.0.0"
port = 6000  

data_queue = queue.Queue()
log_queue = queue.Queue()

# function to handle incoming client connection from drone
def handle_client_connection(conn, addr):
    log_queue.put(f"[connected] drone connected from {addr}")
    buffer = ""
    with conn:
        while True:
            try:
                chunk = conn.recv(1024)  # receive data from drone
                if not chunk:
                    break  # connection closed
                buffer += chunk.decode()
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    try:
                        data = json.loads(line)  # parse JSON data
                        data_queue.put(data)  # pass to GUI
                        log_queue.put(f"[data received] {data}")
                    except json.JSONDecodeError:
                        log_queue.put("[error] failed to decode JSON")
            except Exception as e:
                log_queue.put(f"[error] connection issue: {e}")
                break
    log_queue.put(f"[disconnected] drone disconnected from {addr}")

# function to start the TCP server
def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))  # bind to specified host and port
    server.listen(1)  # allow 1 connection (can be extended)
    print(f"central server listening on {host}:{port}")
    conn, addr = server.accept()  # wait for a connection
    threading.Thread(target=handle_client_connection, args=(conn, addr), daemon=True).start()

# main program entry point
if __name__ == "__main__":
    threading.Thread(target=start_server, daemon=True).start()
    start_gui(data_queue, log_queue)  # launch GUI

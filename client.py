import socket
import threading
import time
import csv
from protocol import create_packet, parse_packet, MSG_INIT, MSG_EVENT, MSG_SNAPSHOT, MSG_ACK, MAX_PACKET_SIZE

# ----------------------------
# Client Setup
# ----------------------------
SERVER_IP = "127.0.0.1"
SERVER_PORT = 5005
ADDR = (SERVER_IP, SERVER_PORT)

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.settimeout(0.5)  # non-blocking receive

player_id = None
seq_num = 0
last_snapshot_id = -1
snapshots_history = []  # store last K snapshots

# ----------------------------
# Logging Setup
# ----------------------------
csv_file = open("client_log.csv", "w", newline="")
csv_writer = csv.writer(csv_file)
csv_writer.writerow(["snapshot_id", "seq_num", "server_timestamp_ms", "recv_time_ms", "latency_ms"])

# ----------------------------
# Send INIT to Server
# ----------------------------
def send_init():
    global seq_num
    packet = create_packet(MSG_INIT, seq_num, 0, b"INIT_REQUEST")
    client.sendto(packet, ADDR)
    seq_num += 1
    print(f"[CLIENT] Sent INIT")

# ----------------------------
# Networking Receive Loop
# ----------------------------
def receive_loop(callback=None):
    """
    callback: function(payload_bytes) called when a new snapshot arrives
    """
    global player_id, last_snapshot_id, snapshots_history
    while True:
        try:
            data, addr = client.recvfrom(MAX_PACKET_SIZE)
            recv_time = int(time.time() * 1000)
            parsed = parse_packet(data)

            msg_type = parsed["msg_type"]
            snapshot_id = parsed["snapshot_id"]
            payload = parsed["payload"]

            if msg_type == MSG_ACK and player_id is None:
                # INIT_ACK received
                player_id = 1  # For simplicity; server assigns ID
                print(f"[CLIENT] Received INIT ACK, assigned player_id = {player_id}")

            elif msg_type == MSG_SNAPSHOT:
                if snapshot_id > last_snapshot_id:
                    last_snapshot_id = snapshot_id
                    snapshots_history.append(payload)
                    if len(snapshots_history) > 3:
                        snapshots_history = snapshots_history[-3:]

                    # Logging
                    latency = recv_time - parsed["timestamp"]
                    csv_writer.writerow([snapshot_id, parsed["seq_num"], parsed["timestamp"], recv_time, latency])
                    csv_file.flush()

                    # Call GUI callback
                    if callback:
                        callback(payload)
        except socket.timeout:
            continue
        except KeyboardInterrupt:
            break

# ----------------------------
# Send Event
# ----------------------------
def send_event(x, y):
    global seq_num
    payload = f"{x},{y}".encode()
    packet = create_packet(MSG_EVENT, seq_num, last_snapshot_id, payload)
    client.sendto(packet, ADDR)
    seq_num += 1
    print(f"[CLIENT] Sent EVENT ({x},{y})")

# ----------------------------
# Cleanup
# ----------------------------
def close_client():
    client.close()
    csv_file.close()
    print("[CLIENT] Connection closed")

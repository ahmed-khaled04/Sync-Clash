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
player_positions = {}  # player_id -> (x, y)

PLAYER_COLORS = {
    1: (0, 100, 255),
    2: (255, 100, 0),
    3: (0, 255, 100),
    4: (255, 255, 0),
}

# ----------------------------
# Logging Setup
# ----------------------------
csv_file = open("client_log.csv", "w", newline="")
csv_writer = csv.writer(csv_file)
csv_writer.writerow(["snapshot_id", "seq_num", "server_timestamp_ms", "recv_time_ms", "latency_ms"])

# ----------------------------
# Pending Events (for retry)
# ----------------------------
pending_events = {}  # seq_num -> (x, y, timestamp)
RETRY_INTERVAL = 0.1  # seconds

# ----------------------------
# Send INIT
# ----------------------------
def send_init():
    global seq_num
    packet = create_packet(MSG_INIT, seq_num, 0, b"INIT_REQUEST")
    client.sendto(packet, ADDR)
    seq_num += 1
    print(f"[CLIENT] Sent INIT")

# ----------------------------
# Send Event
# ----------------------------
def send_event(x, y):
    global seq_num
    payload = f"{x},{y}".encode()
    packet = create_packet(MSG_EVENT, seq_num, last_snapshot_id, payload)
    client.sendto(packet, ADDR)

    # Save event for retry
    pending_events[seq_num] = (x, y, time.time())
    print(f"[CLIENT] Sent EVENT ({x},{y}) seq {seq_num}")
    seq_num += 1

# ----------------------------
# Retry Thread
# ----------------------------
def retry_events_loop():
    while True:
        now = time.time()
        for seq, (x, y, ts) in list(pending_events.items()):
            if now - ts > RETRY_INTERVAL:
                # Resend event
                payload = f"{x},{y}".encode()
                packet = create_packet(MSG_EVENT, seq, last_snapshot_id, payload)
                client.sendto(packet, ADDR)
                pending_events[seq] = (x, y, now)
                print(f"[CLIENT] Retrying EVENT ({x},{y}) seq {seq}")
        time.sleep(0.05)  # 50ms check interval

# Start retry thread once
threading.Thread(target=retry_events_loop, daemon=True).start()

# ----------------------------
# Receive Loop
# ----------------------------
def receive_loop(callback=None):
    global player_id, last_snapshot_id, snapshots_history

    while True:
        try:
            data, addr = client.recvfrom(MAX_PACKET_SIZE)
            recv_time = int(time.time() * 1000)
            parsed = parse_packet(data)

            msg_type = parsed["msg_type"]
            snapshot_id = parsed["snapshot_id"]
            payload = parsed["payload"]

            if msg_type == MSG_ACK:
                ack_seq = parsed["seq_num"]
                # Remove ACKed event
                if ack_seq in pending_events:
                    del pending_events[ack_seq]
                    print(f"[CLIENT] Received ACK for seq={ack_seq}")

                # INIT_ACK handling
                if player_id is None:
                    try:
                        player_id = int(payload.decode())  # Server sends "1", "2", ...
                    except:
                        player_id = 1  # fallback
                    print(f"[CLIENT] Received INIT ACK, assigned player_id={player_id}")

            elif msg_type == MSG_SNAPSHOT:
                # Ignore old snapshots
                if snapshot_id <= last_snapshot_id:
                    continue

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
# Cleanup
# ----------------------------
def close_client():
    client.close()
    csv_file.close()
    print("[CLIENT] Connection closed")

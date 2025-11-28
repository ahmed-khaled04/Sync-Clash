import socket
import threading
import time
import csv
from protocol import create_packet, parse_packet, MSG_INIT, MSG_DATA, MSG_SNAPSHOT, MSG_EVENT, MSG_ACK, MAX_PACKET_SIZE

# ----------------------------
# Server Setup
# ----------------------------
SERVER_IP = "127.0.0.1"
SERVER_PORT = 5005
ADDR = (SERVER_IP, SERVER_PORT)

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(ADDR)
server.settimeout(0.5)  # non-blocking receive
print(f"[SERVER] Listening on {ADDR}")

# ----------------------------
# Player Storage
# ----------------------------
players = {}           # player_id -> {'addr':(ip,port), 'x':0, 'y':0}
next_player_id = 1
snapshot_id = 0
seq_num = 0

# ----------------------------
# Logging Setup
# ----------------------------
csv_file = open("server_log.csv", "w", newline="")
csv_writer = csv.writer(csv_file)
csv_writer.writerow(["client_id", "snapshot_id", "seq_num", "server_timestamp_ms", "recv_time_ms", "latency_ms"])

# ----------------------------
# Helper Functions
# ----------------------------
def build_snapshot_payload():
    """
    Build snapshot payload: "player_id:x,y;player_id:x,y;..."
    Keeps payload small and readable for GUI.
    """
    payload = b""
    for pid, info in players.items():
        payload += f"{pid}:{info['x']},{info['y']};".encode()
    return payload

def broadcast_snapshots():
    """
    Broadcast snapshot periodically to all players.
    Runs in a separate thread.
    """
    global snapshot_id, seq_num
    while True:
        if players:
            payload = build_snapshot_payload()
            for pid, info in players.items():
                packet = create_packet(MSG_SNAPSHOT, seq_num, snapshot_id, payload)
                try:
                    server.sendto(packet, info['addr'])
                    print(f"[SERVER] Sent SNAPSHOT {snapshot_id} seq {seq_num} to player {pid}")
                except Exception as e:
                    print(f"[SERVER] Error sending to {info['addr']}: {e}")

                # Logging
                recv_time = int(time.time() * 1000)
                latency = 0  # approximate for now
                csv_writer.writerow([pid, snapshot_id, seq_num, int(time.time()*1000), recv_time, latency])
                csv_file.flush()

            seq_num += 1
            snapshot_id += 1

        time.sleep(0.05)  # 20 Hz

def handle_clients():
    """
    Main loop to receive client messages (INIT, DATA, EVENT)
    """
    global next_player_id
    while True:
        try:
            data, addr = server.recvfrom(MAX_PACKET_SIZE)
            recv_time = int(time.time() * 1000)
            parsed = parse_packet(data)
            msg_type = parsed["msg_type"]

            if msg_type == MSG_INIT:
                player_id = next_player_id
                next_player_id += 1
                players[player_id] = {'addr': addr, 'x':0, 'y':0}
                reply = create_packet(MSG_ACK, parsed["seq_num"], parsed["snapshot_id"], b"INIT_ACK")
                server.sendto(reply, addr)
                print(f"[SERVER] Player {player_id} joined from {addr}")

            elif msg_type in [MSG_DATA, MSG_EVENT]:
                payload = parsed["payload"]
                try:
                    x, y = map(int, payload.decode().split(","))
                except:
                    x, y = 0, 0

                pid = next((k for k,v in players.items() if v['addr']==addr), None)
                if pid:
                    players[pid]['x'] = x
                    players[pid]['y'] = y
                    reply = create_packet(MSG_ACK, parsed["seq_num"], parsed["snapshot_id"], b"DATA_ACK")
                    server.sendto(reply, addr)

        except socket.timeout:
            continue
        except KeyboardInterrupt:
            print("\n[SERVER] Shutting down...")
            break

# ----------------------------
# Start Threads
# ----------------------------
threading.Thread(target=broadcast_snapshots, daemon=True).start()
handle_clients()
server.close()
csv_file.close()

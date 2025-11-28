import socket
import threading
import time
import csv
import struct
from protocol import create_packet, parse_packet, MSG_INIT, MSG_DATA, MSG_SNAPSHOT, MSG_EVENT, MSG_ACK, MAX_PACKET_SIZE, REDUNDANT_COUNT

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

snapshots_history = []  # store last REDUNDANT_COUNT binary snapshots

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
    """Combine current player positions into binary payload (3 bytes per player: id, x, y)"""
    payload = b""
    for pid, info in players.items():
        if info['x'] is not None and info['y'] is not None:
            payload += struct.pack("!BBB", pid, info['x'], info['y'])
    return payload

def broadcast_snapshots():
    """
    Periodically broadcast snapshots to all players.
    Includes last REDUNDANT_COUNT snapshots for redundancy.
    """
    global snapshot_id, seq_num, snapshots_history
    while True:
        if players:
            payload = build_snapshot_payload()
            snapshots_history.append(payload)

            if len(snapshots_history) > REDUNDANT_COUNT:
                snapshots_history = snapshots_history[-REDUNDANT_COUNT:]

            # Combine snapshots
            redundant_payload = b"".join(snapshots_history)

            for pid, info in players.items():
                packet = create_packet(MSG_SNAPSHOT, seq_num, snapshot_id, redundant_payload)
                try:
                    server.sendto(packet, info['addr'])
                    print(f"[SERVER] Sent SNAPSHOT {snapshot_id} seq {seq_num} to player {pid}")
                except Exception as e:
                    print(f"[SERVER] Error sending to {info['addr']}: {e}")

                # Logging (latency approx 0 for now)
                recv_time = int(time.time() * 1000)
                csv_writer.writerow([pid, snapshot_id, seq_num, int(time.time()*1000), recv_time, 0])
                csv_file.flush()

            seq_num += 1
            snapshot_id += 1

        time.sleep(0.05)  # 20 Hz

def handle_clients():
    """
    Receive client messages (INIT, DATA, EVENT)
    and handle updates + send ACKs
    """
    global next_player_id
    while True:
        try:
            data, addr = server.recvfrom(MAX_PACKET_SIZE)
            parsed = parse_packet(data)
            msg_type = parsed["msg_type"]

            if msg_type == MSG_INIT:
                player_id = next_player_id
                next_player_id += 1
                players[player_id] = {'addr': addr, 'x':None, 'y':None}
                reply = create_packet(MSG_ACK, parsed["seq_num"], parsed["snapshot_id"], b"INIT_ACK")
                server.sendto(reply, addr)
                print(f"[SERVER] Player {player_id} joined from {addr}")

            elif msg_type in [MSG_DATA, MSG_EVENT]:
                pid = next((k for k,v in players.items() if v['addr']==addr), None)
                if pid:
                    payload = parsed["payload"]
                    try:
                        x, y = map(int, payload.decode().split(","))
                    except:
                        x, y = players[pid]['x'], players[pid]['y']

                    players[pid]['x'] = x
                    players[pid]['y'] = y

                    # Send ACK to client for this event
                    ack_packet = create_packet(MSG_ACK, parsed["seq_num"], parsed["snapshot_id"], b"EVENT_ACK")
                    server.sendto(ack_packet, addr)

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

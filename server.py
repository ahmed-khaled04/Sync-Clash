import socket
import threading
import time
import csv
import struct
from protocol import (
    create_packet,
    parse_packet,
    MSG_INIT,
    MSG_DATA,
    MSG_SNAPSHOT,
    MSG_EVENT,
    MSG_ACK,
    MSG_GAMEOVER,       
    MAX_PACKET_SIZE,
    REDUNDANT_COUNT,
)

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

GRID_SIZE = 20
players = {}           # player_id -> {'addr':(ip,port), 'x':0, 'y':0}
next_player_id = 1
snapshot_id = 0
seq_num = 0

grid_owner = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]

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

def check_and_broadcast_game_over():
    """Check if all cells are acquired; if so, compute winner and broadcast GAME_OVER."""
    # Check if grid is full
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            if grid_owner[row][col] is None:
                return  # still cells left, no game over

    # Count cells per player
    scores = {}
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            owner = grid_owner[row][col]
            if owner is not None:
                scores[owner] = scores.get(owner, 0) + 1

    if not scores:
        return  # safety

    # Determine winner (highest score)
    winner_id = max(scores, key=scores.get)

    # Build simple text payload: WINNER:<id>;SCORES:p1=c1,p2=c2,...
    parts = [f"{pid}={count}" for pid, count in scores.items()]
    payload_text = f"WINNER:{winner_id};SCORES:" + ",".join(parts)
    payload = payload_text.encode()

    global seq_num, snapshot_id
    # Broadcast GAME_OVER to all players
    for pid, info in players.items():
        packet = create_packet(MSG_GAMEOVER, seq_num, snapshot_id, payload)
        try:
            server.sendto(packet, info['addr'])
            print(f"[SERVER] Sent GAME_OVER to player {pid}")
        except Exception as e:
            print(f"[SERVER] Error sending GAME_OVER to {info['addr']}: {e}")

# ----------------------------
# Snapshot broadcast
# ----------------------------
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

# ----------------------------
# Client handling
# ----------------------------
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

                reply = create_packet(
                    MSG_ACK,
                    parsed["seq_num"],
                    parsed["snapshot_id"],
                    f"PLAYER_ID:{player_id}".encode()
                )
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

                    # Prevent clicking taken cells
                    if grid_owner[y][x] is not None and grid_owner[y][x] != pid:
                        err_packet = create_packet(MSG_ACK, parsed["seq_num"], parsed["snapshot_id"], b"CELL_TAKEN")
                        server.sendto(err_packet, addr)
                        continue

                    # Accept move
                    grid_owner[y][x] = pid
                    players[pid]['x'] = x
                    players[pid]['y'] = y

                    # After accepting move, check for GAME_OVER
                    check_and_broadcast_game_over()

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

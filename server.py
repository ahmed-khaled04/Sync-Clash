import threading
import time
import socket
import struct
import csv
import os
import psutil
from threading import Lock



from protocol import (
    HEADER_FORMAT, HEADER_SIZE, MsgType,
    PROTOCOL_ID, VERSION,
    JOIN_ACK_FORMAT, JOIN_ACK_SIZE,
    GRID_SIZE,
    SNAPSHOT_SIZE , 
    REDUNDANT_SNAPHOT_SIZE,
    EventType, EVENT_FORMAT, EVENT_SIZE,
    PLAYER_COLOR_FORMAT, PLAYER_COLOR_ACK_FORMAT, PLAYER_COLOR_ACK_SIZE ,
    GAME_OVER_ACK_FORMAT,GAME_OVER_ACK_SIZE
)


SERVER_CSV = "server_metrics.csv"

if not os.path.exists(SERVER_CSV):
    with open(SERVER_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "cpu_percent" ,  "player_id", "sent_kbps", "recv_kbps"])

event_lock = Lock()
grid_lock = Lock()

PLAYER_COLORS = [
    (255,0,0),    
    (0,255,0),    
    (0,0,255),    
    (255,255,0),  
    (255,0,255),  
    (0,255,255),  
]

player_color_map = {}

COLOR_TIMEOUT_MS = 500  # retransmit after 0.5s if no ACK

# key = (client_addr, player_id)
# value = { "packet": bytes, "last_send": int(ms) }
pending_color = {}

# Bandwidth tracking
bytes_sent_per_player = {}        
bytes_recv_per_player = {}    
last_bw_time = int(time.time())

connected_players_last_seq = {}


pending_game_over = {}
GAME_OVER_TIMEOUT_MS = 500

def assign_color(player_id):
    return PLAYER_COLORS[player_id % len(PLAYER_COLORS)]


def send_player_color_reliable(target_addr, player_id, rgb_tuple):
    """
    Send PLAYER_COLOR to one client and remember it for retransmission
    until we get PLAYER_COLOR_ACK.
    """
    r, g, b = rgb_tuple
    payload = struct.pack(PLAYER_COLOR_FORMAT, player_id, r, g, b)

    now_ms = int(time.time() * 1000)
    header = pack_header(
        MsgType.PLAYER_COLOR,
        0,                 # snapshot_id not used here
        0,                 # seq_num not important for this simple rdt
        now_ms,
        len(payload)
    )

    packet = header + payload
    server.sendto(packet, target_addr)

    pending_color[(target_addr, player_id)] = {
        "packet": packet,
        "last_send": now_ms,
    }


# Server settings
SERVER_IP = "192.168.1.3"
SERVER_PORT = 5005
ADDR = (SERVER_IP, SERVER_PORT)

# Create UDP socket
server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(ADDR)

print(f"[SERVER] Listening on {ADDR}")

#initializing snapshot
snapshot_id = 0
seq_num = 0
last_snapshot_bytes = None

#intialze player_id
next_player_id = 1
addr_to_player = {}

client_last_seen = {}
HEARTBEAT_TIMEOUT = 3 # Seconds

# Game state: 20x20 grid, each byte = cell owner (0 = unclaimed)
grid = [0] * (GRID_SIZE * GRID_SIZE)

connected_players = {}

print(f"[SERVER] Running snapshot broadcaster on {ADDR}")

TICK_RATE = 20          # 20 Hz → every 50 ms
TICK_INTERVAL = 1.0 / TICK_RATE

def pack_header(msg_type, snapshot_id, seq_num, timestamp_ms, payload_len):
    return struct.pack(
        HEADER_FORMAT,
        PROTOCOL_ID,
        VERSION,
        msg_type,
        snapshot_id,
        seq_num,
        timestamp_ms,
        payload_len
    )


def snapshot_sender():
    global snapshot_id , last_snapshot_bytes
    global last_bw_time, bytes_sent_per_player, bytes_recv_per_player

    print("[SERVER] Snapshot thread started ...")

    while True :
        now_ms = int(time.time() * 1000)

        current_payload = bytes(grid)

        if last_snapshot_bytes is None:
            combined_payload = current_payload + current_payload
        else:
            combined_payload = current_payload + last_snapshot_bytes
        last_snapshot_bytes = current_payload



        header = pack_header(
            MsgType.SNAPSHOT,
            snapshot_id,
            snapshot_id,
            now_ms,
            len(combined_payload)
        )

        packet = header + combined_payload

        for pid , player_addr in connected_players.items():
            server.sendto(packet , player_addr)
            bytes_sent_per_player[pid] = bytes_sent_per_player.get(pid, 0) + len(packet)

        snapshot_id += 1

        now_sec = int(time.time())

        if now_sec > last_bw_time:
            cpu = psutil.cpu_percent(interval=None)

            with open(SERVER_CSV, "a" , newline="") as f:
                writer = csv.writer(f)

                for pid in connected_players.keys():
                    sent_bps = bytes_sent_per_player.get(pid , 0) * 8
                    recv_bps = bytes_recv_per_player.get(pid , 0) * 8

                    sent_kbps = sent_bps / 1000
                    recv_kbps = recv_bps / 1000

                    writer.writerow([
                        now_ms,
                        cpu,
                        pid,
                        sent_kbps,
                        recv_kbps
                    ])
        bytes_sent_per_player = {}
        bytes_recv_per_player = {}
        last_bw_time = now_sec
        
        with open("server_positions.csv", "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                snapshot_id,
                now_ms
            ] + list(grid))
            

        time.sleep(TICK_INTERVAL)

def color_retransmit_worker():
    while True:
        now_ms = int(time.time() * 1000)
        # copy keys list to avoid RuntimeError while modifying dict
        for key in list(pending_color.keys()):
            state = pending_color.get(key)
            if not state:
                continue

            if now_ms - state["last_send"] >= COLOR_TIMEOUT_MS:
                # timeout: resend packet
                packet = state["packet"]
                target_addr, _pid = key
                server.sendto(packet, target_addr)
                state["last_send"] = now_ms
        time.sleep(0.05)  # 50ms granularity is enough

# start worker
threading.Thread(target=color_retransmit_worker, daemon=True).start()


def send_game_over():
    print("[SERVER] Computing winner...")

    scores = {}
    for cell in grid:
        if cell != 0:
            scores[cell] = scores.get(cell, 0) + 1

    winner_id = max(scores, key=scores.get)
    num_players = len(scores)

    payload = struct.pack("!HB", winner_id, num_players)
    for pid, score in scores.items():
        payload += struct.pack("!HH", pid, score)

    timestamp_ms = int(time.time() * 1000)
    header = pack_header(
        MsgType.GAME_OVER,
        0,
        0,
        timestamp_ms,
        len(payload)
    )

    packet = header + payload

    # Send once immediately + register for RDT
    for pid, addr in connected_players.items():
        server.sendto(packet, addr)
        pending_game_over[pid] = {
            "packet": packet,
            "addr": addr,
            "last_send": timestamp_ms
        }

    print("[SERVER] GAME_OVER SENT")

def game_over_retransmit_worker():
    while True:
        now_ms = int(time.time() * 1000)

        for pid in list(pending_game_over.keys()):
            entry = pending_game_over.get(pid)
            if not entry:
                continue

            if now_ms - entry["last_send"] >= GAME_OVER_TIMEOUT_MS:
                server.sendto(entry["packet"], entry["addr"])
                entry["last_send"] = now_ms

        time.sleep(0.05)

threading.Thread(target=game_over_retransmit_worker, daemon=True).start()



snapshot_thread = threading.Thread(target=snapshot_sender , daemon=True)
snapshot_thread.start()

def heartbeat_monitor():
    global HEARTBEAT_TIMEOUT , connected_players
    while True:
        now = time.time()
        dead = []

        for addr, last in list(client_last_seen.items()):
            if now - last > HEARTBEAT_TIMEOUT:
                dead.append(addr)

        for d in dead:
            print(f"[SERVER] Client {d} disconnected (heartbeat timeout)")
            del client_last_seen[d]
            connected_players.pop(d , None)

        time.sleep(1)

threading.Thread(target=heartbeat_monitor, daemon=True).start()


def send_event_ack(addr, seq):
    payload = struct.pack("!H", seq)

    header = pack_header(
        MsgType.EVENT_ACK,
        0,
        seq,
        int(time.time() * 1000),
        len(payload)
    )

    server.sendto(header + payload, addr)



while True:
    try:
        # Receive data from client
        data, client_addr = server.recvfrom(1024)

        if client_addr in addr_to_player:
            pid = addr_to_player[client_addr]
            bytes_recv_per_player[pid] = bytes_recv_per_player.get(pid, 0) + len(data)
        
        if len(data) < HEADER_SIZE:
            print(f"[WARN] Short packet from {client_addr}, ignoring")
            continue
        
        prot_id, ver, msg_type_val, recv_snapshot_id, recv_seq_num, ts, payload_len = \
            struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
        
        msg_type = MsgType(msg_type_val)

        if prot_id != PROTOCOL_ID or ver != VERSION:
            print(f"[WARN] Invalid protocol/version from {client_addr}")
            continue


        if msg_type == MsgType.JOIN:
            if client_addr not in addr_to_player:
                player_id = next_player_id
                next_player_id += 1
                addr_to_player[client_addr] = player_id
            else:
                player_id = addr_to_player[client_addr]
            
            print(f"[SERVER] JOIN from {client_addr} -> assigned player_id {player_id}")

            color_r, color_g, color_b = assign_color(player_id)

            player_color_map[player_id] = (color_r, color_g, color_b)


            payload = struct.pack(JOIN_ACK_FORMAT, player_id, GRID_SIZE, TICK_RATE , color_r, color_g, color_b)

            # Build response header
            timestamp_ms = int(time.time() * 1000)
            seq_out = 1  # simple for now — later we'll track it

            header = pack_header(
                MsgType.JOIN_ACK,  
                0,                 
                seq_out,            
                timestamp_ms,
                len(payload)
            )

            server.sendto(header + payload, client_addr)
            print(f"[SERVER] Sent JOIN_ACK to {client_addr}")

            
            # 1) Tell the new player about existing players' colors
            for existing_pid, addr in connected_players.items():
                if existing_pid == player_id:
                    continue

                cr, cg, cb = assign_color(existing_pid)
                send_player_color_reliable(client_addr, existing_pid, (cr, cg, cb))

            # 2) Tell everyone about the new player's color
            for pid, addr in connected_players.items():
                send_player_color_reliable(addr, player_id, (color_r, color_g, color_b))


        elif msg_type == MsgType.READY:
                player_id = addr_to_player.get(client_addr)

                if not player_id:
                    print("[SERVER] READY from unknown client, ignoring", client_addr)
                    continue

                # add to snapshot list
                connected_players[player_id] = client_addr
                print("[SERVER] Player added to snapshot list with id:", player_id)

                #send ALL known player colors to this client
                now_ms = int(time.time() * 1000)
                for pid, (r, g, b) in player_color_map.items():
                    payload = struct.pack(PLAYER_COLOR_FORMAT, pid, r, g, b)
                    header = pack_header(
                        MsgType.PLAYER_COLOR,
                        0,
                        0,
                        now_ms,
                        len(payload),
                    )
                    server.sendto(header + payload, client_addr)

                continue

        
        elif msg_type == MsgType.EVENT:

            payload = data[HEADER_SIZE:]

            if len(payload) < EVENT_SIZE:
                print("[SERVER] Bad EVENT payload length, ignoring")
                continue

            try:
                player_id, seq, event_type, cell_index, event_ts = struct.unpack(EVENT_FORMAT, payload)
            except struct.error:
                print("[SERVER] Failed to unpack EVENT payload, ignoring")
                continue

            mapped_pid = addr_to_player.get(client_addr)
            if mapped_pid is None or mapped_pid != player_id:
                print(f"[WARN] EVENT from {client_addr} with mismatched player_id {player_id} (mapped {mapped_pid}) -> ignoring")
                continue

            with event_lock:
                last_seq = connected_players_last_seq.get(player_id, -1)
                if seq <= last_seq:
                    send_event_ack(client_addr, seq)
                    continue

                connected_players_last_seq[player_id] = seq

                acquired = False
                with grid_lock:
                    if 0 <= cell_index < GRID_SIZE * GRID_SIZE:
                        if grid[cell_index] == 0:
                            grid[cell_index] = player_id
                            acquired = True
                        else:
                            acquired = False
                    else:
                        # invalid cell index
                        print("[SERVER] Invalid cell_index in event:", cell_index)
                        # we'll still ACK to stop client's retransmit
                        send_event_ack(client_addr, seq)
                        continue

            send_event_ack(client_addr, seq)

            if 0 not in grid and not pending_game_over:
                send_game_over()

            # Track bandwidth
            bytes_recv_per_player[player_id] = bytes_recv_per_player.get(player_id, 0) + len(data)

            continue

        elif msg_type == MsgType.HEARTBEAT:
            client_last_seen[client_addr] = time.time()

        elif msg_type == MsgType.PLAYER_COLOR_ACK:
            # payload: player_id (2 bytes)
            if len(data) < HEADER_SIZE + PLAYER_COLOR_ACK_SIZE:
                print("[SERVER] Short PLAYER_COLOR_ACK, ignoring")
                continue

            ack_payload = data[HEADER_SIZE:HEADER_SIZE+PLAYER_COLOR_ACK_SIZE]
            ack_pid, = struct.unpack(PLAYER_COLOR_ACK_FORMAT, ack_payload)

            key = (client_addr, ack_pid)
            if key in pending_color:
                del pending_color[key]
                # rdt3.0 "stop_timer" for this color
                print(f"[SERVER] Got PLAYER_COLOR_ACK for player {ack_pid} from {client_addr}")
            continue
        elif msg_type == MsgType.GAME_OVER_ACK:
            if len(data) < HEADER_SIZE + GAME_OVER_ACK_SIZE:
                continue

            ack_payload = data[HEADER_SIZE:HEADER_SIZE + GAME_OVER_ACK_SIZE]
            ack_pid, = struct.unpack(GAME_OVER_ACK_FORMAT, ack_payload)

            if ack_pid in pending_game_over:
                del pending_game_over[ack_pid]
                print(f"[SERVER] Got GAME_OVER_ACK from player {ack_pid}")
            continue
            

    except ConnectionResetError:
        continue

    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
        break

server.close()
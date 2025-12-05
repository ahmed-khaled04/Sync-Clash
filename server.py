import threading
import time
import socket
import struct
import csv
import os
import psutil


from protocol import (
    HEADER_FORMAT, HEADER_SIZE, MsgType,
    PROTOCOL_ID, VERSION,
    JOIN_ACK_FORMAT, JOIN_ACK_SIZE,
    GRID_SIZE,
    SNAPSHOT_SIZE , 
    REDUNDANT_SNAPHOT_SIZE,
    EventType, EVENT_FORMAT, EVENT_SIZE,
    PLAYER_COLOR_FORMAT
)


SERVER_CSV = "server_metrics.csv"

if not os.path.exists(SERVER_CSV):
    with open(SERVER_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "cpu_percent" ,  "player_id", "sent_kbps", "recv_kbps"])

PLAYER_COLORS = [
    (255,0,0),    
    (0,255,0),    
    (0,0,255),    
    (255,255,0),  
    (255,0,255),  
    (0,255,255),  
]

# Bandwidth tracking
bytes_sent_per_player = {}        
bytes_recv_per_player = {}    
last_bw_time = int(time.time())


def assign_color(player_id):
    return PLAYER_COLORS[player_id % len(PLAYER_COLORS)]


# Server settings
SERVER_IP = "192.168.159.1"
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

def send_game_over():
    print("[SERVER] Computing winner...")

    scores = {}

    for cell in grid:
        if cell != 0:
            scores[cell] = scores.get(cell , 0) + 1

    #Determine Winner
    winner_id = max(scores , key=scores.get)
    num_players = len(scores)

    payload = struct.pack("!HB" , winner_id , num_players)

    for pid , score in scores.items():
        payload += struct.pack("!HH" , pid , score)
    
    timestamp_ms = int(time.time() * 1000)

    header = pack_header(
        MsgType.GAME_OVER,
        0,
        0,
        timestamp_ms,
        len(payload)
    )

    final_packet = header + payload

    for pid, player_addr in connected_players.items():
        server.sendto(final_packet, player_addr)

    print("[SERVER] GAME_OVER SENT ✔")



snapshot_thread = threading.Thread(target=snapshot_sender , daemon=True)
snapshot_thread.start()



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

            
            for existing_pid, addr in connected_players.items():

                if existing_pid == player_id:
                    continue

                cr, cg, cb = assign_color(existing_pid)

                payload_old = struct.pack(PLAYER_COLOR_FORMAT,
                                        existing_pid, cr, cg, cb)

                header_old = pack_header(
                    MsgType.PLAYER_COLOR,
                    0, 0,
                    int(time.time() * 1000),
                    len(payload_old)
                )

                server.sendto(header_old + payload_old, client_addr)

            color_payload = struct.pack(PLAYER_COLOR_FORMAT,
                                        player_id,color_r,color_g,color_b)

            color_header = pack_header(
                MsgType.PLAYER_COLOR,
                0,
                0,
                int(time.time()*1000),
                len(color_payload)
            )

            #Tell Everyone This Color
            for pid,addr in connected_players.items():
                server.sendto(color_header+color_payload , addr)

        elif msg_type == MsgType.READY:
            player_id = addr_to_player.get(client_addr)

            if not player_id:
                print("[SERVER] READY from unknown client ignoring" , client_addr)
                continue
            connected_players[player_id] = client_addr
            print("[SERVER] Player added to snapshot list with id: " , player_id)
            continue
        
        elif msg_type == MsgType.EVENT:

            if len(data) < HEADER_SIZE + EVENT_SIZE:
                print("[SERVER] Invalid Event size")
                continue
            
            payload = data[HEADER_SIZE : HEADER_SIZE + EVENT_SIZE]

            player_id, client_seq, event_type, cell_index , client_ts = \
                struct.unpack(EVENT_FORMAT , payload)
            
            print(f"[SERVER] Event from player {player_id}: type={event_type}, cell={cell_index}")

            row = cell_index // GRID_SIZE
            col = cell_index % GRID_SIZE

            if event_type == EventType.CLICK and grid[row * GRID_SIZE + col] == 0:
                grid[row * GRID_SIZE + col] = player_id

                if 0 not in grid:
                    print("[SERVER] GRID COMPLETE -- GAME OVER")
                    send_game_over()
            



    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
        break

server.close()

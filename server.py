import threading
import time
import socket
import struct


from protocol import (
    HEADER_FORMAT, HEADER_SIZE, MsgType,
    PROTOCOL_ID, VERSION,
    JOIN_ACK_FORMAT, JOIN_ACK_SIZE,
    GRID_SIZE,
    SNAPSHOT_SIZE , 
    EventType, EVENT_FORMAT, EVENT_SIZE
)

PLAYER_COLORS = [
    (255,0,0),    
    (0,255,0),    
    (0,0,255),    
    (255,255,0),  
    (255,0,255),  
    (0,255,255),  
]

def assign_color(player_id):
    return PLAYER_COLORS[player_id % len(PLAYER_COLORS)]


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
    global snapshot_id

    print("[SERVER] Snapshot thread started ...")

    while True :
        now_ms = int(time.time() * 1000)

        payload = bytes(grid)

        header = pack_header(
            MsgType.SNAPSHOT,
            snapshot_id,
            seq_num,
            now_ms,
            SNAPSHOT_SIZE
        )

        packet = header + payload

        for player_addr in connected_players.values():
            server.sendto(packet , player_addr)

        snapshot_id += 1

        time.sleep(TICK_INTERVAL)



snapshot_thread = threading.Thread(target=snapshot_sender , daemon=True)
snapshot_thread.start()



while True:
    try:
        # Receive data from client
        data, client_addr = server.recvfrom(1024)
        
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
            



    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
        break

server.close()

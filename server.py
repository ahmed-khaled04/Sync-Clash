import socket
import time
import struct

from protocol import (
    HEADER_FORMAT, HEADER_SIZE, MsgType,
    PROTOCOL_ID, VERSION,
    JOIN_ACK_FORMAT, JOIN_ACK_SIZE,
    GRID_SIZE
)


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

clients = set()

print(f"[SERVER] Running snapshot broadcaster on {ADDR}")

TICK_RATE = 20          # 20 Hz → every 50 ms
TICK_INTERVAL = 1 / TICK_RATE

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

while True:
    try:
        # Receive data from client
        data, client_addr = server.recvfrom(1024)
        
        if len(data) < HEADER_SIZE:
            print(f"[WARN] Short packet from {client_addr}, ignoring")
            continue

        print("[SERVER] Raw packet length:", len(data))
        print("[SERVER] Raw packet bytes:", data)
        
        prot_id, ver, msg_type_val, snapshot_id, seq_num, ts, payload_len = \
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

            payload = struct.pack(JOIN_ACK_FORMAT, player_id, GRID_SIZE, TICK_RATE)

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

        #snapshot logic
        start = time.time()

        snapshot_id += 1
        seq_num += 1
        timestamp_ms = int(time.time() * 1000)

        # Build header
        payload = bytes(grid)  # full snapshot: 400 bytes
        payload_len = len(payload)

        header = pack_header(
                MsgType.SNAPSHOT,
                snapshot_id,
                seq_num,
                timestamp_ms,
                payload_len
            )

        packet = header + payload

        # Send snapshot to all connected clients
        for c in clients:
            server.sendto(packet, c)

        # Sleep until next tick
        elapsed = time.time() - start
        delay = max(0, TICK_INTERVAL - elapsed)
        time.sleep(delay)

    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
        break

server.close()

import socket
import time
import struct
from protocol import HEADER_FORMAT, HEADER_SIZE, MsgType, PROTOCOL_ID, GRID_SIZE


# Server settings
SERVER_IP = "192.168.187.1"
SERVER_PORT = 5005
ADDR = (SERVER_IP, SERVER_PORT)

# Create UDP socket
server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(ADDR)

print(f"[SERVER] Listening on {ADDR}")

#initializing snapshot
snapshot_id = 0
seq_num = 0

# Game state: 20x20 grid, each byte = cell owner (0 = unclaimed)
grid = [0] * (GRID_SIZE * GRID_SIZE)

clients = set()

print(f"[SERVER] Running snapshot broadcaster on {ADDR}")

TICK_RATE = 20          # 20 Hz → every 50 ms
TICK_INTERVAL = 1 / TICK_RATE

while True:
    try:
        # Receive data from client
        data, client_addr = server.recvfrom(1024)
        msg = data.decode()
        print(f"[SERVER] Received from {client_addr}: {msg}")

        # Prepare reply message
        if msg.startswith("INIT"):
            reply = "ACK: Server ready!"
        elif msg.startswith("DATA"):
            reply = f"ACK: Data received -> {msg}"
        else:
            reply = "ERR: Unknown message type"

        # Send reply
        server.sendto(reply.encode(), client_addr)
        print(f"[SERVER] Sent reply to {client_addr}\n")

        #snapshot logic
        start = time.time()

        snapshot_id += 1
        seq_num += 1
        timestamp_ms = int(time.time() * 1000)

        # Build header
        payload = bytes(grid)  # full snapshot: 400 bytes
        payload_len = len(payload)

        header = struct.pack(
            HEADER_FORMAT,
            PROTOCOL_ID,
            1,  # version
            MsgType.SNAPSHOT,  # msg_type
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

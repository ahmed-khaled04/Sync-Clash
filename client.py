import socket
import time
import struct
from protocol import HEADER_FORMAT, HEADER_SIZE, MsgType, PROTOCOL_ID, VERSION

#Server Settings

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

SERVER_IP = "192.168.1.3"
SERVER_PORT = 5005
ADDR = (SERVER_IP , SERVER_PORT)

#Creating UDP Socket
client = socket.socket(socket.AF_INET , socket.SOCK_DGRAM)
client.settimeout(3)

#Send Join Message
print("[CLIENT] Sending JOIN")

join_header = pack_header(
    MsgType.JOIN,
    0,                
    0,                
    int(time.time() * 1000),
    0                 
)

client.sendto(join_header, ADDR)

try:
    packet, addr = client.recvfrom(1024)
except socket.timeout:
    print("[CLIENT] No JOIN_ACK received (timeout)")
    exit()

# Parse JOIN_ACK
header = packet[:HEADER_SIZE]
(
    protocol_id,
    version,
    msg_type,
    snapshot_id,
    seq_num,
    timestamp_ms,
    payload_len
) = struct.unpack(HEADER_FORMAT, header)

if msg_type != MsgType.JOIN_ACK:
    print("[CLIENT] Expected JOIN_ACK but got something else")
    exit()

payload = packet[HEADER_SIZE:]

player_id, grid_size, tick_rate = struct.unpack("!HBB", payload)

print(f"[CLIENT] JOIN_ACK received:")
print(f"  player_id = {player_id}")
print(f"  grid_size = {grid_size}")
print(f"  tick_rate = {tick_rate}")


#Data + Snapshot
last_snapshot_id = -1

#Send Data Messages
while True:
    try:
        packet, addr = client.recvfrom(1200)
        recv_time_ms = int(time.time() * 1000)

        # ------------------------------
        # Parse header
        # ------------------------------
        if len(packet) < HEADER_SIZE:
            print("[CLIENT] Packet too small, skipping")
            continue

        header = packet[:HEADER_SIZE]
        (
            protocol_id,
            version,
            msg_type,
            snapshot_id,
            seq_num,
            timestamp_ms,
            payload_len
        ) = struct.unpack(HEADER_FORMAT, header)
        # Validate protocol ID
        if protocol_id != PROTOCOL_ID:
            print("[CLIENT] Invalid protocol ID, skipping packet")
            continue

        # -----------------------------------------------------
        # Handle snapshot messages
        # -----------------------------------------------------
        if msg_type != MsgType.SNAPSHOT:
            print(f"[CLIENT] Received non-snapshot message: {msg_type}")
            continue

        # DROP outdated/duplicate snapshots
        if snapshot_id <= last_snapshot_id:
            print(f"[CLIENT] Dropped outdated snapshot {snapshot_id}")
            continue

        last_snapshot_id = snapshot_id

        # -----------------------------------------------------
        # Extract grid snapshot payload
        # -----------------------------------------------------
        payload = packet[HEADER_SIZE:]

        if len(payload) != SNAPSHOT_SIZE:
            print(f"[CLIENT] Invalid snapshot size: {len(payload)} (expected {SNAPSHOT_SIZE})")
            continue

        grid = list(payload)

        latency = recv_time_ms - timestamp_ms

        # -----------------------------------------------------
        # Apply snapshot
        # -----------------------------------------------------
        print(
            f"[CLIENT] Applied snapshot {snapshot_id} | "
            f"seq={seq_num} | server_ts={timestamp_ms} | "
            f"latency={latency} ms"
        )

        # You can plug the grid into the GUI or game renderer here
        # update_grid_display(grid)

    except socket.timeout:
        print("[CLIENT] Waiting for server snapshots...")
    except KeyboardInterrupt:
        print("\n[CLIENT] Shutting down...")
        break
    
#Close Connection
client.close()
print("[CLIENT] Connection Closed")
import struct
import time

# -----------------------------
# Protocol Constants
# -----------------------------

PROTOCOL_ID = b'SYNC'    # 4-byte ASCII identifier for packet validation
VERSION = 1              # 1 byte protocol version

# -----------------------------
# Message Types
# -----------------------------
MSG_INIT     = 1  # Client → Server: Join session
MSG_ACK      = 2  # Server → Client: Acknowledge INIT / EVENT
MSG_DATA     = 3  # Client → Server: Position / EVENT (Phase 1 style)
MSG_SNAPSHOT = 4  # Server → Clients: Periodic snapshot of game state
MSG_EVENT    = 5  # Client → Server: Player action (cell click, etc.)
MSG_ERR      = 6  # Server → Client: Unknown / error

# -----------------------------
# Header and Packet Limits
# -----------------------------
MAX_PACKET_SIZE = 1200  # UDP-safe maximum packet size
REDUNDANT_COUNT = 3     # Number of last snapshots included in each packet for redundancy

# -----------------------------
# Helper Functions
# -----------------------------
def create_packet(msg_type, seq_num, snapshot_id, payload=b""):
    """
    Build a binary packet with header + payload

    Header format: !4sBBIIQI
        4s: protocol_id
        B : version
        B : msg_type
        I : seq_num
        I : snapshot_id
        Q : timestamp (ms)
        I : payload length
    """
    timestamp = int(time.time() * 1000)  # current time in milliseconds
    payload_len = len(payload)
    header = struct.pack(
        "!4sBBIIQI", PROTOCOL_ID, VERSION, msg_type, seq_num, snapshot_id, timestamp, payload_len
    )
    return header + payload

def parse_packet(packet):
    """
    Parse received packet and return header fields + payload

    Returns:
        dict with keys:
            protocol_id, version, msg_type, seq_num, snapshot_id, timestamp, payload_len, payload
    """
    header_size = struct.calcsize("!4sBBIIQI")
    header = packet[:header_size]
    payload = packet[header_size:]
    protocol_id, version, msg_type, seq_num, snapshot_id, timestamp, payload_len = struct.unpack("!4sBBIIQI", header)
    return {
        "protocol_id": protocol_id,
        "version": version,
        "msg_type": msg_type,
        "seq_num": seq_num,
        "snapshot_id": snapshot_id,
        "timestamp": timestamp,
        "payload_len": payload_len,
        "payload": payload
    }

def current_millis():
    """Return current timestamp in milliseconds"""
    return int(time.time() * 1000)

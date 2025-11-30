"""
GridClash Protocol Definitions
Used by both server and client.

This file defines:
- Protocol constants
- Message types
- Header structure (fields + sizes)
- Struct packing formats
"""

import struct
from enum import IntEnum

# ---------------------------------------------------------
# Basic Protocol Info
# ---------------------------------------------------------

PROTOCOL_ID = b"GSC"   # 4 bytes (Grid Sync Clash)
VERSION = 1.0             # 1 byte protocol version

# ---------------------------------------------------------
# Message Types
# ---------------------------------------------------------

class MsgType(IntEnum):
    JOIN = 0          # Client → Server
    JOIN_ACK = 1      # Server → Client
    EVENT = 2         # Client → Server
    SNAPSHOT = 3      # Server → Client
    HEARTBEAT = 4
    ERROR = 5

# ---------------------------------------------------------
# Header Structure
# ---------------------------------------------------------
# Header Fields (24 bytes total):
#   protocol_id     4 bytes
#   version         1 byte
#   msg_type        1 byte
#   snapshot_id     4 bytes
#   seq_num         4 bytes
#   timestamp_ms    8 bytes
#   payload_len     2 bytes

HEADER_FORMAT = "!4s B B I I Q H"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# ---------------------------------------------------------
# EVENT Payload Structure (Client → Server)
# ---------------------------------------------------------

class EventType(IntEnum):
    CLICK = 0    # Click on cell

# Payload layout:
#   player_id         2 bytes
#   client_msg_seq    2 bytes
#   event_type        1 byte
#   cell_index        2 bytes   (0–399 for 20×20)
#   client_timestamp  8 bytes   (ms)

EVENT_FORMAT = "!H H B H Q"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

# ---------------------------------------------------------
# JOIN_ACK Payload Structure (Server → Client)
# ---------------------------------------------------------
#   player_id    2 bytes
#   grid_size    1 byte
#   tick_rate    1 byte

JOIN_ACK_FORMAT = "!H B B"
JOIN_ACK_SIZE = struct.calcsize(JOIN_ACK_FORMAT)

# ---------------------------------------------------------
# SNAPSHOT Payload Structure (Server → Client)
# ---------------------------------------------------------
# Phase 1: Full grid snapshot
# 400 bytes = 20x20 grid, each cell 1 byte
#
# IMPORTANT: SNAPSHOT payload size = grid_size * grid_size

# Define SNAPSHOT grid size here so server/client import same value:
GRID_SIZE = 20
SNAPSHOT_GRID_CELLS = GRID_SIZE * GRID_SIZE

# Full snapshot payload = one byte per cell
SNAPSHOT_SIZE = SNAPSHOT_GRID_CELLS  # 400 bytes


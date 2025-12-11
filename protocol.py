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

PROTOCOL_ID = b"GSCP"   # 4 bytes (Grid Sync Clash)
VERSION = 7             # 1 byte protocol version

# ---------------------------------------------------------
# Message Types
# ---------------------------------------------------------

class MsgType(IntEnum):
    JOIN = 0          # Client → Server
    JOIN_ACK = 1      # Server → Client
    EVENT = 2 
    EVENT_ACK = 3
    SNAPSHOT = 4      # Server → Client
    READY = 5
    GAME_OVER = 6
    GAME_OVER_ACK = 7
    PLAYER_COLOR = 8
    PLAYER_COLOR_ACK = 9 
    HEARTBEAT = 10

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
#   color_r      1 byte
#   color_g      1 byte
#   color_b      1 byte


JOIN_ACK_FORMAT = "!H B B B B B"
JOIN_ACK_SIZE = struct.calcsize(JOIN_ACK_FORMAT)

# ---------------------------------------------------------
# PLAYER_COLOR Payload Structure (Server → Client)
# ---------------------------------------------------------
#   player_id    2 bytes
#   color_r      1 byte
#   color_g      1 byte
#   color_b      1 byte

PLAYER_COLOR_FORMAT = "!HBBB"
PLAYER_COLOR_SIZE = struct.calcsize(PLAYER_COLOR_FORMAT)

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
REDUNDANT_SNAPHOT_SIZE = SNAPSHOT_SIZE * 2

# GAME_OVER message format:
# winner_id (H) + num_players(B) + repeating pairs of (player_id H, score H)
GAME_OVER_HEADER = "!HB"

GAME_OVER_ACK_FORMAT = "!H"   # player_id
GAME_OVER_ACK_SIZE = 2


PLAYER_COLOR_FORMAT = "!HBBB"
PLAYER_COLOR_SIZE = struct.calcsize(PLAYER_COLOR_FORMAT)

# NEW: ACK for player color (just player_id)
PLAYER_COLOR_ACK_FORMAT = "!H"
PLAYER_COLOR_ACK_SIZE = struct.calcsize(PLAYER_COLOR_ACK_FORMAT)


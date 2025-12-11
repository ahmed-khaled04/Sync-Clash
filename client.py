import socket
import time
import struct
import csv
import os
import tkinter as tk
from threading import Thread , Lock
from queue import SimpleQueue

from protocol import (
    HEADER_FORMAT,
    HEADER_SIZE,
    MsgType,
    PROTOCOL_ID,
    VERSION,
    GRID_SIZE,
    SNAPSHOT_SIZE,
    EventType,
    EVENT_FORMAT,
    EVENT_SIZE,
    PLAYER_COLOR_ACK_FORMAT, PLAYER_COLOR_ACK_SIZE,
    PLAYER_COLOR_FORMAT
)

# ==========================
# Queue + frame timing
# ==========================

snapshot_queue = SimpleQueue()
FRAME_TIME_MS = 50      # UI refresh ~20 FPS (match TICK_RATE=20)
MAX_QUEUE = 3           # don't let queue grow too large

# Event Handling
pending_events = {}   
pending_lock = Lock()
MAX_EVENT_RETRIES = 6
EVENT_TIMEOUT_MS = 300

# ==========================
# CSV Metrics
# ==========================

CSV_FILE = "client_metrics.csv"
last_recv_time = None
bytes_received_this_second = 0
last_bandwidth_time = int(time.time())
current_bandwidth_kbps = 0

if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "client_id",
            "snapshot_id",
            "seq_num",
            "server_timestamp",
            "recv_time",
            "latency_ms",
            "jitter_ms",
            "bandwidth_per_client_kbps",
        ])

# ==========================
# Grid / UI settings
# ==========================

CELL_SIZE = 20
player_colors = {}
click_enabled = True


def show_game_over_ui(winner_id, scores):
    msg = f"GAME OVER!\nWinner: Player {winner_id}\n\nScores:\n"

    for pid, score in scores.items():
        msg += f"Player {pid}: {score}\n"

    import tkinter.messagebox as mb
    mb.showinfo("Game Over", msg)

    print(msg)

    global click_enabled
    click_enabled = False


def get_color_for_player(pid):
    if pid == 0:
        return "white"
    if pid in player_colors:
        r, g, b = player_colors[pid]
        return f"#{r:02x}{g:02x}{b:02x}"
    return "#cccccc"


class GridUI:
    def __init__(self, root, rows, cols):
        self.rows = rows
        self.cols = cols

        self.canvas = tk.Canvas(
            root,
            width=cols * CELL_SIZE,
            height=rows * CELL_SIZE,
            bg="white",
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)

        self.click_callback = None
        self.last_snapshot = None

        # Create rectangles for all cells
        self.cells = []
        for r in range(rows):
            row_cells = []
            for c in range(cols):
                rect = self.canvas.create_rectangle(
                    c * CELL_SIZE,
                    r * CELL_SIZE,
                    (c + 1) * CELL_SIZE,
                    (r + 1) * CELL_SIZE,
                    outline="gray",
                    fill="white",
                )
                row_cells.append(rect)
            self.cells.append(row_cells)

    def on_click(self, event):
        if self.click_callback is None:
            return

        col = event.x // CELL_SIZE
        row = event.y // CELL_SIZE

        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.click_callback(row, col)

    def set_click_callback(self, callback):
        self.click_callback = callback

    def update_grid(self, snapshot, force_full_render=False):
        if len(snapshot) != self.rows or any(len(r) != self.cols for r in snapshot):
            print("[UI] malformed snapshot received, ignoring")
            return

        # First time or force → repaint everything
        if self.last_snapshot is None or force_full_render:
            for r in range(self.rows):
                for c in range(self.cols):
                    val = int(snapshot[r][c])
                    color = get_color_for_player(val)
                    self.canvas.itemconfig(self.cells[r][c], fill=color)
            self.last_snapshot = snapshot
            return

        # Incremental updates
        for r in range(self.rows):
            for c in range(self.cols):
                if snapshot[r][c] != self.last_snapshot[r][c]:
                    val = int(snapshot[r][c])
                    color = get_color_for_player(val)
                    self.canvas.itemconfig(self.cells[r][c], fill=color)

        self.last_snapshot = snapshot

        # Optional logging of visible grid
        try:
            flat = [cell for row in snapshot for cell in row]
            now_ms = int(time.time() * 1000)
            with open("client_positions.csv", "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([player_id_global, now_ms] + flat)
        except Exception as e:
            print("[CLIENT] Error logging displayed grid:", e)


class ColorLegend:
    def __init__(self, root):
        self.frame = tk.Frame(root, padx=10, pady=10)
        self.frame.pack(side="right", fill="y")

        title = tk.Label(self.frame, text="Player Colors", font=("Arial", 14, "bold"))
        title.pack()

        self.entries = {}  # pid → (color_box, label)

    def update_legend(self):
        for pid, (r, g, b) in list(player_colors.items()):
            color_hex = f"#{r:02x}{g:02x}{b:02x}"

            if pid not in self.entries:
                row = tk.Frame(self.frame)
                row.pack(anchor="w", pady=2)

                color_box = tk.Canvas(row, width=20, height=20, bg=color_hex)
                color_box.pack(side="left")

                label = tk.Label(row, text=f" Player {pid}")
                label.pack(side="left")

                self.entries[pid] = (color_box, label)
            else:
                color_box, label = self.entries[pid]
                color_box.config(bg=color_hex)


# ==========================
# Networking helpers
# ==========================

def pack_header(msg_type, snapshot_id, seq_num, timestamp_ms, payload_len):
    return struct.pack(
        HEADER_FORMAT,
        PROTOCOL_ID,
        VERSION,
        msg_type,
        snapshot_id,
        seq_num,
        timestamp_ms,
        payload_len,
    )


SERVER_IP = "192.168.1.3"   # change if your server runs on another IP
SERVER_PORT = 5005
ADDR = (SERVER_IP, SERVER_PORT)

player_id_global = None
client_seq_num = 0

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.settimeout(1)


def intialize_client():
    global player_id_global

    print("[CLIENT] Sending JOIN ...")

    join_header = pack_header(
        MsgType.JOIN,
        0,
        0,
        int(time.time() * 1000),
        0,
    )

    client.settimeout(1)

    # -------------------------
    # LOOP UNTIL JOIN_ACK RECEIVED
    # -------------------------
    while True:
        try:
            client.sendto(join_header, ADDR)
            print("[CLIENT] JOIN sent, waiting for JOIN_ACK...")

            packet, addr = client.recvfrom(1024)

            if len(packet) < HEADER_SIZE:
                print("[CLIENT] Short packet received, ignoring")
                continue

            (
                protocol_id,
                version,
                msg_type,
                snapshot_id,
                seq_num,
                timestamp_ms,
                payload_len,
            ) = struct.unpack(HEADER_FORMAT, packet[:HEADER_SIZE])

            # Validate
            if protocol_id != PROTOCOL_ID or version != VERSION:
                print("[CLIENT] Invalid protocol/version, ignoring packet")
                continue

            if msg_type != MsgType.JOIN_ACK:
                print(f"[CLIENT] Unexpected packet while waiting JOIN_ACK: {msg_type}")
                continue

            # ✅ JOIN_ACK RECEIVED
            print("[CLIENT] JOIN_ACK received")
            break

        except socket.timeout:
            print("[CLIENT] JOIN timeout... retrying")

    # -------------------------
    # DECODE JOIN_ACK PAYLOAD
    # -------------------------
    payload = packet[HEADER_SIZE:]

    if len(payload) < 6:
        print("[CLIENT] JOIN_ACK payload too short")
        return

    player_id, grid_size, tick_rate, r, g, b = struct.unpack("!HBBBBB", payload)

    player_colors[player_id] = (r, g, b)

    print("\n[CLIENT] JOIN_ACK DETAILS:")
    print(f"  player_id = {player_id}")
    print(f"  grid_size = {grid_size}")
    print(f"  tick_rate = {tick_rate}")
    print(f"  player_color = {player_colors[player_id]}")

    player_id_global = player_id

    # -------------------------
    # SEND READY (MULTIPLE TIMES FOR RELIABILITY)
    # -------------------------
    ready_header = pack_header(
        MsgType.READY,
        0,
        0,
        int(time.time() * 1000),
        0,
    )

    for i in range(3):
        client.sendto(ready_header, ADDR)
        print(f"[CLIENT] READY sent ({i+1}/3)")
        time.sleep(0.1)

    print("[CLIENT] READY PHASE COMPLETE")

def decode_snapshot(snapshot_bytes):
    grid = []
    index = 0
    for _ in range(GRID_SIZE):
        row = []
        for _ in range(GRID_SIZE):
            row.append(snapshot_bytes[index])
            index += 1
        grid.append(row)
    return grid


# ============================================================
#          Receiver Thread (handles ALL messages)
# ============================================================

def listen_for_messages(ui):
    global bytes_received_this_second
    global last_bandwidth_time, current_bandwidth_kbps
    global last_recv_time

    last_snapshot_id = -1
    last_logged_snapshot = -1
    LOG_EVERY_N = 10

    TICK_RATE = 20
    TICK_INTERVAL = 1.0 / TICK_RATE

    while True:
        try:
            packet, addr = client.recvfrom(1500)
            recv_time_ms = int(time.time() * 1000)

            # -------- bandwidth -------------
            bytes_received_this_second += len(packet)
            now_sec = int(time.time())
            if now_sec > last_bandwidth_time:
                current_bandwidth_kbps = (bytes_received_this_second * 8) / 1000.0
                bytes_received_this_second = 0
                last_bandwidth_time = now_sec

            if len(packet) < HEADER_SIZE:
                continue

            (
                protocol_id,
                version,
                msg_type,
                snapshot_id,
                seq_num,
                timestamp_ms,
                payload_len,
            ) = struct.unpack(HEADER_FORMAT, packet[:HEADER_SIZE])

            if protocol_id != PROTOCOL_ID or version != VERSION:
                continue

            # ------------- GAME_OVER -------------------
            if msg_type == MsgType.GAME_OVER:
                payload = packet[HEADER_SIZE:]
                if len(payload) < 3:
                    print("[CLIENT] Bad GAME_OVER payload")
                    continue

                winner_id, num_players = struct.unpack("!HB", payload[:3])
                offset = 3
                scores = {}

                for _ in range(num_players):
                    if offset + 4 > len(payload):
                        break
                    pid, score = struct.unpack("!HH", payload[offset:offset + 4])
                    scores[pid] = score
                    offset += 4


                # Send Game Over ACK
                ack_payload = struct.pack("!H", player_id_global)

                ack_header = pack_header(
                    MsgType.GAME_OVER_ACK,
                    0,       
                    0,               
                    int(time.time() * 1000),
                    len(ack_payload)
                )

                client.sendto(ack_header + ack_payload, ADDR)
                print(f"[CLIENT] Sent GAME_OVER_ACK for player {player_id_global}")

                ui.canvas.after(0, show_game_over_ui, winner_id, scores)

                continue

            if msg_type == MsgType.EVENT_ACK:
                ack_seq = struct.unpack("!H", packet[HEADER_SIZE:])[0]
                with pending_lock:
                    if ack_seq in pending_events:
                        del pending_events[ack_seq]
                continue

            if msg_type == MsgType.PLAYER_COLOR:
                if payload_len != 5:
                    print("[CLIENT] Bad PLAYER_COLOR payload")
                    continue

                payload = packet[HEADER_SIZE:]
                pid, r, g, b = struct.unpack("!HBBB", payload)
                player_colors[pid] = (r, g, b)

                # update legend on UI thread
                ui.legend.frame.after(0, ui.legend.update_legend)

                print(f"[CLIENT] Player {pid} color updated -> {player_colors[pid]}")

                # ---- send ACK (rdt3.0 style) ----
                ack_payload = struct.pack(PLAYER_COLOR_ACK_FORMAT, pid)
                ack_header = struct.pack(
                    HEADER_FORMAT,
                    PROTOCOL_ID,
                    VERSION,
                    MsgType.PLAYER_COLOR_ACK,
                    0,                 # snapshot_id not used
                    0,                 # seq_num not used for this simple ACK
                    int(time.time() * 1000),
                    len(ack_payload)
                )
                client.sendto(ack_header + ack_payload, ADDR)

            # ------------- SNAPSHOT --------------------
            if msg_type != MsgType.SNAPSHOT:
                # ignore others here
                continue

            if snapshot_id <= last_snapshot_id:
                # drop older snapshots
                continue

            payload = packet[HEADER_SIZE:]
            if len(payload) != SNAPSHOT_SIZE * 2:
                continue

            # we only use the new snapshot for low latency
            new_bytes = payload[:SNAPSHOT_SIZE]
            decoded_new = decode_snapshot(new_bytes)

            # keep queue small – always show latest few frames
            while snapshot_queue.qsize() >= MAX_QUEUE:
                snapshot_queue.get()

            snapshot_queue.put((snapshot_id, timestamp_ms, seq_num, decoded_new, recv_time_ms))
            last_snapshot_id = snapshot_id

            # --------- latency / jitter metrics -------
            raw_latency = recv_time_ms - timestamp_ms
            # clamp negative values due to clock skew between server/client
            latency = max(raw_latency, 0)

            if last_recv_time is None:
                jitter = 0
            else:
                jitter = abs((recv_time_ms - last_recv_time) - TICK_INTERVAL * 1000)
            last_recv_time = recv_time_ms

            # log every N snapshots (to reduce disk I/O)
            if (last_logged_snapshot == -1) or (snapshot_id - last_logged_snapshot >= LOG_EVERY_N):
                try:
                    with open(CSV_FILE, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            player_id_global,
                            snapshot_id,
                            seq_num,
                            timestamp_ms,
                            recv_time_ms,
                            latency,
                            jitter,
                            current_bandwidth_kbps,
                        ])
                except Exception as e:
                    print("[CLIENT] Error writing metrics CSV:", e)

                print(
                    f"[CLIENT] Snapshot {snapshot_id} | "
                    f"seq={seq_num} | server_ts={timestamp_ms} | "
                    f"latency={latency} ms | jitter={jitter:.2f} ms | "
                    f"bw={current_bandwidth_kbps:.1f} kbps"
                )
                last_logged_snapshot = snapshot_id

        except socket.timeout:
            continue
        except KeyboardInterrupt:
            print("\n[CLIENT] Shutting down...")
            break
        except Exception as e:
            print("[CLIENT] Error in listen_for_messages:", e)


# ============================================================
#           UI render loop (pull from queue)
# ============================================================

def ui_render_loop(ui):
    try:
        if not snapshot_queue.empty():
            snapshot_id, ts, seq_num, grid, recv_time_ms = snapshot_queue.get()
            ui.update_grid(grid)

        ui.canvas.after(FRAME_TIME_MS, ui_render_loop, ui)
    except RuntimeError:
        # Tk window closed
        return


def send_click_event(row, col, player_id):
    global click_enabled, client_seq_num

    if not click_enabled:
        print("[CLIENT] Click Disabled. Game Over")
        return

    cell_index = row * GRID_SIZE + col
    now_ms = int(time.time() * 1000)

    payload = struct.pack(
        EVENT_FORMAT,
        player_id,
        client_seq_num,
        EventType.CLICK,
        cell_index,
        now_ms,
    )

    header = pack_header(
        MsgType.EVENT,
        0,
        client_seq_num,
        now_ms,
        len(payload),
    )

    packet = header + payload
    client.sendto(packet, ADDR)
    print(f"[CLIENT] CLICK event sent seq={client_seq_num} (row={row}, col={col}, cell={cell_index})")

    with pending_lock:
        pending_events[client_seq_num] = {
            "packet": packet,
            "last_send": now_ms,
            "tries": 1
        }

    client_seq_num += 1

def event_retransmit_worker():
    while True:
        now = int(time.time() * 1000)
        to_remove = []
        with pending_lock:
            for seq, info in list(pending_events.items()):
                if now - info["last_send"] >= EVENT_TIMEOUT_MS:
                    if info["tries"] >= MAX_EVENT_RETRIES:
                        print(f"[CLIENT] Event seq={seq} reached max retries -> giving up")
                        to_remove.append(seq)
                        continue
                    client.sendto(info["packet"], ADDR)
                    info["last_send"] = now
                    info["tries"] += 1
        with pending_lock:
            for seq in to_remove:
                del pending_events[seq]
        time.sleep(0.05)

def send_heartbeat():
    while True:
        try:
            now_ms = int(time.time() * 1000)
            header = pack_header(
                MsgType.HEARTBEAT,
                0,
                0,
                now_ms,
                0,
            )
            client.sendto(header, ADDR)
            time.sleep(1)
        except Exception as e:
            print("[CLIENT] Heartbeat stopped:", e)
            break


def start_ui():
    root = tk.Tk()
    root.title("Grid")

    main_frame = tk.Frame(root)
    main_frame.pack(fill="both", expand=True)

    left_frame = tk.Frame(main_frame)
    left_frame.pack(side="left")

    right_frame = tk.Frame(main_frame)
    right_frame.pack(side="right", anchor="n", padx=10, pady=10)

    ui = GridUI(left_frame, GRID_SIZE, GRID_SIZE)
    ui.legend = ColorLegend(right_frame)
    ui.legend.update_legend()

    ui.set_click_callback(lambda r, c: send_click_event(r, c, player_id_global))

    Thread(target=event_retransmit_worker, daemon=True).start()

    # listener thread (all network messages)
    Thread(target=listen_for_messages, args=(ui,), daemon=True).start()

    # UI render loop (reads from queue)
    ui.canvas.after(FRAME_TIME_MS, ui_render_loop, ui)

    # heartbeat thread
    Thread(target=send_heartbeat, daemon=True).start()

    root.mainloop()


if __name__ == "__main__":
    intialize_client()
    start_ui()

    client.close()
    print("[CLIENT] Connection Closed")

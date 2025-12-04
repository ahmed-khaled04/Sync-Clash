import socket
import time
import struct
import tkinter as tk
from threading import Thread
from collections import deque

from protocol import (
    HEADER_FORMAT, HEADER_SIZE, MsgType, PROTOCOL_ID, VERSION,
    SNAPSHOT_SIZE, EventType, EVENT_FORMAT, EVENT_SIZE
)

GRID_SIZE = 20  
CELL_SIZE = 20 


player_colors = {}

snapshot_buffer = deque()
BUFFER_DELAY_MS = 50 #Same as snapshot interval

def process_snapshot_buffer(ui):
    now_ms = int(time.time() * 1000)

    if not snapshot_buffer:
        ui.canvas.after(25, process_snapshot_buffer, ui)
        return

    snapshot_id, server_ts, decoded_grid = snapshot_buffer[0]

    
    if now_ms >= server_ts + BUFFER_DELAY_MS:

        snapshot_buffer.popleft()

        ui.update_grid(decoded_grid)

        print(f"[SMOOTH] Applied snapshot {snapshot_id} after smoothing at: {now_ms}")

    ui.canvas.after(25, process_snapshot_buffer, ui)


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
            bg="white"
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)
        self.click_callback = None

        # Create rectangles for all cells
        self.cells = []
        for r in range(rows):
            row_cells = []
            for c in range(cols):
                rect = self.canvas.create_rectangle(
                    c * CELL_SIZE,
                    r * CELL_SIZE,
                    (c+1) * CELL_SIZE,
                    (r+1) * CELL_SIZE,
                    outline="gray",
                    fill="white"
                )
                row_cells.append(rect)
            self.cells.append(row_cells)

    def on_click(self, event):
        if self.click_callback is None:
            return

        # Convert pixel → grid cell index
        col = event.x // CELL_SIZE
        row = event.y // CELL_SIZE

        # Clamp to grid size
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.click_callback(row, col) 

    
    def set_click_callback(self, callback):
        self.click_callback = callback

    def update_grid(self, snapshot):
        if len(snapshot) != self.rows or any(len(r) != self.cols for r in snapshot):
            print("[UI] malformed snapshot received, ignoring")
            return

        for r in range(self.rows):
            for c in range(self.cols):
                val = int(snapshot[r][c]) 

                color = get_color_for_player(val)

                self.canvas.itemconfig(self.cells[r][c], fill=color)

class ColorLegend:
    def __init__(self, root):
        self.frame = tk.Frame(root, padx=10, pady=10)
        self.frame.pack(side="right", fill="y")

        title = tk.Label(self.frame, text="Player Colors", font=("Arial", 14, "bold"))
        title.pack()

        self.entries = {}  # pid → widgets

    def update_legend(self):
        for pid, (r, g, b) in player_colors.items():
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

#Server Settings
SERVER_IP = "192.168.159.1"
SERVER_PORT = 5005
ADDR = (SERVER_IP , SERVER_PORT)
player_id_global = None
player_color = None
client_seq_num = 0

#Creating UDP Socket
client = socket.socket(socket.AF_INET , socket.SOCK_DGRAM)
client.settimeout(0.1)

def intialize_client():

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

    player_id, grid_size, tick_rate ,  r, g, b = struct.unpack("!HBBBBB", payload)

    player_colors[player_id] = (r , g, b)


    print(f"[CLIENT] JOIN_ACK received:")
    print(f"  player_id = {player_id}")
    print(f"  grid_size = {grid_size}")
    print(f"  tick_rate = {tick_rate}")
    print(f"  player_color = {player_colors[player_id]}")

    global player_id_global

    player_id_global = player_id

    # Send Ready To Recieve SnapShots message

    ready_header = pack_header(
        MsgType.READY,
        0,                
        0,            
        int(time.time() * 1000),
        0    
    )

    client.sendto(ready_header, ADDR)
    print("[Client] READY SENT")



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



def listen_for_snapshots(ui):

    #Data + Snapshot
    last_snapshot_id = -1

    last_logged_snapshot = -1
    LOG_EVERY_N = 10 

    #Send Data Messages
    while True:
        try:
            packet, addr = client.recvfrom(1200)
            recv_time_ms = int(time.time() * 1000)

            # ------------------------------
            # Parse header
            # ------------------------------
            if len(packet) < HEADER_SIZE:
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
                continue

            
            #PLAYER_COLOR Messages
            if msg_type == MsgType.PLAYER_COLOR:
                if payload_len != 5:
                    print("[CLIENT] Bad PLAYER_COLOR message")
                    continue
                
                payload = packet[HEADER_SIZE:]
                pid , r, g, b = struct.unpack("!HBBB" , payload)

                player_colors[pid] = (r , g, b)
                ui.legend.frame.after(0, ui.legend.update_legend)

                print(f"[CLIENT] Player {pid} color updated → {player_colors[pid]}")

            # -----------------------------------------------------
            # Handle snapshot messages
            # -----------------------------------------------------
            if msg_type != MsgType.SNAPSHOT:
                continue

            # DROP outdated/duplicate snapshots
            if snapshot_id <= last_snapshot_id:
                continue

            # -----------------------------------------------------
            # Extract grid snapshot payload
            # -----------------------------------------------------
            payload = packet[HEADER_SIZE:]

            if len(payload) != SNAPSHOT_SIZE * 2:
                continue

            new_snapshot_bytes = payload[:SNAPSHOT_SIZE]
            old_snapshot_bytes = payload[SNAPSHOT_SIZE:]

            decoded_new = decode_snapshot(new_snapshot_bytes)
            decoded_old = decode_snapshot(old_snapshot_bytes)

            if snapshot_id > last_snapshot_id + 1:
                ui.canvas.after(0, ui.update_grid, decoded_old)


            snapshot_buffer.append((snapshot_id, timestamp_ms, decoded_new))

            last_snapshot_id = snapshot_id

            latency = recv_time_ms - timestamp_ms

            if (last_logged_snapshot == -1) or (snapshot_id - last_logged_snapshot >= LOG_EVERY_N):
                print(
                    f"[CLIENT] Buffered snapshot {snapshot_id} | "
                    f"seq={seq_num} | server_ts={timestamp_ms} | "
                    f"latency={latency} ms"
                )
                last_logged_snapshot = snapshot_id


        except socket.timeout:
            continue
        except KeyboardInterrupt:
            print("\n[CLIENT] Shutting down...")
            break


def send_click_event(row, col, player_id):
    global client_seq_num

    cell_index = row * GRID_SIZE + col
    now_ms = int(time.time() * 1000)

    payload = struct.pack(
        EVENT_FORMAT,
        player_id,
        client_seq_num,
        EventType.CLICK,
        cell_index,
        now_ms
    )

    client_seq_num += 1

    header = pack_header(
        MsgType.EVENT,          
        0,
        client_seq_num,
        now_ms,
        len(payload)
    )

    client.sendto(header + payload, ADDR)

    print(f"[CLIENT] CLICK event sent (row={row}, col={col}, cell={cell_index})")



    

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

    # Thread to receive snapshots
    t = Thread(target=listen_for_snapshots, args=(ui,), daemon=True)
    t.start()
    ui.canvas.after(50 , process_snapshot_buffer , ui)

    root.mainloop()


if __name__ == "__main__":
    intialize_client()
    start_ui()

    #Close Connection
    client.close()
    print("[CLIENT] Connection Closed")

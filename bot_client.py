import os
import threading
import time
import random
import csv
import struct

import pygame

import client  # reuse networking code
from client import send_init, send_event, receive_loop, PLAYER_COLORS

# ----------------------------
# Bot + GUI Settings
# ----------------------------
GRID_SIZE = 20  # must match server
MOVE_INTERVAL = 0.2  # seconds between moves
FPS = 60
CELL_SIZE = 30
WINDOW_SIZE = GRID_SIZE * CELL_SIZE

WHITE = (255, 255, 255)
GRAY = (200, 200, 200)
PENDING_COLOR = (255, 0, 0, 100)
WARN_RED = (255, 50, 50)

running = True
warning_text = ""
warning_alpha = 0
warning_timer = 0

# ----------------------------
# Auto window placement
# ----------------------------
os.makedirs("logs", exist_ok=True)
index_file = "logs/bot_gui_index.txt"

try:
    with open(index_file, "r") as f:
        idx = int(f.read().strip() or "0")
except Exception:
    idx = 0

offset_x = idx * (WINDOW_SIZE + 20)
try:
    with open(index_file, "w") as f:
        f.write(str(idx + 1))
except Exception:
    pass

os.environ["SDL_VIDEO_WINDOW_POS"] = f"{offset_x},100"

# ----------------------------
# Initialize Pygame
# ----------------------------
pygame.init()
screen = pygame.display.set_mode((WINDOW_SIZE, WINDOW_SIZE))
pygame.display.set_caption("Sync-Clash Bot GUI")
clock = pygame.time.Clock()

# ----------------------------
# Client position logging
# ----------------------------
client_pos_file = open("logs/client_positions.csv", "a", newline="")
client_pos_writer = csv.writer(client_pos_file)

# If file is empty, write header once
try:
    client_pos_file.seek(0, 2)  # move to end
    if client_pos_file.tell() == 0:
        client_pos_writer.writerow(["timestamp_ms", "player_id", "x", "y"])
except Exception:
    pass

# ----------------------------
# Game State (local view)
# ----------------------------
grid_owner = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
player_positions = {}  # pid -> (x, y)

# ----------------------------
# Snapshot callback
# ----------------------------
def bot_snapshot_callback(payload):
    """
    Called from receive_loop when a SNAPSHOT arrives.
    Decode positions, update grid, log displayed positions.
    """
    player_positions.clear()
    for i in range(0, len(payload), 3):
        pid, x, y = struct.unpack("!BBB", payload[i:i+3])
        player_positions[pid] = (x, y)
        grid_owner[y][x] = pid

    # Remove ACKed pending events (same as gui_client)
    if client.player_id in player_positions:
        to_remove = [
            seq for seq, (x, y, _) in client.pending_events.items()
            if (x, y) == player_positions[client.player_id]
        ]
        for seq in to_remove:
            del client.pending_events[seq]

    # Log displayed positions based on this snapshot
    ts_ms = int(time.time() * 1000)
    for pid, (x, y) in player_positions.items():
        client_pos_writer.writerow([ts_ms, pid, x, y])
    client_pos_file.flush()

# ----------------------------
# Drawing helpers (copied from gui_client)
# ----------------------------
def draw_grid():
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            rect = pygame.Rect(col * CELL_SIZE, row * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            owner = grid_owner[row][col]
            if owner is not None:
                color = PLAYER_COLORS.get(owner, (150, 150, 150))
                pygame.draw.rect(screen, color, rect)
            else:
                pygame.draw.rect(screen, WHITE, rect)
            pygame.draw.rect(screen, GRAY, rect, 1)

def draw_players():
    for pid, (x, y) in list(player_positions.items()):
        font = pygame.font.SysFont(None, 20)
        img = font.render(str(pid), True, (0, 0, 0))
        screen.blit(img, (x * CELL_SIZE + 5, y * CELL_SIZE + 5))

def draw_pending_events():
    s = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
    s.fill(PENDING_COLOR)
    for x, y, _ in client.pending_events.values():
        screen.blit(s, (x * CELL_SIZE, y * CELL_SIZE))

def draw_warning():
    global warning_alpha, warning_timer
    if warning_alpha <= 0:
        return
    font = pygame.font.SysFont(None, 32)
    text_surface = font.render(warning_text, True, WARN_RED)
    fade_surface = text_surface.convert_alpha()
    fade_surface.set_alpha(warning_alpha)
    screen.blit(fade_surface, (10, 10))
    warning_alpha -= 3
    warning_timer -= 1

def show_warning(msg):
    global warning_text, warning_alpha, warning_timer
    warning_text = msg
    warning_alpha = 255
    warning_timer = 120

def draw_game_over():
    if not client.game_over:
        return
    font_big = pygame.font.SysFont(None, 40)
    font_small = pygame.font.SysFont(None, 28)
    overlay = pygame.Surface((WINDOW_SIZE, 80), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    screen.blit(overlay, (0, WINDOW_SIZE // 2 - 40))
    if client.game_over_winner is not None:
        winner_text = f"GAME OVER - Winner: Player {client.game_over_winner}"
    else:
        winner_text = "GAME OVER"
    text_surface = font_big.render(winner_text, True, (255, 255, 255))
    screen.blit(text_surface, (20, WINDOW_SIZE // 2 - 30))
    if client.game_over_scores:
        parts = [f"P{pid}={count}" for pid, count in sorted(client.game_over_scores.items())]
        scores_line = " ".join(parts)
        scores_surface = font_small.render(scores_line, True, (255, 255, 255))
        screen.blit(scores_surface, (20, WINDOW_SIZE // 2 + 5))

# ----------------------------
# Bot logic (unchanged behavior)
# ----------------------------
def bot_logic():
    """Periodically send random cell clicks."""
    global running
    while running:
        # Wait until we have a player_id and at least one snapshot
        if client.player_id is None or client.last_snapshot_id < 0:
            time.sleep(0.1)
            continue

        # Pick a random cell in the grid
        x = random.randint(0, GRID_SIZE - 1)
        y = random.randint(0, GRID_SIZE - 1)

        # Fire the event; server enforces cell-taken rules
        send_event(x, y)
        time.sleep(MOVE_INTERVAL)


# ----------------------------
# Main
# ----------------------------
def main():
    global running

    # Start networking
    send_init()
    threading.Thread(target=receive_loop, args=(bot_snapshot_callback,), daemon=True).start()

    # Start bot logic
    threading.Thread(target=bot_logic, daemon=True).start()

    try:
        while running:
            screen.fill(WHITE)
            draw_grid()
            draw_players()
            draw_pending_events()
            draw_warning()
            draw_game_over()

            pygame.display.flip()
            clock.tick(FPS)

            if client.last_error:
                show_warning(client.last_error)
                client.last_error = None

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

    except KeyboardInterrupt:
        running = False

    pygame.quit()
    client_pos_file.close()
    print("[BOT] Stopping")

if __name__ == "__main__":
    main()

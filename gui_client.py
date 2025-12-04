import pygame
import threading
import struct
import client  # only import the module
from client import (
    send_event,
    send_init,
    receive_loop,
    close_client,
    PLAYER_COLORS,
)


# ----------------------------
# GUI Settings
# ----------------------------
GRID_SIZE = 20                # Number of cells in one row/column
CELL_SIZE = 30                # Pixel size of each cell
WINDOW_SIZE = GRID_SIZE * CELL_SIZE
FPS = 60                      # frame will update 60 times per second

# Colors
WHITE = (255, 255, 255)       # Background color
GRAY = (200, 200, 200)        # Grid lines
PLAYER_COLOR = (0, 100, 255)  # Default player color (used if PLAYER_COLORS missing)
PENDING_COLOR = (255, 0, 0, 100)  # Semi-transparent red for pending moves
WARN_RED = (255, 50, 50)

# ----------------------------
# Initialize Pygame
# ----------------------------
pygame.init()
screen = pygame.display.set_mode((WINDOW_SIZE, WINDOW_SIZE))
pygame.display.set_caption("Sync-Clash GUI")
clock = pygame.time.Clock() # clock object to control fps

# ----------------------------
# Game State
# ----------------------------
grid_owner = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)] # None or player_id

player_positions = {}  # player_id -> (x, y)

warning_text = ""
warning_alpha = 0         # fade alpha
warning_timer = 0         # frame counter

# ----------------------------
# Snapshot callback
# ----------------------------
def snapshot_callback(payload):
    """
    runs when network receives a snapshot packet from server
    payload: bytes sent by server
    Each player encoded as 3 bytes: player_id, x, y
    """
    player_positions.clear()  # Clear old snapshot

    for i in range(0, len(payload), 3):
        pid, x, y = struct.unpack("!BBB", payload[i:i+3])
        player_positions[pid] = (x, y)

        # Mark the cell as owned automatically
        grid_owner[y][x] = pid    

    # Remove ACKed pending events
    if client.player_id in player_positions:
        to_remove = [
            seq for seq, (x, y, _) in client.pending_events.items()
            if (x, y) == player_positions[client.player_id]
        ]
        for seq in to_remove:
            del client.pending_events[seq]  # Remove ACKed moves


# ----------------------------
# Start networking
# ----------------------------
send_init()  # Send INIT packet to server

# background thread to receive packets
threading.Thread(target=receive_loop, args=(snapshot_callback,), daemon=True).start()


# ----------------------------
# Helper Functions
# ----------------------------
def draw_grid():
    """Draw the grid lines and fill owned cells"""
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            rect = pygame.Rect(col*CELL_SIZE, row*CELL_SIZE, CELL_SIZE, CELL_SIZE)
            
            # Fill cell if owned
            owner = grid_owner[row][col]
            if owner is not None:
                color = PLAYER_COLORS.get(owner, (150, 150, 150))
                pygame.draw.rect(screen, color, rect)
            else:
                pygame.draw.rect(screen, WHITE, rect)
            
            pygame.draw.rect(screen, GRAY, rect, 1) # Draw border


def draw_players():
    """Draw player ID text only (optional)"""
    # iterate over a snapshot copy to avoid 'dictionary changed size' errors
    for pid, (x, y) in list(player_positions.items()):
        font = pygame.font.SysFont(None, 20)
        img = font.render(str(pid), True, (0, 0, 0))
        screen.blit(img, (x*CELL_SIZE + 5, y*CELL_SIZE + 5))


def draw_pending_events():
    """Draw semi-transparent squares for pending (unacknowledged) moves"""
    s = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
    s.fill(PENDING_COLOR)
    for x, y, _ in client.pending_events.values():
        screen.blit(s, (x*CELL_SIZE, y*CELL_SIZE))


# ----------------------------
# WARNING SYSTEM (FADE-OUT)
# ----------------------------
def draw_warning():
    """Draw a fading warning message in red"""
    global warning_alpha, warning_timer

    if warning_alpha <= 0:
        return

    font = pygame.font.SysFont(None, 32)
    text_surface = font.render(warning_text, True, WARN_RED)
    
    # Apply alpha fading
    fade_surface = text_surface.convert_alpha()
    fade_surface.set_alpha(warning_alpha)
    screen.blit(fade_surface, (10, 10))

    # Fade down smoothly
    warning_alpha -= 3
    warning_timer -= 1


def show_warning(msg):
    """Trigger a warning that fades out"""
    global warning_text, warning_alpha, warning_timer
    warning_text = msg
    warning_alpha = 255      # full brightness
    warning_timer = 120      # ~2 seconds


# ----------------------------
# GAME OVER OVERLAY
# ----------------------------
def draw_game_over():
    """Draw GAME OVER winner and scoreboard"""
    if not client.game_over:
        return

    font_big = pygame.font.SysFont(None, 40)
    font_small = pygame.font.SysFont(None, 28)

    # Semi-transparent background banner
    overlay = pygame.Surface((WINDOW_SIZE, 80), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    screen.blit(overlay, (0, WINDOW_SIZE // 2 - 40))

    # Winner text
    if client.game_over_winner is not None:
        winner_text = f"GAME OVER - Winner: Player {client.game_over_winner}"
    else:
        winner_text = "GAME OVER"

    text_surface = font_big.render(winner_text, True, (255, 255, 255))
    screen.blit(text_surface, (20, WINDOW_SIZE // 2 - 30))

    # Scoreboard line: "P1=10  P2=8  ..."
    if client.game_over_scores:
        parts = [f"P{pid}={count}" for pid, count in sorted(client.game_over_scores.items())]
        scores_line = "  ".join(parts)
        scores_surface = font_small.render(scores_line, True, (255, 255, 255))
        screen.blit(scores_surface, (20, WINDOW_SIZE // 2 + 5))

# ----------------------------
# Main Loop
# ----------------------------
running = True
while running:
    screen.fill(WHITE)
    draw_grid()
    draw_players()
    draw_pending_events()
    draw_warning()
    draw_game_over()
    pygame.display.flip()
    clock.tick(FPS)

    # Check for server error message
    if client.last_error:
        show_warning(client.last_error)
        client.last_error = None

    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.MOUSEBUTTONDOWN and client.player_id is not None and not client.game_over:
            mx, my = pygame.mouse.get_pos() # convert mouse pos to grid coords

            cell_x = mx // CELL_SIZE
            cell_y = my // CELL_SIZE

            # Limit movement to grid boundaries
            cell_x = max(0, min(GRID_SIZE - 1, cell_x))
            cell_y = max(0, min(GRID_SIZE - 1, cell_y))

            # Prevent clicking taken cells
            if grid_owner[cell_y][cell_x] is not None:
                show_warning("Cell already taken!")
                continue

            # Mark local grid immediately
            grid_owner[cell_y][cell_x] = client.player_id

            # Update local player position
            player_positions[client.player_id] = (cell_x, cell_y)

            # Send move to server
            send_event(cell_x, cell_y)


# ----------------------------
# Cleanup
# ----------------------------
pygame.quit()
close_client()

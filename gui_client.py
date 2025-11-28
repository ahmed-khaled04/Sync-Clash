import pygame
import threading
import struct
import client  # only import the module
from client import send_event, send_init, receive_loop, close_client, PLAYER_COLORS

# ----------------------------
# GUI Settings
# ----------------------------
GRID_SIZE = 20                # Number of cells in one row/column
CELL_SIZE = 30                # Pixel size of each cell
WINDOW_SIZE = GRID_SIZE * CELL_SIZE
FPS = 60                      # Frames per second for pygame loop

# Colors
WHITE = (255, 255, 255)       # Background color
GRAY = (200, 200, 200)        # Grid lines
PLAYER_COLOR = (0, 100, 255)  # Default player color (used if PLAYER_COLORS missing)
PENDING_COLOR = (255, 0, 0, 100)  # Semi-transparent red for pending moves

# ----------------------------
# Initialize Pygame
# ----------------------------
pygame.init()
screen = pygame.display.set_mode((WINDOW_SIZE, WINDOW_SIZE))
pygame.display.set_caption("Sync-Clash GUI")
clock = pygame.time.Clock()

# ----------------------------
# Game State
# ----------------------------
grid = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]  # Not strictly needed, but can store future info
player_positions = {}  # player_id -> (x, y)

# ----------------------------
# Snapshot callback
# ----------------------------
def snapshot_callback(payload):
    """
    payload: bytes from server
    Each player encoded as 3 bytes: player_id, x, y
    """
    player_positions.clear()  # Clear old snapshot

    for i in range(0, len(payload), 3):
        pid, x, y = struct.unpack("!BBB", payload[i:i+3])
        player_positions[pid] = (x, y)

    # Remove confirmed pending events for this player
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
# Start receive loop in separate thread
threading.Thread(target=receive_loop, args=(snapshot_callback,), daemon=True).start()

# ----------------------------
# Helper Functions
# ----------------------------
def draw_grid():
    """Draw the grid lines"""
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            rect = pygame.Rect(col*CELL_SIZE, row*CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(screen, WHITE, rect)   # Fill cell
            pygame.draw.rect(screen, GRAY, rect, 1) # Draw border

def draw_players():
    """Draw all players on grid using PLAYER_COLORS and show player ID"""
    for pid, (x, y) in player_positions.items():
        color = PLAYER_COLORS.get(pid, (150, 150, 150))  # fallback gray
        rect = pygame.Rect(x*CELL_SIZE, y*CELL_SIZE, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(screen, color, rect)

        # Draw player ID text
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
# Main Loop
# ----------------------------
running = True
while running:
    screen.fill(WHITE)
    draw_grid()
    draw_players()
    draw_pending_events()  # Draw pending moves in red
    pygame.display.flip()
    clock.tick(FPS)

    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.MOUSEBUTTONDOWN and client.player_id is not None:
            mx, my = pygame.mouse.get_pos()

            cell_x = mx // CELL_SIZE
            cell_y = my // CELL_SIZE

            
            # Limit movement to grid boundaries
            cell_x = max(0, min(GRID_SIZE - 1, cell_x))
            cell_y = max(0, min(GRID_SIZE - 1, cell_y))

            # Immediate update of local player position
            player_positions[client.player_id] = (cell_x, cell_y)
            
            # Send move to server
            send_event(cell_x, cell_y)

# ----------------------------
# Cleanup
# ----------------------------
pygame.quit()
close_client()

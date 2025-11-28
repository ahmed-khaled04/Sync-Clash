import pygame
import threading
from client import client, send_event, send_init, receive_loop, close_client

# ----------------------------
# GUI Settings
# ----------------------------
GRID_SIZE = 20
CELL_SIZE = 30
WINDOW_SIZE = GRID_SIZE * CELL_SIZE
FPS = 60

# Colors
WHITE = (255, 255, 255)
GRAY = (200, 200, 200)
PLAYER_COLOR = (0, 100, 255)

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
grid = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
player_positions = {}  # player_id -> (x, y)

# ----------------------------
# Snapshot callback
# ----------------------------
def snapshot_callback(payload):
    """
    payload: bytes from server
    format: "player_id:x,y;player_id:x,y;..."
    """
    snapshot = payload.decode()
    for item in snapshot.split(";"):
        if item:
            pid, pos = item.split(":")
            x, y = map(int, pos.split(","))
            player_positions[int(pid)] = (x, y)

# ----------------------------
# Start networking
# ----------------------------
send_init()
threading.Thread(target=receive_loop, args=(snapshot_callback,), daemon=True).start()

# ----------------------------
# Helper Functions
# ----------------------------
def draw_grid():
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            rect = pygame.Rect(col*CELL_SIZE, row*CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(screen, WHITE, rect)
            pygame.draw.rect(screen, GRAY, rect, 1)

def draw_players():
    for pid, (x, y) in player_positions.items():
        rect = pygame.Rect(x*CELL_SIZE, y*CELL_SIZE, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(screen, PLAYER_COLOR, rect)

# ----------------------------
# Main Loop
# ----------------------------
running = True
while running:
    screen.fill(WHITE)
    draw_grid()
    draw_players()
    pygame.display.flip()
    clock.tick(FPS)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = pygame.mouse.get_pos()
            cell_x = mx // CELL_SIZE
            cell_y = my // CELL_SIZE
            send_event(cell_x, cell_y)

pygame.quit()
close_client()

import socket 
import time 

#Configration 
SERVER_IP = "127.0.0.1"   # Localhost for testing
SERVER_PORT = 5005        # UDP port
BUFFER_SIZE = 1024        # Max bytes to read per packet

# Create UDP socket
server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((SERVER_IP, SERVER_PORT))
print(f"[SERVER] Running on {SERVER_IP}:{SERVER_PORT}")
print("[SERVER] Waiting for clients...")

#dic for connected clients
clients = {}


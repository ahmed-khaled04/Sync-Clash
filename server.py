import socket

# Server settings
SERVER_IP = "192.168.1.102"
SERVER_PORT = 5005
ADDR = (SERVER_IP, SERVER_PORT)

# Create UDP socket
server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(ADDR)

print(f"[SERVER] Listening on {ADDR}")

while True:
    try:
        # Receive data from client
        data, client_addr = server.recvfrom(1024)
        msg = data.decode()
        print(f"[SERVER] Received from {client_addr}: {msg}")

        # Prepare reply message
        if msg.startswith("INIT"):
            reply = "ACK: Server ready!"
        elif msg.startswith("DATA"):
            reply = f"ACK: Data received -> {msg}"
        else:
            reply = "ERR: Unknown message type"

        # Send reply
        server.sendto(reply.encode(), client_addr)
        print(f"[SERVER] Sent reply to {client_addr}\n")

    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
        break

server.close()

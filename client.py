import socket
import time

#Server Settings

SERVER_IP = "192.0.0.1"
SERVER_PORT = 9999
ADDR = (SERVER_IP , SERVER_PORT)

#Creating UDP Socket
client = socket.socket(socket.AF_INET , socket.SOCK_DGRAM)
client.settimeout(3)

#Send INIT Message
init_msg = "INIT: Hello server, client ready!"
client.sendto(init_msg.encode(), ADDR)
print(f"[CLIENT] Sent INIT message to {ADDR}")

#Send Data Messages
for i in range(3):
    data_msg = f"DATA: Position update {i} (x={i*2} , y={i*3})"
    client.sendto(data_msg.encode() , ADDR)
    print(f"[CLIENT] Sent: {data_msg}")
    time.sleep(1)

    try:
        data,_ = client.recvfrom(1024)
        print("[CLIENT] recieved reply: " , data.decode())
    except socket.timeout:
        print("[CLIENT] no reply (timeout)")

    
#Close Connection
client.close()
print("[CLIENT] Connection Closed")
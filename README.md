# 🕹️ Sync-Clash (Phase 1 Prototype)

## 📘 Overview

**Sync-Clash v1** is a UDP-based prototype for a multiplayer synchronization protocol.  
This Phase 1 version demonstrates simple **INIT** and **DATA** message exchange between a client and server to prove basic connectivity over UDP.

---

## ⚙️ Requirements

- Python 3.8 or newer
- Works on Windows, Linux, or WSL
- Wireshark for viewing packets

## 📂 File Structure

```
Sync-Clash/
│
├── server.py         # Runs UDP server
├── client.py         # Sends INIT and DATA packets
├── run_baseline.sh   # Baseline test

```

## ▶️ How to Run

### 🖥️ 1. Run the Server

Open a terminal in the project folder and start:

```bash
python server.py
```

Expected output:

```
[SERVER] Listening on 127.0.0.1:9999
```

### 💻 2. Run the Client

In another terminal (same folder):

```bash
python client.py
```

Expected output:

```
[CLIENT] Sent INIT message to ('127.0.0.1', 9999)
[CLIENT] Sent: DATA: Position update 0 (x=0, y=0)
[CLIENT] Received reply: ACK: got your message
...
```

## 🧪 Run the Automated Baseline Test

This test automatically starts the server, runs the client, and saves both outputs to log files.
It demonstrates the local baseline scenario (no loss, no delay).

Run All Commands In Bash if you are using Windows.

```` `

### 1.Make the script executable

    chmod +x run_baseline.sh

### 2.Run The Test

    ./run_baseline.sh

### 3.After The Test Finishes

    Check The server_output.log to see the results
              client_output.log

```

```

## 🧾 Logs

Both server and client print logs to the console.  
You may redirect them to files for submission:

```bash
python server.py > server_output.log
python client.py > client_output.log
```

## 🎥 GitHub Repo Link

👉 **https://github.com/ahmed-khaled04/Sync-Clash**

## 🧠 Notes

- The project currently runs on localhost (127.0.0.1).
- The server replies to every message with a simple ACK.
- No reliability or synchronization logic is implemented yet — those will come in **Phase 2**.

```

```

# 🕹️ Sync-Clash

## 📘 Overview

**Sync-Clash** v7 is a UDP-based multiplayer synchronization protocol designed for the Grid Clash game.
Phase 2 implements the full protocol, including message handling, reliability features, state synchronization, logging, and automated testing under controlled network impairments.

This version includes:

✔ Full snapshot broadcasting
✔ Client-side interpolation & smoothing
✔ Sequence and snapshot ordering
✔ Redundant update mechanism
✔ Logging for server & client
✔ Automated baseline, loss, delay, and jitter tests
✔ PCAP capture + CSV result generation

---

## ⚙️ Requirements

- Python 3.8 or newer
- Works on Windows, Linux, or WSL
- Wireshark for viewing packets
- Clumsy For Network Control

## 📂 File Structure

```
Sync-Clash/
│
├── server.py                       # Runs UDP server
├── client.py                       # Runs Client Game
├── protocol.py                     # Message formats, header packing/unpacking
├── compute_positional_error.py     # For Error Calculation
├── analyze_logs.py                 # Sumarizes Logs
├── run_all_tests.sh                # All Test scripts
├── results/                        # All Test run results
├── README.md

```

## Packet Structure

| Field Name   | Size    | Description                      |
| ------------ | ------- | -------------------------------- |
| protocol_id  | 4 bytes | ASCII "GSCP" (Grid Clash Header) |
| version      | 1 byte  | Protocol version (7)             |
| msg_type     | 1 byte  | 0=JOIN,1=JOIN_ACK,2=EVENT,etc... |
| snapshot_id  | 4 bytes | Incremented by server every tick |
| seq_num      | 4 bytes | Per-packet sequence number       |
| timestamp_ms | 8 bytes | Server or client send timestamp  |
| payload_len  | 2 bytes | Size of payload                  |

## ▶️ How to Run

### 🖥️ 1. Run the Server

Open a terminal in the project folder and start:

```bash
python server.py
```

Expected output:

```
[SERVER] Server Snapshot Thread Started on 192.168.1.1
```

### 💻 2. Run the Client

In another terminal (same folder):

```bash
python client.py
```

Expected output:

```
[CLIENT] Sending JOIN ...
[CLIENT] JOIN sent, waiting for JOIN_ACK...
[CLIENT] JOIN_ACK received
...
```

## 🧪 Run the Automated Test

This test automatically starts the server, runs the client, and saves both outputs to log files.
It demonstrates the local baseline scenario (no loss, no delay).

Run All Commands In Bash if you are using Windows.

```` `

### 1.Make the script executable

    chmod +x run_all_tests.sh

### 2. Open Clumsy And set The Condition of The Network

### 3.Run The Test

    ./run_all_tests.sh

### 4.After The Test Finishes

    Check The Results folder in the correct test you ran
        and see the outputs and plots.

```

```

## 🎥 GitHub Repo Link

👉 **https://github.com/ahmed-khaled04/Sync-Clash**

```

```

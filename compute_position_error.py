import csv
import math

# Input files
SERVER_POS_CSV = "logs/server_positions.csv"
CLIENT_POS_CSV = "logs/client_positions.csv"

# Output file
ERROR_CSV = "logs/position_error.csv"

# Max time difference (ms) to consider positions "matching"
MAX_TIME_DIFF_MS = 100  # can tune this


def load_server_positions():
    # server: timestamp_ms, snapshot_id, player_id, x, y
    data = {}  # player_id -> list of (t, x, y)
    with open(SERVER_POS_CSV, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = int(row["timestamp_ms"])
            pid = int(row["player_id"])
            x = int(row["x"])
            y = int(row["y"])
            data.setdefault(pid, []).append((t, x, y))
    # sort each player's list by time
    for pid in data:
        data[pid].sort(key=lambda e: e[0])
    return data


def load_client_positions():
    # client: timestamp_ms, player_id, x, y
    data = {}  # player_id -> list of (t, x, y)
    with open(CLIENT_POS_CSV, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = int(row["timestamp_ms"])
            pid = int(row["player_id"])
            x = int(row["x"])
            y = int(row["y"])
            data.setdefault(pid, []).append((t, x, y))
    # sort each player's list by time
    for pid in data:
        data[pid].sort(key=lambda e: e[0])
    return data


def find_nearest(server_list, t_client):
    """
    server_list: sorted list of (t_server, x, y)
    return nearest (t_server, x, y) to t_client if within MAX_TIME_DIFF_MS, else None
    """
    # simple linear scan is fine for small logs; you can optimize later if needed
    best = None
    best_diff = None
    for t_s, x_s, y_s in server_list:
        diff = abs(t_s - t_client)
        if best is None or diff < best_diff:
            best = (t_s, x_s, y_s)
            best_diff = diff
    if best is None or best_diff is None or best_diff > MAX_TIME_DIFF_MS:
        return None
    return best


def main():
    server_data = load_server_positions()
    client_data = load_client_positions()

    with open(ERROR_CSV, "w", newline="") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(["timestamp_ms", "player_id", "server_x", "server_y",
                         "client_x", "client_y", "error"])

        for pid, client_list in client_data.items():
            if pid not in server_data:
                continue
            server_list = server_data[pid]

            for t_c, x_c, y_c in client_list:
                match = find_nearest(server_list, t_c)
                if match is None:
                    continue
                t_s, x_s, y_s = match
                # Euclidean distance
                error = math.sqrt((x_s - x_c) ** 2 + (y_s - y_c) ** 2)
                # use client timestamp as reference
                writer.writerow([t_c, pid, x_s, y_s, x_c, y_c, error])

    print(f"Wrote position errors to {ERROR_CSV}")


if __name__ == "__main__":
    main()

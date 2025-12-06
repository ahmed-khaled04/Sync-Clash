import csv
import numpy as np

SERVER_FILE = "server_positions.csv"
CLIENT_FILE = "client_positions.csv"
OUTPUT_FILE = "position_error_results.csv"

GRID_SIZE = 20
CELL_COUNT = GRID_SIZE * GRID_SIZE


def load_server_positions():
    timestamps = []
    grids = []

    with open(SERVER_FILE, "r") as f:
        reader = csv.reader(f)

        for row in reader:
            if not row:
                continue

            if row[0].lower().startswith("snapshot") or not row[0].isdigit():
                continue

            if len(row) != CELL_COUNT + 2:
                print("[WARN] Skipping bad server row:", len(row))
                continue

            ts = int(row[1])
            grid_values = list(map(int, row[2:]))

            timestamps.append(ts)
            grids.append(grid_values)

    return np.array(timestamps), np.array(grids)


def load_client_positions():
    timestamps = []
    grids = []

    with open(CLIENT_FILE, "r") as f:
        reader = csv.reader(f)

        for row in reader:
            if not row:
                continue

            if row[0].lower().startswith("player") or not row[0].isdigit():
                continue

            if len(row) != CELL_COUNT + 2:
                print("[WARN] Skipping bad client row:", len(row))
                continue

            ts = int(row[1])
            grid_values = list(map(int, row[2:]))

            timestamps.append(ts)
            grids.append(grid_values)

    return np.array(timestamps), np.array(grids)


def compute_positional_error(server_grid, client_grid):

    diffs = (server_grid != client_grid).astype(int)
    return diffs.sum()


def main():
    print("[INFO] Loading logs...")
    server_ts, server_grids = load_server_positions()
    client_ts, client_grids = load_client_positions()

    errors = []
    matched_times = []

    si = 0
    ci = 0

    print("[INFO] Matching timestamps and computing error...")

    while si < len(server_ts) and ci < len(client_ts):

        if client_ts[ci] < server_ts[si]:
            ci += 1
            continue

        error = compute_positional_error(server_grids[si], client_grids[ci])
        errors.append(error)
        matched_times.append(server_ts[si])

        si += 1

    errors = np.array(errors)

    if len(errors) == 0:
        print("[ERROR] No matched timestamps. Check your logs.")
        return

    mean_error = float(np.mean(errors))
    p95_error = float(np.percentile(errors, 95))

    print("\n===== POSITION ERROR RESULTS =====")
    print(f"Mean Error: {mean_error}")
    print(f"95th Percentile Error: {p95_error}")
    print("=================================\n")

    # Save results to CSV for plotting
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.writer(f)

        writer.writerow(["timestamp", "positional_error"])
        for ts, err in zip(matched_times, errors):
            writer.writerow([ts, err])

    print(f"[INFO] Saved detailed error results to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

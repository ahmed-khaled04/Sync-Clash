import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

server_file = Path("server_metrics.csv")
client_file = Path("client_metrics.csv")
positional_file = Path("position_error_results.csv")


for f in [server_file, client_file, positional_file]:
    if not f.exists():
        raise FileNotFoundError(f"{f.name} not found in script directory")

df_server = pd.read_csv(server_file)
df_client = pd.read_csv(client_file)
df_pos = pd.read_csv(positional_file)


summary_client = df_client.groupby("client_id").agg(
    avg_latency=("latency_ms", "mean"),
    median_latency=("latency_ms", "median"),
    p95_latency=("latency_ms", lambda x: x.quantile(0.95)),

    avg_jitter=("jitter_ms", "mean"),
    median_jitter=("jitter_ms", "median"),
    p95_jitter=("jitter_ms", lambda x: x.quantile(0.95)),

    avg_bandwidth=("bandwidth_per_client_kbps", "mean"),
    packet_count=("snapshot_id", "count")
).reset_index()


summary_error = pd.DataFrame({
    "avg_error": [df_pos["positional_error"].mean()],
    "median_error": [df_pos["positional_error"].median()],
    "p95_error": [df_pos["positional_error"].quantile(0.95)]
})


summary_client.to_csv("summary_metrics.csv", index=False)

with open("summary_metrics.csv", "a") as f:
    f.write("\n\nPositional Error Summary\n")
    summary_error.to_csv(f, index=False)

print("[SUCCESS] Summary saved with mean, median, and 95th percentile values.")


# PLOT 1: Latency Per Snapshot
plt.figure()
for pid in df_client["client_id"].unique():
    sub = df_client[df_client["client_id"] == pid]
    plt.plot(sub["snapshot_id"], sub["latency_ms"], label=f"Client {pid}")

plt.xlabel("Snapshot ID")
plt.ylabel("Latency (ms)")
plt.title("Latency Over Time Per Client")
plt.legend()
plt.savefig("latency_plot.png")
plt.close()

# PLOT 2: Jitter Per Snapshot
plt.figure()
for pid in df_client["client_id"].unique():
    sub = df_client[df_client["client_id"] == pid]
    plt.plot(sub["snapshot_id"], sub["jitter_ms"], label=f"Client {pid}")

plt.xlabel("Snapshot ID")
plt.ylabel("Jitter (ms)")
plt.title("Jitter Over Time Per Client")
plt.legend()
plt.savefig("jitter_plot.png")
plt.close()

# PLOT 3: CPU Usage Over Time
plt.figure()
plt.plot(df_server["timestamp"], df_server["cpu_percent"])
plt.xlabel("Timestamp")
plt.ylabel("CPU Usage (%)")
plt.title("Server CPU Usage")
plt.savefig("cpu_plot.png")
plt.close()

# PLOT 4: Positional Error
plt.figure()

plt.plot(df_pos["timestamp"], df_pos["positional_error"])

plt.xlabel("Timestamp (ms)")
plt.ylabel("Positional Error")
plt.title("Positional Error Over Time")

plt.savefig("positional_error_plot.png")
plt.close()

print("[SUCCESS] Positional error plot created using timestamp")

print("[FINISHED] All plots exported successfully!")
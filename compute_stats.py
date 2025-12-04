import csv
import math
from statistics import mean, median

def load_column(filename, column_name):
    values = []
    with open(filename, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            val = row.get(column_name)
            # Skip missing or empty values
            if val is None or val == "":
                continue
            try:
                values.append(float(val))
            except ValueError:
                continue
    return values

def percentile(values, p):
    if not values:
        return None
    vals = sorted(values)
    k = (len(vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return vals[int(k)]
    d0 = vals[f] * (c - k)
    d1 = vals[c] * (k - f)
    return d0 + d1

def print_stats(name, values):
    if not values:
        print(f"{name}: no data")
        return
    print(f"{name}:")
    print(f"  count = {len(values)}")
    print(f"  mean  = {mean(values):.3f}")
    print(f"  median= {median(values):.3f}")
    p95 = percentile(values, 95)
    print(f"  p95   = {p95:.3f}" if p95 is not None else "  p95   = n/a")
    print()

def main():
    # From client_log.csv
    lat = load_column("client_log.csv", "latency_ms")
    jit = load_column("client_log.csv", "jitter_ms")

    # From position_error.csv
    err = load_column("position_error.csv", "error")

    print_stats("Latency (ms)", lat)
    print_stats("Jitter (ms)", jit)
    print_stats("Perceived position error (cells)", err)

if __name__ == "__main__":
    main()

#!/bin/bash
PID="$1"
OUT="$2"

echo "timestamp_ms,cpu_percent" > "$OUT"

while kill -0 "$PID" 2>/dev/null; do
  ts=$(($(date +%s%N)/1000000))
  cpu=$(ps -p "$PID" -o %cpu= | tr -d ' ')
  echo "$ts,$cpu" >> "$OUT"
  sleep 0.5
done

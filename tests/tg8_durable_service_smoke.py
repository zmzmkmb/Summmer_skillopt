"""Offline service-lifecycle probe. No datasets, environments, or network calls."""
import json
import os
import time


if __name__ == "__main__":
    isolated = os.readlink("/proc/self/ns/net") != os.readlink("/proc/1/ns/net")
    if not isolated:
        raise RuntimeError("service did not enter a private network namespace")
    print(json.dumps({"event": "started", "pid": os.getpid(), "isolated": isolated}), flush=True)
    time.sleep(10)
    print(json.dumps({"event": "completed", "formal_episodes": 0}), flush=True)

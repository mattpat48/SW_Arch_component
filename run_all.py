import os
import sys
import subprocess
import signal
import time

SCRIPTS = ["analyzer.py", "publisher.py", "dashboard.py"]


def ensure_logs_dir(path="logs"):
    os.makedirs(path, exist_ok=True)
    return path


def start_processes(scripts, logs_dir):
    procs = []
    python = sys.executable
    for s in scripts:
        logfile_path = os.path.join(logs_dir, f"{os.path.splitext(os.path.basename(s))[0]}.log")
        f = open(logfile_path, "ab")
        p = subprocess.Popen([python, s], stdout=f, stderr=subprocess.STDOUT)
        procs.append((p, f, s))
        print(f"Started {s} (pid={p.pid}), logging to {logfile_path}")
    return procs


def stop_processes(procs, timeout=5.0):
    for p, f, s in procs:
        if p.poll() is None:
            try:
                print(f"Terminating {s} (pid={p.pid})")
                p.terminate()
            except Exception:
                pass
    # wait
    end = time.time() + timeout
    for p, f, s in procs:
        remaining = max(0, end - time.time())
        try:
            p.wait(timeout=remaining)
        except Exception:
            try:
                print(f"Killing {s} (pid={p.pid})")
                p.kill()
            except Exception:
                pass
    for p, f, s in procs:
        try:
            f.close()
        except Exception:
            pass


def main():
    logs_dir = ensure_logs_dir()
    procs = start_processes(SCRIPTS, logs_dir)

    def _handler(signum, frame):
        print("Received exit signal, shutting down children...")
        stop_processes(procs)
        sys.exit(0)

    signal.signal(signal.SIGINT, _handler)
    try:
        # SIGTERM may not be available on all platforms the same way, but try to set it
        signal.signal(signal.SIGTERM, _handler)
    except Exception:
        pass

    try:
        # monitor children and exit when all finished
        while True:
            alive = [p for p, f, s in procs if p.poll() is None]
            if not alive:
                print("All child processes exited.")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        _handler(None, None)


if __name__ == "__main__":
    main()

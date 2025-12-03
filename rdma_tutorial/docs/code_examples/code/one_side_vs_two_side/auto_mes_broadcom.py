#!/usr/bin/env python3
import subprocess
import re
import csv
from pathlib import Path
import matplotlib.pyplot as plt

SERVER_IP = "fd93:16d3:59b6:12e:7ec2:55ff:febd:dc76"
PORT = 9000

BENCH_CLIENT = "./bench_client_broadcom"
BENCH_SERVER = "./bench_server_broadcom"

RESULT_CSV = "rdma_msg_sweep_test_broadcom_2.csv"
PLOT_DIR = Path("plots_msg_sweep_test_broadcom_2")

FIXED_WINDOW = 512
ITERS = 200000
MSG_LIST = [
    256,
    512,
    1024,
    2048,
    4096,
    8192,
    16384,
    32768,
    65536,
    131072,
]

MODES = ["write", "send"]

CLIENT_LINE_RE = re.compile(
    r"\[client\]\s+(\w+)\s+done:\s+([0-9.]+)\s+Mops,\s+([0-9.]+)\s+GiB/s"
)


def run_client(mode: str, msg: int, iters: int, window: int):
    cmd = [
        BENCH_CLIENT,
        SERVER_IP,
        str(PORT),
        "--mode",
        mode,
        "--msg",
        str(msg),
        "--iters",
        str(iters),
        "--window",
        str(window),
    ]
    print("\n=== Running client ===")
    print(" ".join(cmd))

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("!! bench_client exited with non-zero code:", proc.returncode)
        print("stdout:\n", proc.stdout)
        print("stderr:\n", proc.stderr)
        return None

    print("client stdout:\n", proc.stdout.strip())

    m = None
    for line in proc.stdout.splitlines()[::-1]:
        m = CLIENT_LINE_RE.search(line)
        if m:
            break
    if not m:
        raise RuntimeError("Cannot parse client output for Mops/GiB/s")

    mode_str, mops_str, gib_str = m.groups()
    return {
        "mode": mode_str,
        "mops": float(mops_str),
        "gib": float(gib_str),
        "raw_stdout": proc.stdout.strip(),
    }


def ask_start_server(mode: str, msg: int, iters: int):
    if mode == "send":
        srv_cmd = (
            f"{BENCH_SERVER} {PORT} --mode send --msg {msg} "
            f"--iters {iters} --recv-depth {max(256, FIXED_WINDOW * 4)}"
        )
    elif mode in ("write", "read"):
        srv_cmd = f"{BENCH_SERVER} {PORT} --mode {mode} --msg {msg} --iters {iters}"
    else:
        raise ValueError(f"Unknown mode: {mode}")

    print("\n========================================")
    print("On the SERVER machine run:")
    print(f"  {srv_cmd}")
    print("After the server is ready, press ENTER here to start the client...")
    input("Press ENTER to run client...")


def append_result_csv(rows):
    file_exists = Path(RESULT_CSV).exists()
    fieldnames = [
        "experiment",
        "mode",
        "msg",
        "window",
        "iters",
        "mops",
        "gib",
    ]
    with open(RESULT_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for r in rows:
            writer.writerow(r)


def run_msg_sweep():
    print(
        f"\n\n===== Fixed window={FIXED_WINDOW}, sweeping message size (write & send) ====="
    )
    results = []

    for msg in MSG_LIST:
        for mode in MODES:
            print(f"\n--- Msg sweep: msg={msg}, window={FIXED_WINDOW}, mode={mode} ---")
            ask_start_server(mode, msg, ITERS)
            data = run_client(
                mode=mode,
                msg=msg,
                iters=ITERS,
                window=FIXED_WINDOW,
            )

            if data is None:
                print(
                    f"*** Combination failed: msg={msg}, window={FIXED_WINDOW}, "
                    f"mode={mode}, recording NaN and continuing ***"
                )
                row = {
                    "experiment": "msg_sweep",
                    "mode": mode,
                    "msg": msg,
                    "window": FIXED_WINDOW,
                    "iters": ITERS,
                    "mops": float("nan"),
                    "gib": float("nan"),
                }
            else:
                row = {
                    "experiment": "msg_sweep",
                    "mode": mode,
                    "msg": msg,
                    "window": FIXED_WINDOW,
                    "iters": ITERS,
                    "mops": data["mops"],
                    "gib": data["gib"],
                }

            results.append(row)
            print(
                f"Recorded: mode={mode}, msg={msg}, window={FIXED_WINDOW}, "
                f"Mops={row['mops']}, GiB/s={row['gib']}"
            )

    append_result_csv(results)
    print("\nMsg sweep finished, results written to", RESULT_CSV)


def load_results():
    import pandas as pd

    df = pd.read_csv(RESULT_CSV)
    return df


def plot_results():
    import pandas as pd

    PLOT_DIR.mkdir(exist_ok=True)
    df = load_results()

    sweep = df[(df["experiment"] == "msg_sweep")]
    if sweep.empty:
        print("No msg_sweep data found. Run experiments before plotting.")
        return

    plt.figure()
    for mode in MODES:
        s = sweep[sweep["mode"] == mode].sort_values("msg")
        if s.empty:
            continue
        plt.plot(s["msg"], s["gib"], marker="o", label=f"{mode}")
    plt.xlabel("Message size (bytes)")
    plt.ylabel("Throughput (GiB/s)")
    plt.title(f"Throughput vs message size (window={FIXED_WINDOW})")
    plt.xscale("log", base=2)
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / f"msg_sweep_gib_w{FIXED_WINDOW}.png", dpi=200)
    plt.close()

    plt.figure()
    for mode in MODES:
        s = sweep[sweep["mode"] == mode].sort_values("msg")
        if s.empty:
            continue
        plt.plot(s["msg"], s["mops"], marker="o", label=f"{mode}")
    plt.xlabel("Message size (bytes)")
    plt.ylabel("Operations (Mops)")
    plt.title(f"Ops vs message size (window={FIXED_WINDOW})")
    plt.xscale("log", base=2)
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / f"msg_sweep_mops_w{FIXED_WINDOW}.png", dpi=200)
    plt.close()

    print(f"\nPlots saved to: {PLOT_DIR.resolve()}")


def main():
    print("This script assumes:")
    print(f"  Client can run: {BENCH_CLIENT}")
    print(f"  Server can run: {BENCH_SERVER}")
    print(f"  Server IP = {SERVER_IP}, port = {PORT}")
    print(f"  Fixed window = {FIXED_WINDOW}")
    print("\nMenu:")

    while True:
        print("\nSelect an option:")
        print("  1) Run msg sweep experiment (fixed window)")
        print("  2) Plot using existing CSV")
        print("  q) Quit")
        choice = input("> ").strip().lower()
        if choice == "1":
            run_msg_sweep()
        elif choice == "2":
            plot_results()
        elif choice == "q":
            break
        else:
            print("Invalid input, please try again.")


if __name__ == "__main__":
    main()

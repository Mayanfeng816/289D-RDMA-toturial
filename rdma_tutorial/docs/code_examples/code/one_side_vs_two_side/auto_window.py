#!/usr/bin/env python3
import subprocess
import re
import csv
from pathlib import Path
import matplotlib.pyplot as plt


# ================== 配置区 ==================

# 改成你的 server IP
SERVER_IP = "144.202.54.39"
PORT = 9000

# 可执行文件路径（相对脚本位置或绝对路径）
BENCH_CLIENT = "./bench_client"
BENCH_SERVER = "./bench_server"

# 结果输出
RESULT_CSV = "rdma_results.csv"
PLOT_DIR = Path("plots")

# 实验参数
BASELINE_MSG = 8192
BASELINE_ITERS = 100000

SWEEP_MSG_LIST = [32, 64]
SWEEP_WINDOWS = [1, 2, 4, 8, 16, 32, 64]
SWEEP_ITERS = 200000

MODES = ["write", "send"]


# ================== 工具函数 ==================

CLIENT_LINE_RE = re.compile(
    r"\[client\]\s+(\w+)\s+done:\s+([0-9.]+)\s+Mops,\s+([0-9.]+)\s+GiB/s"
)


def run_client(mode: str, msg: int, iters: int, window: int):
    """运行 bench_client 并解析 Mops / GiB/s。"""
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
        # 返回 None，让上层决定怎么处理这个失败
        return None

    print("client stdout:\n", proc.stdout.strip())

    # 找最后一行 [client] ... done
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
    """提示你在 server 上启动 bench_server, 并等待回车。"""
    if mode == "send":
        srv_cmd = f"{BENCH_SERVER} {PORT} --mode send --msg {msg} --iters {iters} --recv-depth 256"
    elif mode in ("write", "read"):
        srv_cmd = f"{BENCH_SERVER} {PORT} --mode {mode} --msg {msg} --iters {iters}"
    else:
        raise ValueError(f"Unknown mode: {mode}")

    print("\n========================================")
    print(f"在 SERVER 机器上运行（手动）:")
    print(f"  {srv_cmd}")
    print("确认 server 已经启动后, 在本窗口按回车继续...")
    input("Press ENTER to run client...")


def append_result_csv(rows):
    """把结果追加写入 CSV 文件。第一次写会加表头。"""
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


# ================== 实验定义 ==================


def run_baseline_experiment():
    """实验 0:大消息 baseline（write & send）。"""
    print(
        "\n\n===== 实验 0:Baseline (msg = {}, window = 64) =====".format(BASELINE_MSG)
    )
    results = []

    for mode in MODES:
        print(f"\n--- Baseline mode={mode} ---")
        ask_start_server(mode, BASELINE_MSG, BASELINE_ITERS)
        data = run_client(
            mode=mode,
            msg=BASELINE_MSG,
            iters=BASELINE_ITERS,
            window=64,
        )
        row = {
            "experiment": "baseline",
            "mode": mode,
            "msg": BASELINE_MSG,
            "window": 64,
            "iters": BASELINE_ITERS,
            "mops": data["mops"],
            "gib": data["gib"],
        }
        results.append(row)
        print(
            f"Recorded: mode={mode}, msg={BASELINE_MSG}, window=64, "
            f"Mops={data['mops']:.3f}, GiB/s={data['gib']:.3f}"
        )

    append_result_csv(results)
    print("\nBaseline 实验完成, 结果已写入", RESULT_CSV)


def run_sweep_experiments():
    """实验 1:小消息 + 扫 window, write & send 对比。"""
    print("\n\n===== 实验 1:小消息 + window 扫描（write vs send） =====")
    results = []

    for msg in SWEEP_MSG_LIST:
        for win in SWEEP_WINDOWS:
            for mode in MODES:
                print(f"\n--- Sweep: msg={msg}, window={win}, mode={mode} ---")
                ask_start_server(mode, msg, SWEEP_ITERS)
                data = run_client(
                    mode=mode,
                    msg=msg,
                    iters=SWEEP_ITERS,
                    window=win,
                )
                if data is None:
                    # 这个组合跑挂了（比如 RNR retry exceeded）
                    print(
                        f"*** 组合失败: msg={msg}, window={win}, mode={mode}，记录为 NaN，继续下一组 ***"
                    )
                    row = {
                        "experiment": "sweep",
                        "mode": mode,
                        "msg": msg,
                        "window": win,
                        "iters": SWEEP_ITERS,
                        "mops": float("nan"),
                        "gib": float("nan"),
                    }
                else:
                    row = {
                        "experiment": "sweep",
                        "mode": mode,
                        "msg": msg,
                        "window": win,
                        "iters": SWEEP_ITERS,
                        "mops": data["mops"],
                        "gib": data["gib"],
                    }
                results.append(row)
                print(
                    f"Recorded: mode={mode}, msg={msg}, window={win}, "
                    f"Mops={data['mops']:.3f}, GiB/s={data['gib']:.3f}"
                )

    append_result_csv(results)
    print("\nSweep 实验完成, 结果已写入", RESULT_CSV)


# ================== 画图 ==================


def load_results():
    import pandas as pd

    df = pd.read_csv(RESULT_CSV)
    return df


def plot_results():
    import pandas as pd

    PLOT_DIR.mkdir(exist_ok=True)
    df = load_results()

    # 画 baseline:不同 mode 在 baseline 上的对比（柱状 or 点都行）
    base = df[(df["experiment"] == "baseline")]
    if not base.empty:
        plt.figure()
        xs = list(range(len(base)))
        labels = [f"{m}" for m in base["mode"]]
        gibs = base["gib"].to_list()
        plt.bar(xs, gibs)
        plt.xticks(xs, labels)
        plt.ylabel("Throughput (GiB/s)")
        plt.title(f"Baseline: msg={BASELINE_MSG}, window=64")
        plt.tight_layout()
        plt.savefig(PLOT_DIR / "baseline_throughput.png", dpi=200)
        plt.close()

    # 画 sweep:对每个 msg, 画 window vs GiB/s / Mops
    sweep = df[(df["experiment"] == "sweep")]
    if not sweep.empty:
        for msg in sorted(sweep["msg"].unique()):
            sub = sweep[sweep["msg"] == msg]

            # GiB/s vs window
            plt.figure()
            for mode in MODES:
                s = sub[sub["mode"] == mode].sort_values("window")
                if s.empty:
                    continue
                plt.plot(s["window"], s["gib"], marker="o", label=f"{mode}")
            plt.xlabel("window size (outstanding requests)")
            plt.ylabel("Throughput (GiB/s)")
            plt.title(f"Throughput vs window (msg={msg} bytes)")
            plt.legend()
            plt.grid(True, linestyle="--", alpha=0.5)
            plt.tight_layout()
            plt.savefig(PLOT_DIR / f"sweep_msg{msg}_gib.png", dpi=200)
            plt.close()

            # Mops vs window
            plt.figure()
            for mode in MODES:
                s = sub[sub["mode"] == mode].sort_values("window")
                if s.empty:
                    continue
                plt.plot(s["window"], s["mops"], marker="o", label=f"{mode}")
            plt.xlabel("window size (outstanding requests)")
            plt.ylabel("Operations (Mops)")
            plt.title(f"Ops vs window (msg={msg} bytes)")
            plt.legend()
            plt.grid(True, linestyle="--", alpha=0.5)
            plt.tight_layout()
            plt.savefig(PLOT_DIR / f"sweep_msg{msg}_mops.png", dpi=200)
            plt.close()

    print(f"\n画图完成, 图片保存在目录: {PLOT_DIR.resolve()}")


# ================== main ==================


def main():
    print("本脚本假设:")
    print(f"  client 上可以直接运行: {BENCH_CLIENT}")
    print(f"  server 上可以直接运行: {BENCH_SERVER}")
    print(f"  server IP = {SERVER_IP}, port = {PORT}")
    print("\n建议:先跑 baseline, 再跑 sweep, 再画图。")

    while True:
        print("\n请选择操作:")
        print("  1) 运行 实验 0:baseline (8KB, window=64)")
        print("  2) 运行 实验 1:小消息 + window 扫描")
        print("  3) 只画图（使用已有 CSV)")
        print("  q) 退出")
        choice = input("> ").strip().lower()
        if choice == "1":
            run_baseline_experiment()
        elif choice == "2":
            run_sweep_experiments()
        elif choice == "3":
            plot_results()
        elif choice == "q":
            break
        else:
            print("无效输入, 请重新选择。")


if __name__ == "__main__":
    main()

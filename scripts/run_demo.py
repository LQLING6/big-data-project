"""Run the bundled demo on localhost. Stops only the children it creates."""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="Start the local CampusComp demo")
    parser.add_argument("--check", action="store_true", help="start, verify and stop the demo")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("端口必须在1—65535之间")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    missing = [name for name in ["fastapi", "uvicorn", "sqlalchemy", "alembic", "pydantic"]
               if importlib.util.find_spec(name) is None]
    if missing:
        print("请先安装依赖：python -m pip install -r backend/requirements-dev.txt")
        return 1
    if not (ROOT / "frontend-dist" / "index.html").exists():
        print("缺少前端构建，请先按README安装前端依赖，再执行python scripts/build_frontend.py")
        return 1
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    backend = ROOT / "backend"
    subprocess.run([sys.executable, "-m", "app.cli", "init-demo"], cwd=backend, env=env, check=True)
    log_dir = ROOT / "data"
    log_dir.mkdir(exist_ok=True)
    hidden_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (log_dir / "local-worker.log").open("a", encoding="utf-8") as log:
        worker = subprocess.Popen([sys.executable, "-m", "app.cli", "worker"], cwd=backend, env=env,
                                  stdout=log, stderr=log, creationflags=hidden_flags)
        api = None
        try:
            print(f"\n赛知演示地址：http://127.0.0.1:{args.port}\n按Ctrl+C停止。\n", flush=True)
            api = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.port)], cwd=backend, env=env)
            if args.check:
                limit = time.monotonic() + 15
                while time.monotonic() < limit and api.poll() is None and worker.poll() is None:
                    try:
                        with urlopen(f"http://127.0.0.1:{args.port}/", timeout=1) as response:
                            if response.status == 200:
                                print("启动检查通过：页面、API进程、本地Worker已启动。")
                                return 0
                    except OSError:
                        time.sleep(0.3)
                print("启动检查失败，请查看终端和data/local-worker.log。")
                return 1
            return api.wait()
        except KeyboardInterrupt:
            print("正在停止本次启动的演示进程…")
            return 0
        finally:
            for process in [api, worker]:
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


if __name__ == "__main__":
    raise SystemExit(main())

import argparse
import time
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import settings


def main():
    parser = argparse.ArgumentParser(description="CampusComp starter tools")
    parser.add_argument("command", choices=["migrate", "init-demo", "import-fixtures", "run-cycle", "worker"])
    args = parser.parse_args()
    if args.command in {"migrate", "init-demo"}:
        root = Path(__file__).resolve().parents[1]
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "migrations"))
        config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
        command.upgrade(config, "head")
        print("数据库迁移完成")
    if args.command in {"init-demo", "import-fixtures"}:
        from app.seed import seed_demo
        print(seed_demo())
    if args.command == "run-cycle":
        from app.worker import run_inline_cycle
        print(run_inline_cycle())
    if args.command == "worker":
        from app.worker import run_inline_cycle
        print("本地单进程提醒 Worker 已启动，间隔30秒。Ctrl+C退出。")
        try:
            while True:
                print(run_inline_cycle(), flush=True)
                time.sleep(30)
        except KeyboardInterrupt:
            print("Worker已停止")


if __name__ == "__main__":
    main()

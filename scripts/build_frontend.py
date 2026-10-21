"""Build and copy browser assets for the Python-only demo."""
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
manager = shutil.which("pnpm") or shutil.which("npm")
if manager is None:
    raise SystemExit("请先安装Node和pnpm或npm，并按README安装frontend依赖")
subprocess.run([manager, "run", "build"], cwd=root / "frontend", check=True)
shutil.copytree(root / "frontend" / "dist", root / "frontend-dist", dirs_exist_ok=True)
print("前端已构建到frontend-dist，可启动Python演示")

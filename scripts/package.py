"""Create a source + prebuilt UI archive without caches, credentials or runtime data."""
import hashlib
import os
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
destination = root.parent / f"{root.name}.zip"
excluded_dirs = {"node_modules", ".pnpm-store", ".venv", "__pycache__", ".pytest_cache", ".git", "data", "dist", "frontend-dist"}

with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for directory, subdirs, filenames in os.walk(root):
        subdirs[:] = [name for name in subdirs if name not in excluded_dirs]
        for filename in sorted(filenames):
            if filename == ".env" or filename.endswith((".db", ".db-shm", ".db-wal", ".pyc")) or filename.startswith("celerybeat-schedule"):
                continue
            file = Path(directory) / filename
            archive.write(file, (Path(root.name) / file.relative_to(root)).as_posix())
    build = root / "frontend" / "dist"
    if not (build / "index.html").exists():
        raise SystemExit("Build frontend before packaging")
    for file in build.rglob("*"):
        if file.is_file():
            archive.write(file, (Path(root.name) / "frontend-dist" / file.relative_to(build)).as_posix())

with zipfile.ZipFile(destination) as archive:
    if archive.testzip() is not None:
        raise SystemExit("Archive integrity check failed")
    names = archive.namelist()
    assert f"{root.name}/README.md" in names
    assert f"{root.name}/frontend-dist/index.html" in names
    assert len([name for name in names if "/docs/tasks/TASK-" in name]) == 4
    assert not any("/node_modules/" in name or name.endswith(".db") or name.endswith("/.env") for name in names)
digest = hashlib.sha256(destination.read_bytes()).hexdigest()
destination.with_suffix(".zip.sha256").write_text(f"{digest}  {destination.name}\n", encoding="utf-8")
print(f"Archive: {destination.name}; files: {len(names)}; bytes: {destination.stat().st_size}; SHA256: {digest}")

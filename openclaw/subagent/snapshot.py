import shutil
from pathlib import Path


class SnapshotManager:
    def __init__(self, workspace_dir, keep=5):
        self.workspace_dir = Path(workspace_dir)
        self.keep = keep
        self.snapshots_dir = self.workspace_dir / ".pi" / "snapshots"

    def create(self, slice_id):
        snapshot_dir = self.snapshots_dir / slice_id
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        src = self.workspace_dir / "src"
        dst = snapshot_dir / "src"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

    def restore(self, slice_id):
        snapshot_src = self.snapshots_dir / slice_id / "src"
        target_src = self.workspace_dir / "src"
        if target_src.exists():
            shutil.rmtree(target_src)
        shutil.copytree(snapshot_src, target_src)

    def cleanup(self):
        if not self.snapshots_dir.exists():
            return
        snapshots = sorted(
            [d for d in self.snapshots_dir.iterdir() if d.is_dir()],
            key=lambda p: p.stat().st_mtime,
        )
        for old in snapshots[:-self.keep]:
            shutil.rmtree(old)

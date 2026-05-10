from pathlib import Path


class ScoutAgent:
    def __init__(self, workspace_dir):
        self.workspace_dir = Path(workspace_dir)

    def run(self):
        src_dir = self.workspace_dir / "src"
        files = list(src_dir.rglob("*")) if src_dir.exists() else []
        files = [f for f in files if f.is_file() and not f.is_symlink()]

        lines = []
        total_lines = 0
        for f in files:
            content = f.read_text()
            count = len(content.splitlines()) if content else 0
            total_lines += count
            lines.append(f"- {f.relative_to(src_dir)}: {count} lines")

        report_lines = ["# Scout Report", ""]
        if lines:
            report_lines.extend(lines)
            report_lines.append("")
            report_lines.append(f"Total: {total_lines} lines of code")
        else:
            report_lines.append("No source files found.")

        report = "\n".join(report_lines)

        report_path = self.workspace_dir / ".pi" / "scout_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report)

        return report

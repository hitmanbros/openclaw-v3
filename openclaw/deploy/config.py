"""Deployment configuration generator."""

from pathlib import Path


class DeploymentConfig:
    """Generate deployment configuration files for a project."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = Path(project_dir)

    def generate(self) -> None:
        """Create deployment files in project_dir."""
        self._write_dockerfile()
        self._write_docker_compose()
        self._write_systemd_service()
        self._write_env_example()

    def _write_dockerfile(self) -> None:
        path = self.project_dir / "Dockerfile"
        content = (
            "FROM python:3.12-slim\n"
            "WORKDIR /app\n"
            "COPY . /app\n"
            "CMD [\"python\", \"-m\", \"openclaw\"]\n"
        )
        path.write_text(content)

    def _write_docker_compose(self) -> None:
        path = self.project_dir / "docker-compose.yml"
        content = (
            "services:\n"
            "  openclaw:\n"
            "    build: .\n"
            "    volumes:\n"
            "      - ./data:/app/data\n"
            "    env_file:\n"
            "      - .env\n"
        )
        path.write_text(content)

    def _write_systemd_service(self) -> None:
        path = self.project_dir / "openclaw.service"
        content = (
            "[Unit]\n"
            "Description=OpenClaw Service\n"
            "After=docker.service\n"
            "Requires=docker.service\n\n"
            "[Service]\n"
            "Restart=always\n"
            "ExecStart=docker run --rm openclaw\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )
        path.write_text(content)

    def _write_env_example(self) -> None:
        path = self.project_dir / ".env.example"
        content = (
            "MATRIX_TOKEN=\n"
            "KIMI_API_KEY=\n"
            "GITHUB_TOKEN=\n"
        )
        path.write_text(content)

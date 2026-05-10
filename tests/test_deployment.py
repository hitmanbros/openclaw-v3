"""Tests for deployment config."""

import pytest
from pathlib import Path
import tempfile

from openclaw.deploy.config import DeploymentConfig


class TestDeploymentConfig:
    """Deployment configuration behavior."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_dockerfile_exists(self, temp_dir):
        """Dockerfile template is generated."""
        deploy = DeploymentConfig(project_dir=temp_dir)
        deploy.generate()
        
        assert (temp_dir / "Dockerfile").exists()

    def test_dockerfile_has_python_base(self, temp_dir):
        """Dockerfile uses Python 3.12 base image."""
        deploy = DeploymentConfig(project_dir=temp_dir)
        deploy.generate()
        
        dockerfile = (temp_dir / "Dockerfile").read_text()
        assert "python:3.12" in dockerfile

    def test_docker_compose_exists(self, temp_dir):
        """docker-compose.yml is generated."""
        deploy = DeploymentConfig(project_dir=temp_dir)
        deploy.generate()
        
        assert (temp_dir / "docker-compose.yml").exists()

    def test_docker_compose_has_service(self, temp_dir):
        """docker-compose defines openclaw service."""
        deploy = DeploymentConfig(project_dir=temp_dir)
        deploy.generate()
        
        compose = (temp_dir / "docker-compose.yml").read_text()
        assert "openclaw" in compose

    def test_systemd_service_exists(self, temp_dir):
        """Systemd service file is generated."""
        deploy = DeploymentConfig(project_dir=temp_dir)
        deploy.generate()
        
        assert (temp_dir / "openclaw.service").exists()

    def test_systemd_has_docker_run(self, temp_dir):
        """Systemd service runs docker container."""
        deploy = DeploymentConfig(project_dir=temp_dir)
        deploy.generate()
        
        service = (temp_dir / "openclaw.service").read_text()
        assert "docker run" in service

    def test_env_example_exists(self, temp_dir):
        """.env.example is generated with required vars."""
        deploy = DeploymentConfig(project_dir=temp_dir)
        deploy.generate()
        
        assert (temp_dir / ".env.example").exists()
        
        env = (temp_dir / ".env.example").read_text()
        assert "MATRIX_TOKEN" in env
        assert "KIMI_API_KEY" in env
        assert "GITHUB_TOKEN" in env

    def test_idempotent_generation(self, temp_dir):
        """Generating twice doesn't duplicate content."""
        deploy = DeploymentConfig(project_dir=temp_dir)
        deploy.generate()
        deploy.generate()
        
        dockerfile = (temp_dir / "Dockerfile").read_text()
        assert dockerfile.count("FROM") == 1

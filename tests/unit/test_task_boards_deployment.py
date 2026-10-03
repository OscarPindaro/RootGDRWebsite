from pathlib import Path

import yaml

DEPLOYMENT = Path(__file__).parents[2] / "deploy" / "task-boards.compose.yaml"


def test_task_boards_use_pinned_images_and_an_isolated_project() -> None:
    config = yaml.safe_load(DEPLOYMENT.read_text())

    assert config["name"] == "rootgdr-task-boards"
    assert {name: service["image"] for name, service in config["services"].items()} == {
        "vikunja-init": "docker.io/library/busybox:1.37.0",
        "vikunja": "docker.io/vikunja/vikunja:2.6.0",
        "kanboard": "docker.io/kanboard/kanboard:v1.2.54",
    }
    assert all("env_file" not in service for service in config["services"].values())


def test_only_the_board_interfaces_are_published_on_loopback() -> None:
    services = yaml.safe_load(DEPLOYMENT.read_text())["services"]

    assert services["vikunja"]["ports"] == ["127.0.0.1:3456:3456"]
    assert services["kanboard"]["ports"] == ["127.0.0.1:3457:80"]
    assert "ports" not in services["vikunja-init"]
    assert services["vikunja-init"]["network_mode"] == "none"


def test_each_board_has_its_own_persistent_storage() -> None:
    config = yaml.safe_load(DEPLOYMENT.read_text())
    services = config["services"]

    assert set(config["volumes"]) == {"vikunja-db", "vikunja-files", "kanboard-data"}
    assert services["vikunja"]["volumes"] == [
        "vikunja-db:/db",
        "vikunja-files:/app/vikunja/files",
    ]
    assert services["kanboard"]["volumes"] == ["kanboard-data:/var/www/app/data"]
    assert services["vikunja"]["environment"]["VIKUNJA_DATABASE_TYPE"] == "sqlite"
    assert services["vikunja"]["environment"]["VIKUNJA_SERVICE_SECRET_FILE"] == (
        "/db/.service-secret"
    )
    assert services["vikunja-init"]["profiles"] == ["setup"]
    assert "depends_on" not in services["vikunja"]


def test_local_evaluation_does_not_send_mail_or_enable_public_sharing() -> None:
    services = yaml.safe_load(DEPLOYMENT.read_text())["services"]
    environment = services["vikunja"]["environment"]

    assert environment["VIKUNJA_SERVICE_PUBLICURL"] == "http://localhost:3456/"
    assert environment["VIKUNJA_MAILER_ENABLED"] == "false"
    assert environment["VIKUNJA_SERVICE_ENABLELINKSHARING"] == "false"
    assert services["kanboard"]["environment"]["PLUGIN_INSTALLER"] == "false"

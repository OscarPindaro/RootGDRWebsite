import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.external_integrations
REPO = Path(__file__).parents[2]


@pytest.fixture(
    params=["FedoraServer", "FedoraServer (default)"], ids=["plain", "default"]
)
def firewall(tmp_path, request):
    executable = tmp_path / "firewall-cmd"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "state = Path(os.environ['TEST_FIREWALL_STATE'])\n"
        "args = sys.argv[1:]\n"
        "if args == ['--get-active-zones']:\n"
        "    print(os.environ['TEST_FIREWALL_ZONES'])\n"
        "    sys.exit(0)\n"
        "scope = 'permanent' if '--permanent' in args else 'runtime'\n"
        "if os.environ.get('TEST_FIREWALL_FAILURE') == scope:\n"
        "    sys.exit(42)\n"
        "rule = next(arg.split('=', 1)[1] for arg in args if '-rich-rule=' in arg)\n"
        "port = next(port for port in ('8001', '3458') if f'port port=\"{port}\"' in rule)\n"
        'assert rule == f\'rule family="ipv4" source address="192.168.1.0/24" port port="{port}" protocol="tcp" accept\'\n'
        "entry = scope + ':' + port\n"
        "rules = json.loads(state.read_text()) if state.exists() else []\n"
        "if any(arg.startswith('--query-rich-rule=') for arg in args):\n"
        "    sys.exit(0 if entry in rules else 1)\n"
        "assert '--zone=FedoraServer' in args\n"
        "assert any(arg.startswith('--add-rich-rule=rule family=') for arg in args)\n"
        "rules.append(entry)\n"
        "state.write_text(json.dumps(rules))\n"
    )
    executable.chmod(0o700)
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text(
        "all:\n  children:\n    rootgdr_targets:\n      hosts:\n"
        "        isolated:\n          ansible_connection: local\n"
        f"          ansible_python_interpreter: {sys.executable}\n"
    )
    state = tmp_path / "firewall-state.json"
    environment = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "TEST_FIREWALL_STATE": str(state),
        "TEST_FIREWALL_ZONES": request.param + "\n  interfaces: test0",
        "ANSIBLE_CONFIG": str(REPO / "deploy" / "ansible.cfg"),
    }
    return inventory, state, environment


def apply(firewall, *arguments):
    inventory, _, environment = firewall
    return subprocess.run(
        [
            "ansible-playbook",
            "-i",
            str(inventory),
            str(REPO / "deploy" / "server-setup.yaml"),
            "--tags",
            "firewall",
            "-e",
            "ansible_become=false",
            *arguments,
        ],
        cwd=REPO,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )


LAN_RULES = ["permanent:3458", "permanent:8001", "runtime:3458", "runtime:8001"]


@pytest.mark.parametrize(
    "existing", [[], ["runtime:8001"], ["permanent:3458"], LAN_RULES]
)
def test_server_setup_check_mode_never_changes_firewall(firewall, existing):
    firewall[1].write_text(json.dumps(existing))
    before = firewall[1].read_bytes()
    result = apply(firewall, "--check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert ("changed=0" if len(existing) == 4 else "changed=1") in result.stdout
    for entry in LAN_RULES:
        scope, port = entry.split(":")
        assert (f"Would enable the {scope} LAN rule for {port}" in result.stdout) == (
            entry not in existing
        )
    assert firewall[1].read_bytes() == before


@pytest.mark.parametrize(
    "existing", [[], ["runtime:8001"], ["permanent:3458"], LAN_RULES]
)
def test_server_setup_adds_only_missing_rules_and_reapply_is_unchanged(
    firewall, existing
):
    firewall[1].write_text(json.dumps(existing))
    first = apply(firewall)
    assert first.returncode == 0, first.stdout + first.stderr
    assert sorted(json.loads(firewall[1].read_text())) == LAN_RULES
    second = apply(firewall)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "changed=0" in second.stdout
    assert len(json.loads(firewall[1].read_text())) == 4


@pytest.mark.parametrize("failure", ["runtime", "permanent"])
def test_server_setup_query_errors_block_all_mutations(firewall, failure):
    firewall[2]["TEST_FIREWALL_FAILURE"] = failure
    result = apply(firewall)
    assert result.returncode != 0
    assert not firewall[1].exists()


def test_server_setup_refuses_inactive_zone(firewall):
    result = apply(firewall, "-e", "rootgdr_firewall_zone=public")
    assert result.returncode != 0
    assert "not active" in result.stdout
    assert not firewall[1].exists()


@pytest.mark.parametrize(
    "inventory",
    [
        "all:\n  children: {}\n",
        "all:\n  children:\n    rootgdr_targets:\n      hosts:\n        first:\n          ansible_connection: local\n        second:\n          ansible_connection: local\n",
    ],
)
def test_server_setup_refuses_empty_or_ambiguous_inventory(firewall, inventory):
    firewall[0].write_text(inventory)
    result = apply(firewall)
    assert result.returncode != 0
    assert "Explicitly inventory exactly one" in result.stdout
    assert not firewall[1].exists()

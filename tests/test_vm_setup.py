import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def write_executable(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class VMSetupTests(unittest.TestCase):
    def test_shared_system_is_an_exact_clean_submodule_pin(self):
        index = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-s", "agent-system"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.split()
        self.assertEqual(index[0], "160000")
        expected = index[1]
        actual = subprocess.run(
            ["git", "-C", str(ROOT / "agent-system"), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        self.assertEqual(actual, expected)
        self.assertEqual(
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(ROOT),
                    "config",
                    "-f",
                    ".gitmodules",
                    "--get",
                    "submodule.agent-system.url",
                ],
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip(),
            "https://github.com/hermes-os/coding-agent-system.git",
        )
        self.assertFalse(
            subprocess.run(
                ["git", "-C", str(ROOT / "agent-system"), "status", "--porcelain"],
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
        )

    def test_vm_launchers_apply_interactive_defaults_only(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            log = home / "calls.log"
            stub = home / "native-agent"
            write_executable(
                stub,
                '#!/usr/bin/env bash\nprintf "%s\\n" "$*" >>"$VM_TEST_LOG"\n',
            )
            env = {
                **os.environ,
                "HOME": str(home),
                "VM_TEST_LOG": str(log),
                "AGENT_CLAUDE_BIN": str(stub),
                "AGENT_CODEX_BIN": str(stub),
                "AGENT_CODEX_IGNORE_DESKTOP_APP_SERVER": "1",
            }
            commands = (
                (ROOT / "host" / "bin" / "agent-claude", "fix it"),
                (ROOT / "host" / "bin" / "agent-claude", "doctor"),
                (ROOT / "host" / "bin" / "agent-codex", "fix it"),
                (ROOT / "host" / "bin" / "agent-codex", "doctor"),
            )
            for executable, argument in commands:
                subprocess.run([str(executable), argument], env=env, check=True)

            self.assertEqual(
                log.read_text(encoding="utf-8").splitlines(),
                [
                    "--remote-control --permission-mode bypassPermissions fix it",
                    "doctor",
                    "remote-control start --json",
                    "--dangerously-bypass-approvals-and-sandbox --dangerously-bypass-hook-trust --search fix it",
                    "doctor",
                ],
            )

    def test_shared_installer_accepts_the_vm_owned_adapter(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            env = {**os.environ, "HOME": str(home)}
            install = subprocess.run(
                [
                    str(ROOT / "agent-system" / "install.sh"),
                    "--coordination-repo",
                    str(ROOT),
                    "--host-integration",
                    str(ROOT / "host"),
                ],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(install.returncode, 0, install.stderr)
            config = json.loads((home / ".agents" / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["coordinationRepo"], str(ROOT))
            self.assertEqual(config["hostIntegrationRoot"], str(ROOT / "host"))
            self.assertEqual(
                (home / ".agents" / "bin" / "agent-codex").resolve(),
                ROOT / "host" / "bin" / "agent-codex",
            )
            doctor = subprocess.run(
                [
                    str(ROOT / "agent-system" / "bin" / "agent-system-doctor"),
                    "--home",
                    str(home),
                    "--repo",
                    str(ROOT),
                ],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(doctor.returncode, 0, doctor.stderr)

    def test_bootstrap_pins_shared_system_and_keeps_restores_independent(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture = base / "vm"
            fixture.mkdir()
            log = base / "calls.log"
            stub_bin = base / "bin"
            write_executable(
                stub_bin / "git",
                "#!/usr/bin/env bash\n"
                'printf "git %s\\n" "$*" >>"$VM_TEST_LOG"\n'
                'case "$*" in\n'
                '  *"ls-files -s agent-system") printf "160000 %040d 0 agent-system\\n" 0 ;;\n'
                '  *"rev-parse HEAD") printf "%040d\\n" "${VM_PIN_MISMATCH:-0}" ;;\n'
                "esac\n",
            )
            scripts = (
                ("agent-system/install.sh", "install"),
                ("claude-code/restore-claude-credentials.sh", "claude-restore"),
                ("codex/install-standalone.sh", "codex-install"),
                ("codex/ensure-codex-config.sh", "codex-config"),
                ("codex/restore-codex-credentials.sh", "codex-restore"),
                ("codex/start-remote-control.sh", "codex-remote"),
            )
            for relative, label in scripts:
                write_executable(
                    fixture / relative,
                    f'#!/usr/bin/env bash\nprintf "{label} %s\\n" "$*" >>"$VM_TEST_LOG"\n',
                )
            (fixture / "host").mkdir()

            env = {
                **os.environ,
                "HOME": str(base / "home"),
                "PATH": f"{stub_bin}:/usr/bin:/bin",
                "VM_TEST_LOG": str(log),
                "CODING_AGENT_VM_SETUP": str(fixture),
                "CLAUDE_PROJECT_DIR": str(base / "workspace"),
            }
            for key in (
                "SHARED_REPO_TOKEN",
                "CLAUDE_CODE_CREDENTIALS_B64",
                "CODEX_AUTH_JSON_B64",
            ):
                env.pop(key, None)
            result = subprocess.run(
                [str(ROOT / "bootstrap.sh")],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                log.read_text(encoding="utf-8").splitlines(),
                [
                    f"git -C {fixture} submodule sync --recursive",
                    f"git -C {fixture} submodule update --init --recursive",
                    f"git -C {fixture} ls-files -s agent-system",
                    f"git -C {fixture / 'agent-system'} rev-parse HEAD",
                    f"git -C {fixture / 'agent-system'} status --porcelain",
                    f"install --coordination-repo {fixture} --host-integration {fixture / 'host'}",
                    "claude-restore ",
                    "codex-install ",
                    "codex-config ",
                    "codex-restore ",
                    "codex-remote ",
                ],
            )
            self.assertNotIn(
                "AGENT_SYSTEM_PRUNE_LEGACY",
                (ROOT / "bootstrap.sh").read_text(encoding="utf-8"),
            )

            log.write_text("", encoding="utf-8")
            env["VM_PIN_MISMATCH"] = "1"
            mismatched = subprocess.run(
                [str(ROOT / "bootstrap.sh")],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(mismatched.returncode, 0, mismatched.stderr)
            self.assertIn("not the exact clean VM pin", mismatched.stderr)
            self.assertEqual(
                log.read_text(encoding="utf-8").splitlines(),
                [
                    f"git -C {fixture} submodule sync --recursive",
                    f"git -C {fixture} submodule update --init --recursive",
                    f"git -C {fixture} ls-files -s agent-system",
                    f"git -C {fixture / 'agent-system'} rev-parse HEAD",
                    f"git -C {fixture / 'agent-system'} status --porcelain",
                    "claude-restore ",
                    "codex-install ",
                    "codex-config ",
                    "codex-restore ",
                    "codex-remote ",
                ],
            )


if __name__ == "__main__":
    unittest.main()

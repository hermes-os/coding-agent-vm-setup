import json
import os
import runpy
import sqlite3
import signal
import stat
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "host" / "bin" / "agent-hermes-worker"
STAGED_HERMES = Path(
    "/opt/agent-worker-hermes/releases/ee5b5ec21e576ccf9b941f9ff71330418415a5cb/source/.venv/bin/hermes"
)
STAGED_PYTHON = STAGED_HERMES.parent / "python"


FIXTURE_SOURCE = textwrap.dedent(
    '''\
    #!/usr/bin/env python3
    import json
    import os
    import sqlite3
    import signal
    import sys
    import time
    from pathlib import Path

    CONTROL = __FIXTURE_CONTROL__
    args = sys.argv[1:]
    home = Path(os.environ["HERMES_HOME"])
    record_path = home / ".fixture-record.json"
    behavior = CONTROL.get("behavior", "success")
    record_path.write_text(json.dumps({
        "argv": args,
        "stdin": sys.stdin.read() if behavior != "block-stdin" and CONTROL.get("read_input", True) else "",
        "hermes_home": os.environ.get("HERMES_HOME", ""),
        "access": os.environ.get("AGENT_ACCESS_MODE", ""),
        "managed": os.environ.get("AGENT_WORKER_MANAGED", ""),
        "model": os.environ.get("HERMES_MODEL", ""),
        "inference_model": os.environ.get("HERMES_INFERENCE_MODEL", ""),
        "inference_provider": os.environ.get("HERMES_INFERENCE_PROVIDER", ""),
        "ambient_surface": {
            key: os.environ.get(key, "")
            for key in (
                "HERMES_MAX_ITERATIONS",
                "HERMES_MAX_TOKENS",
                "HERMES_EPHEMERAL_SYSTEM_PROMPT",
                "HERMES_PREFILL_MESSAGES_FILE",
                "HERMES_ENVIRONMENT_HINT",
                "HERMES_FUTURE_BEHAVIOR_OVERRIDE",
                "HERMES_BUNDLED_SKILLS",
                "HERMES_BUNDLED_PLUGINS",
                "HERMES_ENABLE_PROJECT_PLUGINS",
                "HERMES_OPTIONAL_SKILLS",
                "HERMES_OPTIONAL_MCPS",
                "HERMES_TUI_SKILLS",
                "HERMES_TUI_TOOLSETS",
            )
        },
        "retained_surface": {
            key: os.environ.get(key, "")
            for key in (
                "OPENAI_API_KEY",
                "OPENAI_BASE_URL",
                "NOUS_API_KEY",
                "NOUS_BASE_URL",
                "QWEN_API_KEY",
                "DEEPINFRA_API_KEY",
                "DEEPINFRA_BASE_URL",
                "MODEL_API_KEY",
                "TERMINAL_ENV",
                "HERMES_SUPERVISED_CHILD",
                "HERMES_YOLO_MODE",
            )
        },
    }), encoding="utf-8")

    (home / "fixture-state.txt").write_text(CONTROL.get("state", "state"), encoding="utf-8")
    session_id = CONTROL.get("session", "20260905_120000_fixture")

    def seed_session(native_id, *, parent=None, cwd=None, yolo=False, end_reason=None, message=True):
        db_path = home / "state.db"
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                parent_session_id TEXT,
                cwd TEXT,
                model_config TEXT,
                source TEXT,
                started_at REAL,
                ended_at REAL,
                end_reason TEXT,
                last_activity_at REAL,
                session_key TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp REAL NOT NULL
            );
        """)
        now = time.time()
        conn.execute(
            "INSERT OR REPLACE INTO sessions "
            "(id,parent_session_id,cwd,model_config,source,started_at,ended_at,end_reason,last_activity_at,session_key) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (native_id, parent, cwd or os.getcwd(), json.dumps({"yolo_mode": yolo}), "cli", now,
             now if end_reason else None, end_reason, now, ""),
        )
        if message:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (native_id,))
            conn.execute("INSERT INTO messages(session_id,timestamp) VALUES (?,?)", (native_id, now))
        conn.commit()
        conn.close()
        db_path.chmod(0o600)

    if behavior == "resume-rotate":
        parent_id = CONTROL["parent_session"]
        seed_session(parent_id, cwd=os.getcwd(), end_reason="compression", message=False)
        seed_session(session_id, parent=parent_id, cwd=os.getcwd(), message=True)
    elif behavior not in {"block-stdin"}:
        seed_session(session_id, cwd=os.getcwd(), yolo=CONTROL.get("yolo", False))

    if behavior == "sleep":
        ready = Path(CONTROL["pid_file"])
        temporary = ready.with_suffix(ready.suffix + ".tmp")
        temporary.write_text(str(os.getpid()), encoding="ascii")
        os.replace(temporary, ready)
        print(f"session_id: {session_id}", file=sys.stderr, flush=True)
        time.sleep(60)
    elif behavior == "block-stdin":
        ready = Path(CONTROL["pid_file"])
        temporary = ready.with_suffix(ready.suffix + ".tmp")
        temporary.write_text(str(os.getpid()), encoding="ascii")
        os.replace(temporary, ready)
        print(f"session_id: {session_id}", file=sys.stderr, flush=True)
        time.sleep(60)
    elif behavior == "fork-holder":
        holder_pid = os.fork()
        if holder_pid == 0:
            time.sleep(60)
            os._exit(0)
        ready = Path(CONTROL["pid_file"])
        temporary = ready.with_suffix(ready.suffix + ".tmp")
        temporary.write_text(str(holder_pid), encoding="ascii")
        os.replace(temporary, ready)
        print(f"session_id: {session_id}", file=sys.stderr, flush=True)
        print(CONTROL.get("result", "fixture result"), flush=True)
        os._exit(0)
    elif behavior == "fork-holder-error":
        holder_pid = os.fork()
        if holder_pid == 0:
            time.sleep(60)
            os._exit(0)
        ready = Path(CONTROL["pid_file"])
        temporary = ready.with_suffix(ready.suffix + ".tmp")
        temporary.write_text(str(holder_pid), encoding="ascii")
        os.replace(temporary, ready)
        print(f"session_id: {session_id}", file=sys.stderr, flush=True)
        raise SystemExit(17)
    elif behavior == "large-unterminated":
        print(f"session_id: {session_id}", file=sys.stderr, flush=True)
        os.write(sys.stdout.fileno(), b"x" * (8 * 1024 * 1024 + 1))
        os._exit(0)
    elif behavior == "large-diagnostic":
        os.write(sys.stderr.fileno(), b"d" * (256 * 1024 + 1))
        print(f"session_id: {session_id}", file=sys.stderr, flush=True)
        print("fixture result")
        os._exit(0)
    elif behavior == "large-diagnostic-ignore-term":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        ready = Path(CONTROL["pid_file"])
        temporary = ready.with_suffix(ready.suffix + ".tmp")
        temporary.write_text(str(os.getpid()), encoding="ascii")
        os.replace(temporary, ready)
        os.write(sys.stderr.fileno(), b"d" * (256 * 1024 + 1))
        time.sleep(60)
    elif behavior == "provider-error":
        print(f"provider secret: {CONTROL.get('secret', 'fixture-secret')}", file=sys.stderr)
        print(f"session_id: {session_id}", file=sys.stderr)
        raise SystemExit(17)
    elif behavior == "no-session":
        print("fixture completed without native identity", file=sys.stderr)
        print("fixture result")
    elif behavior == "empty":
        print(f"session_id: {session_id}", file=sys.stderr)
    else:
        print(f"session_id: {session_id}", file=sys.stderr)
        print(CONTROL.get("result", "fixture result"))
    ''')

HARNESS_SOURCE = textwrap.dedent(
    '''\
    import importlib.machinery
    import importlib.util
    import os

    loader = importlib.machinery.SourceFileLoader("hermes_worker_bridge", __BRIDGE__)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    bridge = importlib.util.module_from_spec(spec)
    loader.exec_module(bridge)
    fixture = os.environ.pop("HERMES_TEST_BINARY")
    bridge.resolve_hermes_runtime = lambda: (fixture,)
    raise SystemExit(bridge.main())
    ''')


class HermesWorkerBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.work = Path(self.tempdir.name)
        self.fixture = self.make_fixture({})
        self.harness = self.work / "bridge-harness.py"
        self.harness.write_text(
            HARNESS_SOURCE.replace("__BRIDGE__", repr(str(BRIDGE))),
            encoding="utf-8",
        )

    def make_fixture(self, control):
        fixture = self.work / f"hermes-fixture-{uuid.uuid4().hex}"
        fixture.write_text(
            FIXTURE_SOURCE.replace("__FIXTURE_CONTROL__", repr(control)),
            encoding="utf-8",
        )
        fixture.chmod(fixture.stat().st_mode | stat.S_IXUSR)
        return fixture

    def make_environment(self, *, path=None):
        home = self.work / "test-user-home"
        home.mkdir(exist_ok=True)
        environment = {
            key: os.environ[key]
            for key in ("LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ")
            if key in os.environ
        }
        environment.update(
            {
                "HOME": str(home),
                "PATH": path or os.environ.get("PATH", "/usr/bin:/bin"),
            }
        )
        return environment

    def make_native_home(self, *, session_id, cwd=None, binding_cwd=None, yolo=False, broker_session_id="11111111-1111-4111-8111-111111111111", access="write"):
        self.assertTrue(STAGED_PYTHON.is_file(), "staged Hermes interpreter is unavailable")
        seed_home = self.work / "native-seed-home"
        seed_home.mkdir(exist_ok=True)
        home = self.work / f"native-runtime-{uuid.uuid4().hex}"
        home.mkdir(mode=0o700)
        (home / "config.yaml").write_bytes((ROOT / "host" / "hermes-worker" / "config.yaml").read_bytes())
        (home / "config.yaml").chmod(0o400)
        (home / ".no-bundled-skills").write_bytes(b"")
        (home / ".no-bundled-skills").chmod(0o400)
        script = textwrap.dedent(
            """
            import os, sys, time
            from pathlib import Path
            from hermes_state import SessionDB
            home, native_id, cwd, yolo = map(str, sys.argv[1:5])
            db = SessionDB(db_path=Path(home) / "state.db")
            db.create_session(native_id, "cli", model="fixture/model-v1",
                              model_config={"yolo_mode": yolo == "1"}, cwd=cwd)
            db.append_message(native_id, "user", "seed")
            db.close()
            (Path(home) / "state.db").chmod(0o600)
            """
        )
        subprocess.run(
            [str(STAGED_PYTHON), "-I", "-c", script, str(home), session_id, cwd or str(Path.cwd()), "1" if yolo else "0"],
            check=True,
            capture_output=True,
            text=True,
            env={
                "HOME": str(seed_home),
                "HERMES_HOME": str(home),
                "PATH": "/usr/bin:/bin",
            },
        )
        binding = {
            "version": 1,
            "sessions": {
                session_id: {
                    "broker_session_id": broker_session_id,
                    "access": access,
                    "cwd": str(Path(binding_cwd or cwd or Path.cwd()).resolve()),
                }
            },
        }
        (home / "bridge-state.json").write_text(json.dumps(binding), encoding="utf-8")
        (home / "bridge-state.json").chmod(0o600)
        return home

    def make_native_compression_home(self, *, parent_id, child_id):
        seed_home = self.work / "native-seed-home"
        seed_home.mkdir(exist_ok=True)
        home = self.work / f"native-lineage-{uuid.uuid4().hex}"
        home.mkdir(mode=0o700)
        (home / "config.yaml").write_bytes((ROOT / "host" / "hermes-worker" / "config.yaml").read_bytes())
        (home / "config.yaml").chmod(0o400)
        (home / ".no-bundled-skills").write_bytes(b"")
        (home / ".no-bundled-skills").chmod(0o400)
        script = textwrap.dedent(
            """
            import sys
            from pathlib import Path
            from hermes_state import SessionDB
            home, parent_id, child_id, cwd = sys.argv[1:]
            db = SessionDB(db_path=Path(home) / "state.db")
            db.create_session(parent_id, "cli", model="fixture/model-v1", model_config={}, cwd=cwd)
            db.end_session(parent_id, "compression")
            db.create_session(child_id, "cli", model="fixture/model-v1", model_config={}, cwd=cwd,
                              parent_session_id=parent_id)
            db.append_message(child_id, "user", "seed")
            db.close()
            (Path(home) / "state.db").chmod(0o600)
            """
        )
        subprocess.run(
            [str(STAGED_PYTHON), "-I", "-c", script, str(home), parent_id, child_id, str(Path.cwd())],
            check=True,
            capture_output=True,
            text=True,
            env={
                "HOME": str(seed_home),
                "HERMES_HOME": str(home),
                "PATH": "/usr/bin:/bin",
            },
        )
        binding = {
            "version": 1,
            "sessions": {
                parent_id: {
                    "broker_session_id": "11111111-1111-4111-8111-111111111111",
                    "access": "write",
                    "cwd": str(Path.cwd().resolve()),
                }
            },
        }
        (home / "bridge-state.json").write_text(json.dumps(binding), encoding="utf-8")
        (home / "bridge-state.json").chmod(0o600)
        return home

    def tearDown(self):
        self.tempdir.cleanup()

    def run_bridge(
        self,
        *,
        access="write",
        runtime_home=None,
        session_args=("--fresh-session",),
        behavior="success",
        session="20260905_120000_fixture",
        task="inspect the assigned repository",
        extra_env=None,
        provider="openai-api",
        model="fixture/model-v1",
        effort="high",
        timeout=10,
        native=False,
    ):
        if runtime_home is None:
            runtime_home = self.work / f"runtime-{uuid.uuid4().hex}"
        extra_env = dict(extra_env or {})
        record = runtime_home / ".fixture-record.json"
        record.unlink(missing_ok=True)
        if not native:
            configured_binary = str(
                self.make_fixture(
                    {
                        "behavior": behavior,
                        "session": session,
                        "parent_session": extra_env.get("FIXTURE_PARENT_SESSION"),
                        "pid_file": extra_env.get("FIXTURE_PID_FILE"),
                        "secret": extra_env.get("FIXTURE_SECRET"),
                        "result": extra_env.get("FIXTURE_RESULT", "fixture result"),
                        "state": extra_env.get("FIXTURE_STATE", "state"),
                    }
                )
            )
        env = self.make_environment(path="/usr/bin:/bin" if native else None)
        env.update(
            {
                "AGENT_WORKER_MANAGED": "1",
                "AGENT_ACCESS_MODE": access,
            }
        )
        if not native:
            env["HERMES_TEST_BINARY"] = configured_binary
        env.update({key: value for key, value in extra_env.items() if not key.startswith("FIXTURE_")})
        command = [
            *([str(BRIDGE)] if native else [sys.executable, "-I", str(self.harness)]),
            "--provider",
            provider,
            "--model",
            model,
            "--effort",
            effort,
            "--access",
            access,
            "--runtime-home",
            str(runtime_home),
            "--broker-session-id",
            "11111111-1111-4111-8111-111111111111",
            *session_args,
        ]
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(input=task, timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate(timeout=3)
            raise
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        fixture_record = json.loads(record.read_text(encoding="utf-8")) if record.exists() else None
        return result, events, fixture_record, runtime_home

    def read_ready_pid(self, path, *, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                value = path.read_text(encoding="ascii").strip()
            except (FileNotFoundError, UnicodeDecodeError):
                value = ""
            if value.isdigit() and int(value) > 0:
                return int(value)
            time.sleep(0.01)
        self.fail("fixture did not publish a validated PID")

    def assert_pid_stopped(self, pid, *, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.01)
        self.fail(f"process {pid} remained alive")

    def test_resume_rejects_saved_cwd_mismatch_before_native_child(self):
        assigned = self.work / "assigned"
        other = self.work / "other"
        assigned.mkdir()
        other.mkdir()
        home = self.make_native_home(session_id="native-cwd", cwd=str(other), binding_cwd=str(assigned))
        env = {
            "AGENT_WORKER_MANAGED": "1",
            "AGENT_ACCESS_MODE": "write",
            "HOME": str(self.work / "native-cwd-home"),
            "OPENAI_API_KEY": "",
            "PATH": "/usr/bin:/bin",
        }
        Path(env["HOME"]).mkdir()
        command = [
            str(BRIDGE), "--provider", "openai-api", "--model", "model/v1",
            "--effort", "medium", "--access", "write", "--runtime-home", str(home),
            "--broker-session-id", "11111111-1111-4111-8111-111111111111", "--resume-session", "native-cwd",
        ]
        result = subprocess.run(command, input="probe", text=True, capture_output=True, env=env, cwd=assigned)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[-1]["code"], "resume_cwd_mismatch")
        self.assertNotIn("started", [event["event"] for event in events])

    def test_read_resume_rejects_persisted_native_yolo(self):
        home = self.make_native_home(session_id="native-yolo", yolo=True, access="read")
        result, events, record, _ = self.run_bridge(
            access="read",
            runtime_home=home,
            session_args=("--resume-session", "native-yolo"),
            extra_env={"OPENAI_API_KEY": ""},
            native=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[-1]["code"], "resume_persisted_yolo")
        self.assertIsNone(record)

    def test_resume_rejects_missing_native_session_before_child(self):
        home = self.make_native_home(session_id="native-present")
        binding = json.loads((home / "bridge-state.json").read_text(encoding="utf-8"))
        binding["sessions"]["native-missing"] = binding["sessions"]["native-present"]
        (home / "bridge-state.json").write_text(json.dumps(binding), encoding="utf-8")
        result, events, record, _ = self.run_bridge(
            runtime_home=home,
            session_args=("--resume-session", "native-missing"),
            extra_env={"OPENAI_API_KEY": ""},
            native=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[-1]["code"], "resume_session_missing")
        self.assertIsNone(record)

    def test_same_access_resume_passes_native_preflight_before_provider_failure(self):
        home = self.make_native_home(session_id="native-same", access="write")
        result, events, record, _ = self.run_bridge(
            runtime_home=home,
            session_args=("--resume-session", "native-same"),
            extra_env={"OPENAI_API_KEY": ""},
            native=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[0]["event"], "started")
        self.assertEqual(events[-1]["code"], "provider_failed")
        self.assertIsNone(record)

    @unittest.skipUnless(STAGED_HERMES.is_file(), "staged Hermes runtime is unavailable")
    def test_staged_native_compression_descendant_is_the_effective_resume_target(self):
        home = self.make_native_compression_home(parent_id="native-parent", child_id="native-child")
        result, events, record, _ = self.run_bridge(
            runtime_home=home,
            session_args=("--resume-session", "native-parent"),
            extra_env={"OPENAI_API_KEY": ""},
            native=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[0]["event"], "started")
        self.assertEqual(events[0]["effective_resume_native_session_id"], "native-child")
        self.assertEqual(events[-1]["code"], "provider_failed")
        self.assertIsNone(record)

    @unittest.skipUnless(STAGED_HERMES.is_file(), "staged Hermes runtime is unavailable")
    def test_staged_runtime_inventory_is_lean_and_ambient_overrides_are_ignored(self):
        ambient_skills = self.work / "ambient-skills"
        ambient_skills.mkdir()
        (ambient_skills / "ambient").mkdir()
        (ambient_skills / "ambient" / "SKILL.md").write_text("ambient", encoding="utf-8")
        ambient_plugins = self.work / "ambient-plugins"
        ambient_plugins.mkdir()
        result, _, _, runtime_home = self.run_bridge(
            provider="openai-api",
            native=True,
            extra_env={
                "OPENAI_API_KEY": "",
                "HERMES_BUNDLED_SKILLS": str(ambient_skills),
                "HERMES_BUNDLED_PLUGINS": str(ambient_plugins),
                "HERMES_ENABLE_PROJECT_PLUGINS": "1",
                "HERMES_OPTIONAL_SKILLS": str(ambient_skills),
                "HERMES_OPTIONAL_MCPS": str(ambient_plugins),
            },
        )
        self.assertNotEqual(result.returncode, 0)
        skill_files = sorted(
            path.relative_to(runtime_home / "skills").as_posix()
            for path in (runtime_home / "skills").rglob("SKILL.md")
        )
        self.assertEqual(skill_files, ["autonomous-ai-agents/hermes-agent/SKILL.md"])
        inventory_script = textwrap.dedent(
            """
            import json
            from agent.skill_utils import get_external_skills_dirs
            from hermes_cli.config import load_config_readonly
            from toolsets import resolve_toolset
            names = ("file", "search", "terminal", "skills")
            cfg = load_config_readonly()
            tools = sorted({tool for name in names for tool in resolve_toolset(name)})
            print(json.dumps({
                "toolsets": cfg.get("toolsets"),
                "external_dirs": [str(path) for path in get_external_skills_dirs()],
                "tools": tools,
            }))
            """
        )
        inventory = subprocess.run(
            [str(STAGED_PYTHON), "-I", "-c", inventory_script],
            cwd=STAGED_HERMES.parents[2],
            env={
                "HOME": str(self.work / "inventory-home"),
                "HERMES_HOME": str(runtime_home),
                "PATH": "/usr/bin:/bin",
            },
            check=True,
            capture_output=True,
            text=True,
        )
        surface = json.loads(inventory.stdout)
        self.assertEqual(surface["toolsets"], ["file", "search", "terminal", "skills"])
        self.assertEqual(surface["external_dirs"], [])
        self.assertNotIn("cronjob_manage", surface["tools"])
        self.assertNotIn("delegate_task", surface["tools"])

    @unittest.skipUnless(STAGED_HERMES.is_file(), "staged Hermes runtime is unavailable")
    def test_staged_bootstrap_ignores_sticky_active_profile(self):
        synthetic_home = self.work / "synthetic-home"
        profile_root = synthetic_home / ".hermes"
        profile_home = profile_root / "profiles" / "probe"
        profile_home.mkdir(parents=True, mode=0o700)
        profile_root.chmod(0o700)
        (profile_root / "active_profile").write_text("probe\n", encoding="utf-8")
        (profile_root / "active_profile").chmod(0o600)
        (profile_home / "config.yaml").write_bytes((ROOT / "host" / "hermes-worker" / "config.yaml").read_bytes())
        (profile_home / "config.yaml").chmod(0o400)
        result, _, _, runtime_home = self.run_bridge(
            runtime_home=profile_root / "worker",
            provider="openai-api",
            extra_env={"HOME": str(synthetic_home), "OPENAI_API_KEY": ""},
            native=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((runtime_home / "skills" / "autonomous-ai-agents" / "hermes-agent" / "SKILL.md").is_file())
        self.assertFalse((profile_home / "skills").exists())

    def test_external_process_and_unreviewed_providers_are_rejected_before_child(self):
        marker = self.work / "external-process-launched"
        external_bin = self.work / "bin"
        external_bin.mkdir()
        external_cli = external_bin / "copilot"
        external_cli.write_text(
            f"#!/usr/bin/env bash\ntouch {str(marker)!r}\n",
            encoding="utf-8",
        )
        external_cli.chmod(0o700)
        for provider in (
            "copilot-acp",
            "github-copilot-acp",
            "copilot-acp-agent",
            "unreviewed-process-provider",
        ):
            with self.subTest(provider=provider):
                result, events, record, _ = self.run_bridge(
                    provider=provider,
                    native=True,
                    extra_env={
                        "HOME": str(self.work / "external-home"),
                        "HERMES_COPILOT_ACP_COMMAND": str(external_cli),
                        "COPILOT_CLI_PATH": str(external_cli),
                        "PATH": f"{external_bin}:{os.environ['PATH']}",
                    },
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(events[-1]["code"], "provider_transport_denied")
                self.assertIsNone(record)
                self.assertFalse(marker.exists())

    @unittest.skipUnless(STAGED_HERMES.is_file(), "staged Hermes runtime is unavailable")
    def test_reviewed_provider_admission_matches_staged_source_classification(self):
        synthetic_home = self.work / "provider-inventory-home"
        synthetic_home.mkdir()
        inventory_source = textwrap.dedent(
            """
            import json
            import hermes_cli.auth as auth
            from providers import list_providers

            profiles = {profile.name: profile for profile in list_providers()}
            wire = {}
            for name, profile in profiles.items():
                wire[name] = profile.auth_type
                for alias in profile.aliases:
                    wire[alias] = profile.auth_type
            for alias, canonical in auth._PROVIDER_ALIASES.items():
                profile = profiles.get(canonical)
                config = auth.PROVIDER_REGISTRY.get(canonical)
                wire[alias] = profile.auth_type if profile else config.auth_type if config else None
            for name, config in auth.PROVIDER_REGISTRY.items():
                wire.setdefault(name, config.auth_type)
            custom_clients = sorted(
                name for name, profile in profiles.items()
                if type(profile).create_client.__module__ != "providers.base"
            )
            print(json.dumps({
                "direct": sorted(name for name, auth_type in wire.items()
                                 if auth_type and auth_type != "external_process"),
                "external": sorted(name for name, auth_type in wire.items()
                                   if auth_type == "external_process"),
                "unknown": sorted(name for name, auth_type in wire.items() if auth_type is None),
                "custom_clients": custom_clients,
            }))
            """
        )
        inventory = subprocess.run(
            [str(STAGED_PYTHON), "-I", "-c", inventory_source],
            cwd=STAGED_HERMES.parents[2],
            env={
                "HOME": str(synthetic_home),
                "HERMES_HOME": str(synthetic_home / "runtime"),
                "PATH": "/usr/bin:/bin",
            },
            check=True,
            capture_output=True,
            text=True,
        )
        staged = json.loads(inventory.stdout)
        bridge = runpy.run_path(str(BRIDGE), run_name="hermes_worker_contract")
        self.assertEqual(set(staged["direct"]), bridge["TRUSTED_DIRECT_PROVIDERS"])
        self.assertEqual(set(staged["external"]), bridge["EXTERNAL_PROCESS_PROVIDERS"])
        self.assertEqual(staged["unknown"], [])
        self.assertEqual(staged["custom_clients"], ["copilot-acp"])

    def test_supported_direct_alias_preserves_arbitrary_model_selection(self):
        result, events, record, _ = self.run_bridge(
            provider="or",
            model="vendor/arbitrary-model:v2",
            effort="ultra",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events[0]["provider"], "or")
        self.assertEqual(events[0]["model"], "vendor/arbitrary-model:v2")
        self.assertEqual(record["argv"][record["argv"].index("--provider") + 1], "or")
        self.assertEqual(record["argv"][record["argv"].index("--model") + 1], "vendor/arbitrary-model:v2")
        self.assertEqual(record["argv"][record["argv"].index("--reasoning") + 1], "ultra")

    def test_worker_state_provider_plugin_is_rejected_before_native_import(self):
        runtime_home = self.work / "runtime-provider-plugin"
        fresh, _, _, _ = self.run_bridge(runtime_home=runtime_home, session="native-plugin-root")
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        marker = self.work / "provider-plugin-imported"
        provider_dir = runtime_home / "plugins" / "model-providers" / "openai-api"
        provider_dir.mkdir(parents=True)
        (provider_dir / "__init__.py").write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('imported', encoding='utf-8')\n",
            encoding="utf-8",
        )
        result, events, record, _ = self.run_bridge(
            runtime_home=runtime_home,
            session_args=("--resume-session", "native-plugin-root"),
            native=True,
            extra_env={"OPENAI_API_KEY": ""},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[-1]["code"], "unsafe_runtime_home")
        self.assertIsNone(record)
        self.assertFalse(marker.exists())

    @unittest.skipUnless(STAGED_HERMES.is_file(), "staged Hermes runtime is unavailable")
    def test_production_path_ignores_ambient_runtime_injection(self):
        synthetic_home = self.work / "synthetic-runtime-home"
        synthetic_home.mkdir()
        python_injection = self.work / "python-injection"
        python_injection.mkdir()
        python_marker = self.work / "ambient-python-imported"
        (python_injection / "sitecustomize.py").write_text(
            f"from pathlib import Path\nPath({str(python_marker)!r}).touch()\n",
            encoding="utf-8",
        )
        result, events, record, _ = self.run_bridge(
            provider="openai-api",
            model="arbitrary/model-selection",
            extra_env={
                "AGENT_HERMES_BIN": str(self.fixture),
                "HOME": str(synthetic_home),
                "OPENAI_API_KEY": "",
                "PYTHONPATH": str(python_injection),
            },
            native=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[-1]["code"], "provider_failed")
        self.assertIsNone(record)
        self.assertFalse(python_marker.exists())

    def test_runtime_tree_rejects_worker_writable_import_code(self):
        runtime_tree = self.work / "runtime-tree"
        runtime_tree.mkdir()
        provider = runtime_tree / "provider.py"
        provider.write_text("raise SystemExit\n", encoding="utf-8")
        provider.chmod(0o666)
        bridge = runpy.run_path(str(BRIDGE), run_name="hermes_worker_contract")
        with self.assertRaises(bridge["BridgeError"]) as raised:
            bridge["_verify_deployment_tree"](
                runtime_tree,
                allowed_symlink_roots=(runtime_tree,),
            )
        self.assertEqual(raised.exception.code, "runtime_untrusted")

    def test_oversized_unterminated_diagnostic_is_rejected(self):
        result, events, _, _ = self.run_bridge(behavior="large-diagnostic", timeout=6)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[-1]["code"], "diagnostic_too_large")

    def test_oversized_diagnostic_terminates_term_ignoring_child(self):
        pid_file = self.work / "diagnostic-holder.pid"
        runtime_home = self.work / "runtime-diagnostic-holder"
        fixture = self.make_fixture(
            {"behavior": "large-diagnostic-ignore-term", "session": "20260905_diagnostic_holder", "pid_file": str(pid_file)}
        )
        process = subprocess.Popen(
            [
                sys.executable, "-I", str(self.harness), "--provider", "openai-api", "--model", "fixture/model-v1",
                "--effort", "high", "--access", "write", "--runtime-home", str(runtime_home),
                "--broker-session-id", "11111111-1111-4111-8111-111111111111", "--fresh-session",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env={
                **self.make_environment(),
                "HERMES_TEST_BINARY": str(fixture),
                "AGENT_WORKER_MANAGED": "1",
                "AGENT_ACCESS_MODE": "write",
            },
        )
        child_pid = None
        try:
            process.stdin.write("diagnostic overflow")
            process.stdin.close()
            child_pid = self.read_ready_pid(pid_file)
            stdout, stderr = process.communicate(timeout=5)
            events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(events[-1]["code"], "diagnostic_too_large")
            self.assertNotIn("diagnostic overflow", stdout + stderr)
        finally:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate(timeout=3)
            if child_pid is not None:
                self.assert_pid_stopped(child_pid)

    def test_resume_compression_descendant_is_accepted_only_from_native_lineage(self):
        runtime_home = self.work / "runtime-resume-lineage"
        fresh, _, _, _ = self.run_bridge(runtime_home=runtime_home, session="native-root")
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        result, events, record, _ = self.run_bridge(
            runtime_home=runtime_home,
            session_args=("--resume-session", "native-root"),
            session="native-child",
            behavior="resume-rotate",
            extra_env={"FIXTURE_PARENT_SESSION": "native-root"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(record["argv"][record["argv"].index("--resume") + 1], "native-root")
        self.assertEqual(events[-1]["native_session_id"], "native-child")

    def test_fresh_routes_exact_selection_and_reports_native_result(self):
        result, events, record, runtime_home = self.run_bridge(
            extra_env={
                "HERMES_MODEL": "ambient/model",
                "HERMES_INFERENCE_MODEL": "ambient/inference-model",
                "HERMES_INFERENCE_PROVIDER": "ambient-provider",
                "HERMES_MAX_ITERATIONS": "ambient-iterations",
                "HERMES_MAX_TOKENS": "ambient-tokens",
                "HERMES_EPHEMERAL_SYSTEM_PROMPT": "ambient-prompt",
                "HERMES_PREFILL_MESSAGES_FILE": "ambient-prefill",
                "HERMES_ENVIRONMENT_HINT": "ambient-hint",
                "HERMES_FUTURE_BEHAVIOR_OVERRIDE": "ambient-future",
                "HERMES_IGNORE_USER_CONFIG": "1",
                "HERMES_IGNORE_RULES": "1",
                "HERMES_SUPERVISED_CHILD": "ambient-marker",
                "OPENAI_API_KEY": "synthetic-provider-key",
                "OPENAI_BASE_URL": "https://synthetic-provider.invalid/v1",
                "NOUS_API_KEY": "synthetic-nous-key",
                "NOUS_BASE_URL": "https://synthetic-nous.invalid/v1",
                "QWEN_API_KEY": "synthetic-qwen-key",
                "DEEPINFRA_API_KEY": "synthetic-deepinfra-key",
                "DEEPINFRA_BASE_URL": "https://synthetic-deepinfra.invalid/v1",
                "MODEL_API_KEY": "synthetic-model-key",
                "TERMINAL_ENV": "synthetic-terminal",
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([event["event"] for event in events], ["started", "session", "final"])
        self.assertEqual(events[0]["provider"], "openai-api")
        self.assertEqual(events[0]["model"], "fixture/model-v1")
        self.assertEqual(events[0]["effort"], "high")
        self.assertEqual(events[1]["native_session_id"], "20260905_120000_fixture")
        self.assertEqual(events[2]["result"], "fixture result")
        self.assertEqual(events[2]["native_session_id"], "20260905_120000_fixture")
        self.assertEqual(events[2]["broker_session_id"], "11111111-1111-4111-8111-111111111111")
        self.assertEqual(record["stdin"], "inspect the assigned repository")
        self.assertIn("--provider", record["argv"])
        self.assertEqual(record["argv"][record["argv"].index("--provider") + 1], "openai-api")
        self.assertEqual(record["argv"][record["argv"].index("--model") + 1], "fixture/model-v1")
        self.assertEqual(record["argv"][record["argv"].index("--reasoning") + 1], "high")
        self.assertIn("--toolsets", record["argv"])
        self.assertEqual(
            record["argv"][record["argv"].index("--toolsets") + 1],
            "file,search,terminal,skills",
        )
        self.assertIn("--yolo", record["argv"])
        self.assertNotIn("inspect the assigned repository", record["argv"])
        self.assertEqual(record["access"], "write")
        self.assertEqual(record["managed"], "1")
        self.assertEqual(record["model"], "")
        self.assertEqual(record["inference_model"], "")
        self.assertEqual(record["inference_provider"], "")
        self.assertEqual(set(record["ambient_surface"].values()), {""})
        self.assertEqual(set(record["retained_surface"].values()), {
            "synthetic-provider-key", "https://synthetic-provider.invalid/v1", "synthetic-nous-key",
            "https://synthetic-nous.invalid/v1", "synthetic-qwen-key", "synthetic-deepinfra-key",
            "https://synthetic-deepinfra.invalid/v1", "synthetic-model-key", "synthetic-terminal", "1",
        })
        self.assertEqual(record["retained_surface"]["HERMES_YOLO_MODE"], "1")
        self.assertEqual(record["hermes_home"], str(runtime_home))
        self.assertEqual(
            (runtime_home / "config.yaml").read_text(encoding="utf-8"),
            (ROOT / "host" / "hermes-worker" / "config.yaml").read_text(encoding="utf-8"),
        )

    def test_resume_passes_exact_native_identity_and_rejects_latest(self):
        runtime_home = self.work / "runtime-resume"
        fresh, _, _, _ = self.run_bridge(runtime_home=runtime_home, session="20260904_100000_exact")
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        result, events, record, _ = self.run_bridge(
            runtime_home=runtime_home,
            session_args=("--resume-session", "20260904_100000_exact"),
            session="20260905_rotated_native",
            behavior="resume-rotate",
            extra_env={"FIXTURE_PARENT_SESSION": "20260904_100000_exact"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(record["argv"][record["argv"].index("--resume") + 1], "20260904_100000_exact")
        self.assertIn("--no-restore-cwd", record["argv"])
        self.assertNotIn("latest", record["argv"])
        self.assertEqual(events[1]["native_session_id"], "20260905_rotated_native")
        self.assertEqual(events[1]["resumed_from_native_session_id"], "20260904_100000_exact")
        self.assertEqual(events[2]["native_session_id"], "20260905_rotated_native")

        rejected, error_events, no_record, _ = self.run_bridge(
            session_args=("--resume-session", "latest"),
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(error_events[-1]["event"], "error")
        self.assertEqual(error_events[-1]["code"], "invalid_session")
        self.assertIsNone(no_record)

    def test_runtime_state_isolated_between_workers(self):
        first, _, first_record, first_home = self.run_bridge()
        second, _, second_record, second_home = self.run_bridge()

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotEqual(first_record["hermes_home"], second_record["hermes_home"])
        self.assertEqual((first_home / "fixture-state.txt").read_text(encoding="utf-8"), "state")
        self.assertEqual((second_home / "fixture-state.txt").read_text(encoding="utf-8"), "state")
        self.assertFalse((first_home / "second").exists())
        self.assertFalse((second_home / "first").exists())

    def test_read_mode_requires_boundary_and_does_not_enable_yolo(self):
        result, _, record, _ = self.run_bridge(access="read", extra_env={"HERMES_YOLO_MODE": "ambient-yolo"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("--yolo", record["argv"])
        self.assertEqual(record["access"], "read")
        self.assertEqual(record["retained_surface"]["HERMES_YOLO_MODE"], "")

        rejected, events, no_record, _ = self.run_bridge(
            access="read",
            extra_env={"AGENT_WORKER_MANAGED": ""},
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(events[-1]["code"], "boundary_required")
        self.assertIsNone(no_record)

        mismatch, mismatch_events, mismatch_record, _ = self.run_bridge(
            access="read",
            extra_env={"AGENT_ACCESS_MODE": "write"},
        )
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertEqual(mismatch_events[-1]["code"], "boundary_required")
        self.assertIsNone(mismatch_record)

    def test_write_binding_cannot_be_resumed_as_read(self):
        runtime_home = self.work / "runtime-write-binding"
        fresh, _, _, _ = self.run_bridge(runtime_home=runtime_home, access="write", session="native-bound")
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        rejected, events, record, _ = self.run_bridge(
            runtime_home=runtime_home,
            access="read",
            session_args=("--resume-session", "native-bound"),
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(events[-1]["code"], "resume_binding_mismatch")
        self.assertIsNone(record)

    def test_empty_or_missing_native_result_fails_without_final(self):
        for behavior, code in (("empty", "empty_result"), ("no-session", "missing_native_session")):
            with self.subTest(behavior=behavior):
                result, events, _, _ = self.run_bridge(behavior=behavior)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(events[-1]["event"], "error")
                self.assertEqual(events[-1]["code"], code)
                self.assertNotIn("final", [event["event"] for event in events])

    def test_provider_error_is_nonzero_and_redacts_child_diagnostics(self):
        result, events, _, _ = self.run_bridge(
            behavior="provider-error",
            extra_env={"FIXTURE_SECRET": "do-not-leak-this"},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[-1]["event"], "error")
        self.assertEqual(events[-1]["code"], "provider_failed")
        self.assertNotIn("do-not-leak-this", result.stdout)
        self.assertNotIn("do-not-leak-this", result.stderr)
        self.assertNotIn("final", [event["event"] for event in events])

    def test_descendant_held_pipes_are_closed_after_direct_child_exit(self):
        pid_file = self.work / "holder.pid"
        result, events, _, _ = self.run_bridge(
            behavior="fork-holder",
            extra_env={"FIXTURE_PID_FILE": str(pid_file)},
            timeout=6,
        )
        holder_pid = self.read_ready_pid(pid_file)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events[-1]["event"], "final")
        self.assert_pid_stopped(holder_pid)

    def test_descendant_held_pipes_are_closed_on_provider_failure(self):
        pid_file = self.work / "failure-holder.pid"
        result, events, _, _ = self.run_bridge(
            behavior="fork-holder-error",
            extra_env={"FIXTURE_PID_FILE": str(pid_file)},
            timeout=6,
        )
        holder_pid = self.read_ready_pid(pid_file)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[-1]["code"], "provider_failed")
        self.assert_pid_stopped(holder_pid)

    def test_large_unterminated_result_is_rejected_with_a_bound(self):
        started = time.monotonic()
        result, events, _, _ = self.run_bridge(behavior="large-unterminated", timeout=6)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events[-1]["code"], "result_too_large")
        self.assertLess(time.monotonic() - started, 5)

    def test_cancellation_while_child_stdin_is_blocked_cleans_up(self):
        pid_file = self.work / "blocked.pid"
        runtime_home = self.work / "runtime-blocked"
        fixture = self.make_fixture({"behavior": "block-stdin", "session": "native-blocked", "pid_file": str(pid_file)})
        process = subprocess.Popen(
            [
                sys.executable, "-I", str(self.harness), "--provider", "openai-api", "--model", "fixture/model-v1",
                "--effort", "high", "--access", "write", "--runtime-home", str(runtime_home),
                "--broker-session-id", "11111111-1111-4111-8111-111111111111", "--fresh-session",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                **self.make_environment(),
                "HERMES_TEST_BINARY": str(fixture),
                "AGENT_WORKER_MANAGED": "1",
                "AGENT_ACCESS_MODE": "write",
            },
        )
        writer_error = []

        def write_task():
            try:
                process.stdin.write(b"x" * (4 * 1024 * 1024))
                process.stdin.close()
            except (BrokenPipeError, OSError) as exc:
                writer_error.append(exc)

        writer = threading.Thread(target=write_task, daemon=True)
        writer.start()
        child_pid = None
        try:
            child_pid = self.read_ready_pid(pid_file)
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=8)
            events = [json.loads(line) for line in stdout.decode().splitlines() if line.strip()]
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(events[-1]["code"], "interrupted")
            self.assertNotIn("final", [event["event"] for event in events])
            self.assertNotIn("x" * 100, stdout.decode() + stderr.decode())
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=3)
            writer.join(timeout=3)
            if child_pid is not None:
                self.assert_pid_stopped(child_pid)
        self.assertFalse(writer.is_alive())
        self.assertFalse(writer_error and not isinstance(writer_error[0], BrokenPipeError))

    def test_invalid_selection_and_unsafe_resume_home_are_rejected(self):
        invalid_model, model_events, model_record, _ = self.run_bridge(model="")
        self.assertNotEqual(invalid_model.returncode, 0)
        self.assertEqual(model_events[-1]["code"], "invalid_config")
        self.assertIsNone(model_record)

        automatic_provider, provider_events, provider_record, _ = self.run_bridge(provider="auto")
        self.assertNotEqual(automatic_provider.returncode, 0)
        self.assertEqual(provider_events[-1]["code"], "provider_transport_denied")
        self.assertIsNone(provider_record)

        invalid_effort, effort_events, effort_record, _ = self.run_bridge(effort="not-an-effort")
        self.assertNotEqual(invalid_effort.returncode, 0)
        self.assertEqual(effort_events[-1]["code"], "invalid_arguments")
        self.assertIsNone(effort_record)

        runtime_home = self.work / "unsafe-runtime"
        fresh, _, _, _ = self.run_bridge(runtime_home=runtime_home)
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        runtime_home.chmod(0o755)
        unsafe, unsafe_events, unsafe_record, _ = self.run_bridge(
            runtime_home=runtime_home,
            session_args=("--resume-session", "20260905_120000_fixture"),
        )
        self.assertNotEqual(unsafe.returncode, 0)
        self.assertEqual(unsafe_events[-1]["code"], "unsafe_runtime_home")
        self.assertIsNone(unsafe_record)

    def test_interrupted_child_is_cleaned_up_and_never_succeeds(self):
        pid_file = self.work / "fixture.pid"
        runtime_home = self.work / "runtime-interrupted"
        fixture = self.make_fixture({"behavior": "sleep", "session": "20260905_interrupt", "pid_file": str(pid_file)})
        process = subprocess.Popen(
            [
                sys.executable,
                "-I",
                str(self.harness),
                "--provider",
                "openai-api",
                "--model",
                "fixture/model-v1",
                "--effort",
                "high",
                "--access",
                "write",
                "--runtime-home",
                str(runtime_home),
                "--broker-session-id",
                "11111111-1111-4111-8111-111111111111",
                "--fresh-session",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env={
                **self.make_environment(),
                **{
                    "HERMES_TEST_BINARY": str(fixture),
                    "AGENT_WORKER_MANAGED": "1",
                    "AGENT_ACCESS_MODE": "write",
                },
            },
        )
        child_pid = None
        try:
            process.stdin.write("interrupt this task")
            process.stdin.close()
            child_pid = self.read_ready_pid(pid_file)
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=10)
            events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(events[-1]["event"], "error")
            self.assertEqual(events[-1]["code"], "interrupted")
            self.assertNotIn("final", [event["event"] for event in events])
            self.assertNotIn("interrupt this task", stdout + stderr)
        finally:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate(timeout=5)
            if child_pid is not None:
                self.assert_pid_stopped(child_pid)


if __name__ == "__main__":
    unittest.main()

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".venv", "__pycache__", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".zip"}


def project_files():
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if EXCLUDED_PARTS.intersection(path.parts):
            continue
        if path.suffix in EXCLUDED_SUFFIXES:
            continue
        yield path


class PortabilityTest(unittest.TestCase):
    def test_no_machine_specific_paths_in_project_files(self):
        forbidden = ["/home/" + "eliah", "Playground" + "/voltex", "Downloads" + "/voltex"]

        leaks = []
        for path in project_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for item in forbidden:
                if item in text:
                    leaks.append(f"{path.relative_to(PROJECT_ROOT)} contains {item}")

        self.assertEqual(leaks, [])

    def test_docs_do_not_tell_users_to_sudo_the_installer(self):
        forbidden = [
            "sudo " + "./install",
            "sudo " + "./scripts/install",
            "sudo " + "install.sh",
        ]
        docs = [PROJECT_ROOT / "README.md", PROJECT_ROOT / "docs" / "INSTALL.md"]

        leaks = []
        for path in docs:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for item in forbidden:
                if item in text:
                    leaks.append(f"{path.relative_to(PROJECT_ROOT)} contains {item}")

        self.assertEqual(leaks, [])

    def test_docs_use_prebaked_install_entrypoint(self):
        docs = [PROJECT_ROOT / "README.md", PROJECT_ROOT / "docs" / "INSTALL.md"]

        for path in docs:
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertIn("./install", text, str(path.relative_to(PROJECT_ROOT)))
            self.assertNotIn("./install" + ".sh", text, str(path.relative_to(PROJECT_ROOT)))

    def test_installer_python_commands_are_non_interactive(self):
        installer = (PROJECT_ROOT / "scripts" / "install-linux.sh").read_text(encoding="utf-8")

        self.assertIn("refuse_root_install", installer)
        self.assertIn("--install-system-deps", installer)
        self.assertIn("Missing system dependencies", installer)
        self.assertNotIn("python3 - " + "<<", installer)
        self.assertIn("python3 -c 'import venv' >/dev/null 2>&1 </dev/null", installer)
        self.assertIn("-m pip install", installer)
        self.assertIn("</dev/null ||", installer)

    def test_launcher_defaults_to_xwayland(self):
        launcher = (PROJECT_ROOT / "run-voltex").read_text(encoding="utf-8")

        self.assertIn('GDK_BACKEND="${VOLTEX_GDK_BACKEND:-x11}"', launcher)

    def test_installer_refuses_root_execution_before_python_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_bin = Path(tmp) / "bin"
            fake_bin.mkdir()
            fake_id = fake_bin / "id"
            fake_id.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"${1:-}\" == \"-u\" ]]; then echo 0; else /usr/bin/id \"$@\"; fi\n",
                encoding="utf-8",
            )
            fake_id.chmod(0o755)
            env = {
                "HOME": str(Path(tmp) / "home"),
                "PATH": f"{fake_bin}{os.pathsep}/usr/bin:/bin",
            }

            result = subprocess.run(
                [str(PROJECT_ROOT / "install")],
                cwd=PROJECT_ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Do not run the VoLtex installer with sudo", result.stderr)
        self.assertNotIn("Installing Python dependencies", result.stdout + result.stderr)

    def test_installer_does_not_install_system_deps_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_bin = Path(tmp) / "bin"
            fake_bin.mkdir()
            for command in ["python3", "wine", "xdg-mime", "dnf", "apt-get", "pacman", "zypper", "yum"]:
                fake_command = fake_bin / command
                fake_command.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
                fake_command.chmod(0o755)

            env = {
                "HOME": str(Path(tmp) / "home"),
                "PATH": f"{fake_bin}{os.pathsep}/usr/bin:/bin",
                "VOLTEX_INSTALL_DIR": str(Path(tmp) / "app"),
            }

            result = subprocess.run(
                [str(PROJECT_ROOT / "install")],
                cwd=PROJECT_ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing system dependencies", output)
        self.assertNotIn("Installing missing system dependencies", output)


if __name__ == "__main__":
    unittest.main()

"""Sửa activation và launcher sau khi di chuyển .ragvenv, giữ nguyên thư viện."""

import importlib.metadata
import sys
import venv
from pathlib import Path


def main():
    expected = Path(__file__).resolve().parents[1] / ".ragvenv"
    if Path(sys.prefix).resolve() != expected.resolve():
        raise SystemExit("Chạy bằng .\\.ragvenv\\Scripts\\python.exe scripts/repair_venv.py")
    from pip._vendor.distlib.scripts import ScriptMaker

    builder = venv.EnvBuilder()
    context = builder.ensure_directories(str(expected))
    builder.create_configuration(context)
    builder.setup_scripts(context)
    maker = ScriptMaker(None, str(expected / "Scripts"))
    maker.executable = sys.executable
    maker.clobber = True
    maker.variants = {""}
    repaired = 0
    for distribution in importlib.metadata.distributions():
        for entry in distribution.entry_points:
            if entry.group in ("console_scripts", "gui_scripts"):
                maker.make(f"{entry.name} = {entry.value}",
                           options={"gui": entry.group == "gui_scripts"})
                repaired += 1
    print(f"Repaired {repaired} launchers; Python: {sys.executable}")


if __name__ == "__main__":
    main()

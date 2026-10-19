# Executado pelo launcher antes de importar a interface.
from pathlib import Path

# O host instalado tem nome proprio, portanto o log nao deve depender de o
# nome de sys.executable conter "pythonw".
_log_dir = Path(appdata) / "RotorPU2PTU"
_log_dir.mkdir(parents=True, exist_ok=True)
sys.stdout = sys.stderr = open(_log_dir / "startup.log", "a", encoding="utf-8",
                              errors="replace", buffering=1)

_runtime_root = Path(scriptdir)
os.environ["TCL_LIBRARY"] = str(_runtime_root / "lib" / "tcl8.6")
os.environ["TK_LIBRARY"] = str(_runtime_root / "lib" / "tk8.6")
if hasattr(os, "add_dll_directory"):
    # Conservar o handle enquanto a janela estiver aberta.
    _tk_dll_directory = os.add_dll_directory(str(_runtime_root / "pkgs"))

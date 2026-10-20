"""Gera o instalador Windows x64 em Windows ou Linux, com Pynsist e NSIS.

Python/Tk sao obtidos da distribuicao oficial para Windows. Os wheels sao
baixados para CPython 3.12/Windows x64, nunca copiados do Python de Linux.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
from brand_runtime import brand_runtime

HERE = Path(__file__).resolve().parent
WINDOWS = HERE.parent
PYTHON_VERSION = "3.12.10"
EMBED = "python-3.12.10-embed-amd64.zip"
PINNED = {
    EMBED: "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3",
    "tcltk.msi": "55c96ffad69b1c834aa52e11b9ce41637a178ba6ad6607e83956044834276e2a",
    "pyserial-3.5-py2.py3-none-any.whl": "c4451db6ba391ca6ca299fb3ec7bae67a5c55dde170964c7a14ceefec02f2cf0",
    "geographiclib-2.1-py3-none-any.whl": "e2a873b9b9e7fc38721ad73d5f4e6c9ed140d428a339970f505c07056997d40b",
    "pillow-12.3.0-cp312-cp312-win_amd64.whl": "a2b55dd6b2a4c4b7d87ffa56bdb33fdc5fdb9a462173861a7bc097f17d91cb09",
}


def digest(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def checked(path: Path) -> Path:
    if digest(path) != PINNED[path.name]:
        raise RuntimeError(f"SHA-256 inesperado: {path}. Remova o arquivo e tente novamente.")
    return path


def download(url: str, dest: Path) -> Path:
    if not dest.exists():
        print(f"Baixando {dest.name}...", flush=True)
        partial = dest.with_suffix(dest.suffix + ".partial")
        with urllib.request.urlopen(url, timeout=90) as src, partial.open("wb") as out:
            shutil.copyfileobj(src, out)
        partial.replace(dest)
    return checked(dest)


def extract_tk(msi: Path, target: Path) -> Path:
    # Extracao administrativa nao instala Python no sistema.
    target.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        result = subprocess.run([
            "msiexec.exe", "/a", str(msi), "/qn", f"TARGETDIR={target}",
        ], check=False)
        if result.returncode not in (0, 3010):
            raise RuntimeError(f"Falha ao extrair Tcl/Tk: msiexec {result.returncode}")
    else:
        extractor = shutil.which("msiextract")
        if not extractor:
            raise RuntimeError("Instale msitools (msiextract) para extrair o Tcl/Tk de Windows.")
        subprocess.run([extractor, "-C", str(target), str(msi)], check=True,
                       stdout=subprocess.DEVNULL)
    if not (target / "DLLs" / "_tkinter.pyd").is_file():
        raise RuntimeError(f"Tcl/Tk nao encontrado em {target}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=HERE / ".build-installer")
    parser.add_argument("--tk-source", type=Path,
                        help="Python 3.12.10 x64 de Windows ja extraido (DLLs, Lib e tcl)")
    args = parser.parse_args()
    if not shutil.which("makensis"):
        raise RuntimeError("Instale NSIS 3.09+ e adicione makensis ao PATH.")
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    cache = work / "downloads"
    cache.mkdir(exist_ok=True)
    base = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/"
    download(base + EMBED, cache / EMBED)
    tk = args.tk_source.resolve() if args.tk_source else extract_tk(
        download(base + "amd64/tcltk.msi", cache / "tcltk.msi"), work / "tk")

    wheels = work / "wheels"
    wheels.mkdir(exist_ok=True)
    subprocess.run([
        sys.executable, "-m", "pip", "download", "--only-binary=:all:",
        "--no-deps", "--platform", "win_amd64", "--python-version", "3.12",
        "--implementation", "cp", "--abi", "cp312", "--dest", str(wheels),
        "pyserial==3.5", "geographiclib==2.1", "Pillow==12.3.0",
    ], check=True)
    wheel_files = [checked(wheels / name) for name in PINNED if name.endswith(".whl")]

    stage = work / "stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    for name in ("installer.cfg", "rotor.nsi", "startup.py", "CREDITOS.txt", "LICENSE_PYSERIAL.txt"):
        shutil.copy2(HERE / name, stage / name)
    shutil.copy2(WINDOWS / "assets" / "rotor_icon.ico", stage / "rotor_icon.ico")
    shutil.copy2(WINDOWS.parent / "LEIA_PRIMEIRO.md", stage / "LEIA_PRIMEIRO.md")
    shutil.copytree(tk / "tcl", stage / "lib")
    (stage / "wheels").mkdir()
    for wheel in wheel_files:
        shutil.copy2(wheel, stage / "wheels" / wheel.name)
    pkgs = stage / "pynsist_pkgs"
    pkgs.mkdir()
    for name in ("rotor_pc.py", "rotor_geo.py", "rotor_map.py", "rotor_windows.py", "rotor_i18n.py"):
        shutil.copy2(WINDOWS / name, pkgs / name)
    shutil.copy2(HERE / "rotor_sim.py", pkgs / "rotor_sim.py")
    shutil.copytree(WINDOWS / "assets", pkgs / "assets")
    shutil.copytree(tk / "Lib" / "tkinter", pkgs / "tkinter",
                    ignore=shutil.ignore_patterns("__pycache__", "test"))
    # Inclui tambem zlib1.dll, exigida pelo Tcl/Tk desta distribuicao.
    for file in (tk / "DLLs").iterdir():
        if file.suffix.lower() in (".dll", ".pyd"):
            shutil.copy2(file, pkgs / file.name)
    shutil.copy2(tk / "libs" / "_tkinter.lib", pkgs / "_tkinter.lib")

    env = os.environ.copy()
    env["PYNSIST_CACHE_DIR"] = str(cache)
    subprocess.run([sys.executable, "-m", "nsist", "--no-makensis", "installer.cfg"],
                   cwd=stage, env=env, check=True)
    brand_runtime(stage / "build/Python/pythonw.exe",
                  stage / "build/Python/Rotor_PU2PTU.exe",
                  WINDOWS / "assets/rotor_icon.ico")
    subprocess.run([shutil.which("makensis"), "build/installer.nsi"],
                   cwd=stage, env=env, check=True)
    installer_name = "Rotor_PU2PTU_1.3.0_Setup_x64.exe"
    dest = WINDOWS.parent.parent / installer_name
    shutil.copy2(stage / "build" / installer_name, dest)
    manifest = {
        "installer": dest.name,
        "sha256": digest(dest),
        "size_bytes": dest.stat().st_size,
        "runtime": "CPython 3.12.10 Windows x64 + Tcl/Tk oficial",
        "application_host": "Python/Rotor_PU2PTU.exe",
        "application_host_sha256": digest(stage / "build/Python/Rotor_PU2PTU.exe"),
        "inputs_sha256": PINNED,
    }
    (HERE / "BUILD_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Instalador gerado: {dest}", flush=True)
    print(f"SHA-256: {manifest['sha256']}")


if __name__ == "__main__":
    main()

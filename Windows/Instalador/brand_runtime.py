"""Cria um host GUI do Rotor a partir de uma copia do Pythonw oficial.

Altera somente recursos PE/metadados. O codigo executavel, as importacoes e o
pythonw.exe original permanecem preservados. LIEF e dependencia de build.
"""
from __future__ import annotations

import struct
from pathlib import Path
import lief


def _block(key: str, value: bytes = b"", children: bytes = b"", text=False) -> bytes:
    header = struct.pack("<HHH", 0, len(value)//2 if text else len(value), int(text))
    result = header + (key+"\0").encode("utf-16le")
    result += bytes(-len(result) % 4) + value
    if children:
        result += bytes(-len(result) % 4) + children
    result = struct.pack("<H", len(result)) + result[2:]
    return result


def _join(blocks):
    return b"".join(b+bytes(-len(b) % 4) for b in blocks)


def _version_resource() -> bytes:
    strings = {
        "CompanyName": "Mario Pin - PU2PTU",
        "FileDescription": "Rotor PU2PTU",
        "FileVersion": "1.2.1.0",
        "InternalName": "RotorPU2PTU",
        "OriginalFilename": "Rotor_PU2PTU.exe",
        "ProductName": "Rotor PU2PTU",
        "ProductVersion": "1.2.1",
        "LegalCopyright": "Aplicativo: Mario Pin - PU2PTU. Runtime CPython: Python Software Foundation e demais titulares; ver Python/LICENSE.txt.",
        "Comments": "Host CPython 3.12.10 com recursos visuais do Rotor. Copia modificada; pythonw.exe original preservado.",
    }
    table = _block("040904b0", children=_join([
        _block(k, (v+"\0").encode("utf-16le"), text=True) for k, v in strings.items()
    ]), text=True)
    strinfo = _block("StringFileInfo", children=table, text=True)
    translation = _block("Translation", struct.pack("<HH", 0x0409, 1200))
    varinfo = _block("VarFileInfo", children=translation, text=True)
    fixed = struct.pack("<13I", 0xFEEF04BD, 0x10000, 0x10002, 0x10000,
                        0x10002, 0x10000, 0x3F, 0, 0x40004, 1, 0, 0, 0)
    return _block("VS_VERSION_INFO", fixed, _join([strinfo, varinfo]))


def _resource(name: int, data: bytes, language=0):
    directory = lief.PE.ResourceDirectory(name)
    item = lief.PE.ResourceData(list(data), 0)
    item.id = language
    directory.add_child(item)
    return directory


def brand_runtime(original: Path, output: Path, ico: Path) -> None:
    binary = lief.PE.parse(original)
    if binary is None or not binary.has_resources:
        raise RuntimeError("Runtime Windows invalido")
    data = ico.read_bytes()
    reserved, image_type, count = struct.unpack_from("<HHH", data)
    if (reserved, image_type) != (0, 1) or not count:
        raise RuntimeError("ICO invalido")
    tree = binary.resources
    for kind in (3, 14, 16):
        tree.delete_child(kind)
    icon_dir = lief.PE.ResourceDirectory(3)
    group_data = struct.pack("<HHH", 0, 1, count)
    for i in range(count):
        width, height, colors, reserved, planes, bits, size, offset = struct.unpack_from(
            "<BBBBHHII", data, 6+16*i)
        icon_dir.add_child(_resource(i+1, data[offset:offset+size]))
        group_data += struct.pack("<BBBBHHIH", width, height, colors, reserved,
                                  planes, bits, size, i+1)
    group_dir = lief.PE.ResourceDirectory(14)
    group_dir.add_child(_resource(1, group_data))
    version_dir = lief.PE.ResourceDirectory(16)
    version_dir.add_child(_resource(1, _version_resource(), 0x0409))
    tree.add_child(icon_dir)
    tree.add_child(group_dir)
    tree.add_child(version_dir)
    # A assinatura PSF pertence ao arquivo original, nao a esta copia modificada.
    certificate = binary.data_directory(lief.PE.DataDirectory.TYPES.CERTIFICATE_TABLE)
    certificate.rva, certificate.size = 0, 0
    config = lief.PE.Builder.config_t()
    config.resources = True
    config.overlay = False
    binary.write(output, config)

# Recriar o instalador Windows x64 1.3.0

Para usar o programa, baixe `Rotor_PU2PTU_1.3.0_Setup_x64.exe` no release. O operador não precisa instalar Python ou NSIS.

## Windows

Instale Python 3.11+ com Launcher e NSIS 3.09 ou superior. Execute `Windows/GERAR_INSTALADOR.bat`. A receita baixa CPython **3.12.10 x64**, Tcl/Tk e três wheels fixados, confere SHA-256 e compila o instalador. A extração administrativa do MSI de Tcl/Tk pode exigir elevação na máquina de compilação.

## Linux

Instale NSIS, msitools, Pynsist 2.8 e LIEF 0.17.6. Execute:

```sh
python3 Windows/Instalador/build_installer.py --work-dir /caminho/temporario/build-rotor
```

O Python de build precisa de pip. O aplicativo sempre recebe o runtime Windows 3.12.10 e módulos Windows x64. O instalador gerado fica na pasta pai da raiz do repositório; `BUILD_MANIFEST.json` registra os hashes do instalador, do host e dos downloads. Os arquivos temporários ficam em `--work-dir` e não devem ser versionados.

## Conteúdo e identidade

`installer.cfg` inclui `rotor_pc`, `rotor_geo`, `rotor_map`, `rotor_windows` e `rotor_i18n`, além das dependências. `startup.py` prepara Tcl/Tk e DLLs. O atalho de simulação usa `rotor_sim.py`. `rotor.nsi` define interface do instalador em português, instalação por usuário, ícone, atalhos e desinstalação. O idioma do aplicativo é escolhido pelas cinco bandeiras na própria janela.

A receita prepara Pynsist com `--no-makensis`, gera `Python/Rotor_PU2PTU.exe` com `brand_runtime.py` e compila NSIS. O host é cópia do Pythonw com recursos PE de ícone/versão substituídos; código, ponto de entrada e imports são preservados. A assinatura do original não é atribuída à cópia modificada, e os binários oficiais originais ficam incluídos. LIEF é dependência apenas de build.

A instalação não altera PATH nem instalações de Python existentes, e não grava o Arduino. O aplicativo 1.3.0 exige firmware 1.2/protocolo 2. A desinstalação preserva configurações e cache em `%APPDATA%\RotorPU2PTU`.

Referências: [Pynsist](https://pynsist.readthedocs.io/en/latest/cfgfile.html), [NSIS Modern UI](https://nsis.sourceforge.io/Docs/Modern%20UI%202/Readme.html).

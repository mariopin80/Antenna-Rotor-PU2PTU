# Recriar o instalador Windows x64

O operador pode usar diretamente `Rotor_PU2PTU_1.2.1_Setup_x64.exe`. Nao precisa de Python, NSIS ou destes scripts.

Para recriar no Windows, instale Python 3.11+ com o Python Launcher e NSIS 3.09 ou superior. Execute `Windows/GERAR_INSTALADOR.bat`. O script baixa o runtime oficial de CPython **3.12.10 x64**, Tcl/Tk e os tres wheels fixados, confere SHA-256 e compila o instalador. A extracao administrativa do MSI de Tcl/Tk pode exigir elevacao no computador de compilacao. Nao instala outro Python no computador do operador.

Em Linux, instale NSIS, msitools e Pynsist 2.8 e LIEF 0.17.6. Execute:

```
python3 Windows/Instalador/build_installer.py --work-dir /caminho/temporario/build-rotor
```

O Python usado para compilar precisa de pip. O build pode usar Python 3.11+, mas sempre inclui o runtime Windows 3.12.10, com modulos binarios Windows x64. O destino do instalador e a pasta que contem o pacote `Rotor_PU2PTU_1.2.1`; nao e instalado automaticamente. O manifesto registra o hash do instalador e de suas entradas.

O template `rotor.nsi` define idioma portugues, instalacao por usuario, icone, atalhos, abertura ao terminar e desinstalacao. `startup.py` configura as bibliotecas Tcl/Tk antes de abrir a janela. `rotor_sim.py` implementa o atalho de simulacao. O icone da janela e aplicado por `RotorApp.set_window_icon` no codigo principal.

O desinstalador remove apenas os componentes do programa. As configuracoes e o cache em `%APPDATA%\RotorPU2PTU` ficam preservados para uma reinstalacao. A instalacao nao altera o PATH nem uma instalacao preexistente de Python e nao grava firmware.

Referencias de build: [Pynsist](https://pynsist.readthedocs.io/en/latest/faq.html#packaging-with-tkinter), [configuracao](https://pynsist.readthedocs.io/en/latest/cfgfile.html), [NSIS Modern UI](https://nsis.sourceforge.io/Docs/Modern%20UI%202/Readme.html).

A receita prepara o Pynsist com `--no-makensis`, cria `Python/Rotor_PU2PTU.exe` com `brand_runtime.py` e só então compila o NSIS. O host é uma cópia do Pythonw com recursos PE de ícone e versão substituídos. O código `.text`, o ponto de entrada e as importações são preservados. A assinatura do original não é atribuída à cópia modificada; os arquivos oficiais originais permanecem no pacote. LIEF é necessário somente para gerar o instalador, não é instalado no computador do operador.

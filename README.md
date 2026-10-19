# Rotor PU2PTU

Controlador de rotor de antena com firmware Arduino Uno e interface para Windows.

**Autor: Mario Pin – PU2PTU.**

| Componente | Versão atual | Código principal |
|---|---|---|
| Interface Windows | 1.2.1 | [Windows/rotor_pc.py](Windows/rotor_pc.py) |
| Firmware Arduino Uno | 1.1 | [Arduino/rotor_1_1/rotor_1_1.ino](Arduino/rotor_1_1/rotor_1_1.ino) |
| Protocolo serial | 1, a 115200 baud | [PROTOCOLO.md](PROTOCOLO.md) |

## Recursos

- Conexão USB por porta COM, leitura de azimute e controle manual ESQ/DIR.
- Apontamento para ângulo ou grid locator Maidenhead de 2, 4 ou 6 caracteres.
- Mapa OpenStreetMap centrado na estação, com escala ajustável.
- Cone transparente com largura total do feixe horizontal a −3 dB e opacidade ajustável.
- Modo de simulação sem Arduino.
- Firmware com aceleração/desaceleração, limites eletrônicos, prioridade dos botões físicos e parada por perda de comunicação.

## Interface Windows

O instalador da versão 1.2.1 destina-se a Windows 10/11 x64 e inclui Python e as bibliotecas necessárias. O instalador pronto é distribuído à parte; o repositório contém os fontes completos e a receita para recriá-lo.

Para executar pelos fontes, instale Python 3.11 ou 3.12 com Tcl/Tk. Na pasta `Windows`, execute `INSTALAR.bat` e depois `SIMULAR.bat` ou `INICIAR.bat`.

Para compilar o instalador, use `Windows/GERAR_INSTALADOR.bat`. Veja os pré-requisitos em [Windows/Instalador/REBUILD.md](Windows/Instalador/REBUILD.md). Para gerar um executável com PyInstaller, use `Windows/GERAR_EXE.bat`.

As configurações da estação e do mapa ficam em `%APPDATA%\RotorPU2PTU`. Novas áreas do mapa exigem internet. Os cálculos de grid locator e a comunicação USB funcionam sem o mapa disponível.

O campo de feixe informa o **ângulo total**: por exemplo, 60° significa ±30° em torno do eixo.

## Firmware Arduino

Abra `Arduino/rotor_1_1/rotor_1_1.ino` na IDE Arduino e selecione **Arduino Uno**. Instale **Adafruit GFX Library**, **Adafruit ST7735 and ST7789 Library** e **Adafruit BusIO**.

A montagem usa display ST7789, potenciômetro em A0 e ponte H BTS7960. Os pinos, a calibração, os limites e os procedimentos de ensaio estão no [guia do firmware](Arduino/GUIA_FIRMWARE_1.1.md). A versão original recebida do autor está preservada em `Arduino/Original_1.0`.

## Organização

| Pasta ou arquivo | Conteúdo |
|---|---|
| `Windows/` | Interface, mapa, cálculos geográficos, scripts e ícones |
| `Windows/Instalador/` | Receita NSIS/Pynsist, identificação do executável e manifesto |
| `Arduino/` | Firmware atual, original 1.0 e documentação do hardware |
| `Testes/` | Testes da interface, comunicação, mapas, ícones e firmware |
| [LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md) | Manual de operação da interface atual |
| [VALIDACAO.md](VALIDACAO.md) | Resultados e limites da validação |
| [CHANGELOG.md](CHANGELOG.md) | Histórico das versões |

## Testes

Com as dependências de `Windows/requirements.txt` instaladas, execute na raiz:

```sh
python -m unittest discover -s Testes -v
```

O teste da interface é habilitado com `ROTOR_TEST_UI=1`; exige um display gráfico. O teste de ícones nativos exige Windows, e os testes de pseudo-terminal exigem POSIX. Consulte [VALIDACAO.md](VALIDACAO.md) para executar os testes opcionais.

Os cenários do firmware usam o sketch real com IO substituído e requerem `g++`:

```sh
python Testes/executar_firmware.py
```

Na preparação da 1.2.1, 27 testes da interface/cálculos/comunicação passaram em Linux; um teste específico de janela Windows foi ignorado. O instalador e seus recursos foram conferidos por análise estática. A apresentação final da 1.2.1 no Windows e a operação mecânica dependem de ensaio no equipamento.

O cone do mapa representa apenas a orientação e a abertura angular configurada. A documentação detalha os limites dessa representação e da precisão mecânica.

## Créditos

Dados do mapa: [OpenStreetMap contributors](https://www.openstreetmap.org/copyright). Bibliotecas e avisos de terceiros: [Windows/Instalador/CREDITOS.txt](Windows/Instalador/CREDITOS.txt).

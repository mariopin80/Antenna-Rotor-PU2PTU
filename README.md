# Rotor PU2PTU

Controlador de rotor de antena com firmware Arduino Uno e interface para Windows.

**Autor: Mario Pin – PU2PTU.**

| Componente | Versão atual | Código principal |
|---|---|---|
| Interface Windows | 1.3.0 | [Windows/rotor_pc.py](Windows/rotor_pc.py) |
| Firmware Arduino Uno | 1.2 | [Arduino/rotor_1_2/rotor_1_2.ino](Arduino/rotor_1_2/rotor_1_2.ino) |
| Protocolo serial | 2, a 115200 baud | [PROTOCOLO.md](PROTOCOLO.md) |

## Recursos

- Painel de comandos compacto, com 60% da largura anterior e mais espaço para o mapa.
- Interface em português, inglês, espanhol, alemão e russo; seleção por bandeiras no canto inferior direito.
- Configuração de estação e largura total do feixe −3 dB dentro da janela principal.
- Limite global de velocidade em seis níveis, configurável pelo Windows ou pelos dois botões do Arduino, salvo na EEPROM.
- Conexão USB por porta COM, azimute em tempo real e controle manual ESQ/PARAR/DIR.
- Apontamento para ângulo ou grid locator Maidenhead de 2, 4 ou 6 caracteres.
- Mapa OpenStreetMap centrado na estação, escala ajustável e cone transparente com opacidade ajustável.
- Simulação sem Arduino; aceleração/desaceleração, limites eletrônicos, prioridade local e parada por perda de comunicação no firmware.

![Interface 1.3.0 em simulação](Interface_1.3.png)

## Instalar ou atualizar

Baixe **Rotor_PU2PTU_1.3.0_Setup_x64.exe** no [release v1.3.0](https://github.com/mariopin80/rotor-pu2ptu/releases/tag/v1.3.0). Destina-se a Windows 10/11 x64 e inclui Python e as bibliotecas necessárias.

**Para controlar o equipamento com o Windows 1.3.0, grave também o firmware 1.2.** O protocolo mudou para a versão 2; o aplicativo não habilita uma versão antiga de firmware. O instalador não grava o Arduino.

O release inclui o pacote completo de fontes e um pacote separado do firmware. As versões Arduino 1.0 e 1.1 permanecem preservadas. Consulte [LEIA_PRIMEIRO.md](LEIA_PRIMEIRO.md) e o [guia do firmware 1.2](Arduino/GUIA_FIRMWARE_1.2.md).

As configurações existentes são reaproveitadas em `%APPDATA%\RotorPU2PTU\mapa.json`; o idioma passa a ser salvo nesse arquivo. O limite de velocidade é lido do Arduino, sem aplicar um valor antigo do computador ao conectar.

## Executar ou compilar pelos fontes

Instale Python 3.11/3.12 com Tcl/Tk. Na pasta `Windows`, execute `INSTALAR.bat` e depois `SIMULAR.bat` ou `INICIAR.bat`. Para recriar o instalador, use `GERAR_INSTALADOR.bat`; os pré-requisitos estão em [REBUILD.md](Windows/Instalador/REBUILD.md). `GERAR_EXE.bat` mantém a alternativa PyInstaller.

Abra `Arduino/rotor_1_2/rotor_1_2.ino` na IDE Arduino, selecione **Arduino Uno** e instale **Adafruit GFX Library**, **Adafruit ST7735 and ST7789 Library** e **Adafruit BusIO**. EEPROM, SPI e Wire pertencem ao pacote AVR.

## Limite de velocidade

| Nível | PWM máximo / 255 |
|---|---:|
| 1 | 70 |
| 2 | 90 |
| 3 | 110 |
| 4 | 140 |
| 5 | 175 |
| 6 | 220 |

O limite vale para botões físicos, JOG USB e apontamento automático. É um limite de PWM; a velocidade mecânica depende da alimentação e da carga. No Arduino parado, mantenha ambos os botões por dois segundos para abrir o ajuste, solte-os, use ESQ/DIR e pressione ambos para salvar. Ambos durante movimento continuam causando parada imediata.

## Organização e testes

| Pasta ou arquivo | Conteúdo |
|---|---|
| `Windows/` | Interface, traduções, mapa, cálculos, ícones e scripts |
| `Windows/Instalador/` | Receita NSIS/Pynsist, identificação do executável e manifesto |
| `Arduino/` | Firmware atual, versões anteriores e documentação do hardware |
| `Testes/` | Testes da interface, comunicação, mapas, ícones e firmware |
| [VALIDACAO.md](VALIDACAO.md) | Verificações e limites desta entrega |
| [CHANGELOG.md](CHANGELOG.md) | Histórico das versões |

Na raiz, com as dependências de `Windows/requirements.txt` instaladas:

```sh
python -m unittest discover -s Testes -v
python Testes/executar_firmware.py
```

A GUI é habilitada com `ROTOR_TEST_UI=1` e exige display gráfico. Os testes de pseudo-terminal exigem POSIX e a consulta de ícone nativo exige Windows. Nesta entrega passaram 34 testes Python e 25 cenários do firmware; um teste específico de Windows foi ignorado. O firmware também compilou para Uno com o core AVR real e as bibliotecas Adafruit. Não houve ensaio no rotor físico nem execução em Windows neste ambiente.

O feixe configurado é o **ângulo total**: 60° significa ±30° em torno do eixo. O cone representa orientação e abertura, sem estimar alcance ou cobertura de rádio. Novas áreas do mapa exigem internet; controle USB e cálculos de grid funcionam sem mapa.

## Créditos

Dados do mapa: [OpenStreetMap contributors](https://www.openstreetmap.org/copyright). Bibliotecas e avisos: [Windows/Instalador/CREDITOS.txt](Windows/Instalador/CREDITOS.txt).

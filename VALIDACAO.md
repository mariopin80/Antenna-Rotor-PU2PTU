# Validação — Windows 1.3.0 / Arduino 1.2 — 20/10/2026

## Resultado

- Suíte Python: **35 casos, 34 aprovados e 1 ignorado** por exigir janela nativa Windows.
- Firmware real com IO substituído: **25 cenários aprovados**.
- Compilação para Arduino Uno com core AVR real e bibliotecas Adafruit: **aprovada**, 41 unidades de compilação; programa 27.498 bytes e dados estáticos 1.073 bytes.
- Inspeção visual em português, inglês, espanhol, alemão e russo, incluindo configuração dentro da janela e mosaicos OpenStreetMap reais da vista atual.
- Instalador Windows x64 gerado e inspecionado estaticamente conforme o manifesto de build.

Ambiente Python 3.12, Pillow 12.3.0, GeographicLib 2.1, pySerial 3.5 e Tk em Linux. Os testes de GUI usam display virtual. O rotor físico e uma máquina Windows não estavam disponíveis; compilação e simulação não comprovam execução nesses ambientes.

## Interface e comunicação

Mantidas as regressões de grid locator, geodésicas WGS84, projeção/antimeridiano, escala, cache HTTP, mistura RGBA do cone, fila de STOP, validação serial, ícones e parada por soltura/perda de foco.

Verificações específicas desta atualização:

- Coluna esquerda com 234 px (60% dos 390 px anteriores) e mapa usando o espaço restante.
- Configuração como Frame da janela principal, sem nova Toplevel; dados inválidos sinalizados no próprio formulário.
- Feixe −3 dB no formulário da estação; alternar idioma preserva valores em edição e salvar não inicia movimento.
- Catálogos dos cinco idiomas completos e com os mesmos parâmetros de formatação.
- Persistência do idioma, migração de configurações anteriores e ausência de restauração de velocidade antiga do computador.
- Simulação com os seis tetos de PWM; seleção pendente impede novos comandos até a confirmação.
- Modo 5 bloqueia controles de movimento/alteração remota do limite; STOP continua disponível.
- Transporte pySerial real sobre pseudo-terminal com identidade protocolo 2, consulta/alteração de SPEED, pacotes fragmentados e reinício da placa.
- Cone ocultado ao desconectar, atalhos do teclado sem movimento dentro de campos e regressões dos ícones preservadas.

As capturas `Interface_1.3.png` e `Configuracao_1.3.png` são simulações em Linux. Usam centro do grid GG66dr, destino GG67aa e apontamento de 325°; esses dados não são gravados como estação padrão. O primeiro uso continua exigindo configurar a estação.

## Firmware

Os 25 cenários incluem os testes anteriores de parser, watchdog de comunicação, fim de curso, sensor, prioridade local, travamento, duração máxima, inversão e trajetória automática, além de:

- Todos os seis níveis em botões físicos, JOG nos dois sentidos e automático.
- Redução imediata do teto durante movimento e aumento gradual sem salto ao máximo.
- Identidade 1.2/protocolo 2 e validação estrita de SPEED.
- Gravação/restauração em dois registros EEPROM, ausência de regravação do mesmo nível, 300 gravações cruzando a volta do contador e recuperação após interrupção de escrita.
- EEPROM virgem iniciando em 6 e registros inválidos adotando 1.
- Entrada no menu parado, liberação dos botões, alteração por toque, salvamento e bloqueio de movimento até soltura.
- Dois botões durante movimento parando sem abrir menu; falha de sensor continua protegendo mesmo no menu.

Os sketches 1.0 e 1.1 permanecem preservados. O corte final do PWM mínimo e o ajuste geral de desaceleração não foram alterados nesta versão. Os limites eletrônicos continuam dependendo da calibração e do sensor da montagem.

## Repetir

```sh
python -m unittest discover -s Testes -v
python Testes/executar_firmware.py
```

Para incluir GUI, defina `ROTOR_TEST_UI=1` e use um display disponível. Em PowerShell:

```powershell
$env:ROTOR_TEST_UI='1'
py -3 -m unittest discover -s Testes -v
```

Pseudo-terminais exigem POSIX; WM_GETICON exige Windows. Testes de mapa não usam a rede; a inspeção visual de OSM foi separada, apenas para a vista atual. Nenhum cache é distribuído.

Para compilar o firmware, abra o sketch 1.2 na IDE Arduino com placa Uno e as bibliotecas do guia. Os testes nativos usam g++ e não substituem essa compilação AVR.

## Instalador e limites

A receita usa CPython 3.12.10 Windows x64, Tcl/Tk oficial, wheels Windows fixados por SHA-256, Pynsist 2.8, LIEF 0.17.6 e NSIS 3.09. O pacote contém os cinco módulos da aplicação, traduções, assets e dependências. O manifesto registra o instalador e o host com seus hashes.

A inspeção confere integridade do arquivo, identidade x64, recursos de ícone, módulos idênticos aos fontes, ausência de extensões Linux, imports das DLLs e presença do runtime. O host e os atalhos preservam a correção de ícones da 1.2.1. A instalação/remoção e os ícones exibidos no Windows precisam de confirmação nesse sistema.

Não houve ensaio mecânico, medição de velocidade, torque, precisão ou diagrama de radiação. O teto é PWM, não uma velocidade física regulada. O cone representa orientação e abertura, sem prever cobertura. O primeiro ensaio deve começar no modo Simulação e depois seguir o guia de bancada do firmware.

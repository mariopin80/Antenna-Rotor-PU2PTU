# Validação — Windows 1.2.1 — 19/10/2026

## Resultado

Foram aprovados **27 testes automatizados**, incluindo a interface Tk em display virtual. Também houve inspeção visual de uma vista real do OpenStreetMap, carregada pela implementação do aplicativo, com todos os 12 mosaicos necessários à vista disponíveis.

Ambiente: Python 3.12, Pillow 12.3.0, GeographicLib 2.1, pySerial 3.5 e Tk em Linux. O rotor físico e uma máquina Windows não estavam disponíveis. O instalador Windows x64 1.2.1 foi compilado em Linux; a execução no Windows do operador ainda precisa ser confirmada.

## O que foi verificado

- Grid locator Maidenhead de 2, 4 e 6 caracteres, aceitando letras maiúsculas/minúsculas e rejeitando entradas inválidas.
- Coordenadas com vírgula decimal e validação dos limites da projeção.
- Azimutes cardeais, distância e azimute geodésicos WGS84, incluindo comparação com o exemplo oficial Wellington–Salamanca da GeographicLib.
- Projeção/inversão, preservação da estação exatamente no centro e passagem pelo antimeridiano.
- Abertura do feixe como ângulo **total**: um feixe de 60° produz bordas a ±30°, inclusive cruzando 0°/360°.
- Ajuste de escala para que o círculo de referência caiba na janela, em diferentes latitudes e raios.
- Persistência de estação, feixe, opacidade e destino, com tratamento de configurações inválidas.
- Cache sem acesso à rede quando válido; identificação HTTP própria; revalidação condicional; manutenção do tile disponível quando a rede falha.
- Entrada e validação de ângulo, análise de telemetria e prioridade de STOP na fila.
- Identificação e comandos seriais com pySerial real sobre pseudo-terminal, reinício da placa e fragmentação de pacotes.
- Na interface: configurar estação, calcular destino sem movimentar, apontar para o grid, parar, JOG e parada ao soltar, configurações de mapa e persistência.
- As setas do teclado em campos de edição e no slider de opacidade não iniciam movimento do rotor.
- Mistura RGBA do cone conferida numericamente contra o pixel original do mapa, confirmando a opacidade configurada.
- O cone é ocultado ao desconectar/perder telemetria.
- O ícone `.ico` contém os tamanhos 16, 24, 32, 48, 64, 128 e 256 px; os arquivos usados pela janela e pelo empacotador estão presentes.

A vista real de exemplo usa o centro do grid GG66dr, destino GG67aa e azimute simulado de 325°. Não é um registro do rotor físico nem define automaticamente a localização do operador na primeira execução. A configuração inicial de estação permanece vazia até ser informada pelo usuário.

## Firmware

O arquivo `Arduino/rotor_1_1/rotor_1_1.ino` foi comparado byte a byte com o firmware anterior e está idêntico.

SHA-256: `3ccebbfd42006941598731c5a57b32543d17ff747235eb9e397e83bf3bd3fb0b`.

Esta atualização não introduz alteração de movimento, não revalida mecanicamente o rotor e não altera o corte final de PWM. A validação anterior e o guia do firmware foram preservados em `Arduino/VALIDACAO_FIRMWARE_1.1.md` e `Arduino/GUIA_FIRMWARE_1.1.md`.

## Repetir os testes

Na raiz do pacote, com dependências de `Windows/requirements.txt` instaladas:

```
python -m unittest discover -s Testes -v
```

Os testes de cálculo, armazenamento, comunicação e regressão dos ícones são executados normalmente. A suíte completa tem 28 casos: 27 passaram em Linux, incluindo a GUI; a consulta WM_GETICON foi ignorada por exigir Windows. Os testes de pseudo-terminal são específicos de POSIX e serão ignorados no Windows.

O teste de interface é opcional. Em PowerShell, para ativá-lo:

```
$env:ROTOR_TEST_UI='1'
py -3 -m unittest discover -s Testes -v
```

Em Linux, é preciso um display disponível (`DISPLAY`) ou um Xvfb. O teste de interface usa tiles de teste/ausentes e não acessa a rede. A inspeção visual do OpenStreetMap real foi feita separadamente, apenas para a vista atual; nenhum cache de tiles é distribuído.

## Limites

Não houve ensaio de campo, medição de diagrama de radiação nem validação de precisão mecânica. O mapa mostra orientação e abertura angular; não representa cobertura de rádio. A precisão de apontamento por grid depende da célula informada e da posição real da estação dentro dela.

O instalador Windows foi compilado com Pynsist 2.8, LIEF 0.17.6 e NSIS 3.09. A execução em Windows e a criação/remoção efetiva dos atalhos ainda não foram testadas. O teste em Wine não chegou a iniciar: o ambiente bloqueou a criação do socket local necessário ao wineserver (`Operation not permitted`). Isso não é um resultado de execução do aplicativo.

## Correção dos ícones em 1.2.1

As imagens enviadas pelo operador mostram que a versão 1.2 abriu a janela com ícone genérico e apresentou Python na barra de tarefas. Esse relato comprova o defeito visual no Windows, apesar da presença dos assets no instalador.

A versão 1.2.1 usa um host GUI com nome e ícone próprios e os atalhos abrem esse host. O código nativo do host é idêntico ao do Pythonw oficial; somente os recursos e metadados PE foram alterados, sem atribuir a assinatura original à cópia. O runtime original permanece preservado. A identidade inferida do caminho do EXE permite ao Windows relacionar processo e atalhos.

A janela aplica o ICO ao Tk e usa `LoadImageW`/`WM_SETICON` no HWND externo. O PNG é alternativa independente. A configuração é repetida após o mapeamento da janela, com handles do tamanho correto para 64 bits e liberação ao fechar. Falhas ficam registradas no log do programa.

Os cinco novos testes portáteis cobrem: falha de DPI sem omitir identidade; identidade do host; ICO independente do PNG; falha do Tk sem impedir a via nativa; e HWND externo com handles maiores que 32 bits. O teste adicional de GUI em Windows consulta `WM_GETICON` para os dois tamanhos, mas não foi executado neste ambiente.

## Verificação do instalador

- Instalador e desinstalador com cabeçalhos PE de Windows x64 e recursos de ícone conferidos.
- Os sete recursos RT_ICON incorporados ao instalador, ao desinstalador e ao host `Rotor_PU2PTU.exe` correspondem byte a byte às imagens do ICO fornecido (16, 24, 32, 48, 64, 128 e 256 px).
- Conteúdo do instalador extraído com 7-Zip para conferir integridade, módulos, assets e dependências.
- Python 3.12.10 embutido para Windows x64, com Tcl/Tk extraído do MSI oficial da mesma versão e arquitetura.
- Wheels Windows: Pillow 12.3.0 CPython 3.12 x64, pySerial 3.5 e GeographicLib 2.1. Downloads fixados e conferidos por SHA-256.
- `_tkinter.pyd`, Tcl/Tk, zlib1 e as bibliotecas Visual C++ exigidas estão no pacote. Os binários do programa são todos x64; não há extensões `.so` de Linux.
- Importações PE conferidas contra as DLLs incluídas e bibliotecas do sistema Windows. Essa análise estática não substitui a carga das DLLs no Windows.
- Os quatro módulos principais, incluindo `rotor_windows.py`, são os mesmos submetidos aos testes.
- PNG e ICO da janela ficam em `pkgs/assets`, caminho resolvido por `rotor_windows.asset_path`; o preâmbulo configura os caminhos de Tcl/Tk e das DLLs, além do log de inicialização.
- Template compilado em português, por usuário, com atalho na área de trabalho, menu Iniciar, opção de simulação e desinstalador. Os atalhos apontam para o host `Python/Rotor_PU2PTU.exe` e usam o ICO do rotor; os caminhos e argumentos são colocados entre aspas.
- A receita de desinstalação remove os componentes conhecidos do programa, seus atalhos e o registro de desinstalação; preserva `%APPDATA%\RotorPU2PTU`.
- O SHA-256 do instalador está em `Windows/Instalador/BUILD_MANIFEST.json`.

No Windows, o primeiro ensaio recomendado é abrir **Rotor PU2PTU - Simulacao** no menu Iniciar, conferir o ícone no canto superior esquerdo e só então testar a conexão ao Arduino já gravado com o firmware 1.1.

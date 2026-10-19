# Rotor — Mario Pin / PU2PTU · versão 1.1

Esta versão parte do arquivo `rotor_1.0.ino` fornecido pelo autor. Acrescenta controle USB pelo computador, mantendo os pinos, a calibração, a tela ST7789 e os seis níveis de PWM dos botões físicos. O controle automático e os limites são executados no Arduino; o programa Windows envia comandos e mostra o estado recebido.

## O que o programa faz

- Lista as portas COM e conecta ao firmware compatível.
- Mostra azimute atual e direção cardinal.
- Mostra a barra de posição mecânica entre os limites esquerdo e direito, como no display.
- Gira enquanto ESQ ou DIR estiver pressionado. Soltar ou tirar o mouse do botão interrompe o comando. As setas do teclado também funcionam quando o campo de ângulo não está selecionado.
- Recebe um ângulo entre 0° e 360°, incluindo vírgula decimal, e inicia o apontamento pelo botão APONTAR ou pela tecla Enter no campo.
- Acelera automaticamente em pequenos incrementos de PWM e reduz o PWM ao se aproximar do alvo.
- PARAR e Esc cancelam o movimento. Desconectar ou fechar a janela também solicita parada.
- Tem modo de simulação para experimentar a interface sem hardware.

Correção incluída: compatibilidade dos protótipos automáticos da IDE Arduino, que elimina o erro `iniciarComando declared void`. O aplicativo Windows e o protocolo permanecem na versão 1.1.

Ajuste de suavidade incluído: `AUTO_DESACELERACAO = 30.0f` e `AUTO_DESACEL_PASSO = 1`, após o primeiro relato de ensaio do rotor.

## 1. Atualizar o Arduino

1. Guarde a versão 1.0. A cópia recebida está na pasta `Arduino/Original_1.0`.
2. Abra `Arduino/rotor_1_1/rotor_1_1.ino` na IDE Arduino. O nome da pasta deve coincidir com o nome do sketch.
3. Selecione **Arduino Uno** e a porta COM correta.
4. Mantenha as bibliotecas usadas na 1.0: **Adafruit GFX Library**, **Adafruit ST7735 and ST7789 Library** e **Adafruit BusIO**. As bibliotecas SPI e Wire são do pacote AVR.
5. Compile e grave. Não altere a ligação do BTS7960 para esta atualização.
6. Feche o Monitor Serial antes de conectar o aplicativo. A mesma porta não pode ser aberta pelos dois ao mesmo tempo.

O sketch contém watchdog de 1 segundo e é destinado ao Uno com bootloader Optiboot. Placas AVR antigas com outro bootloader precisam ser verificadas antes de usar esse recurso. A verificação de compilação e suas versões constam de `VALIDACAO.md`.

### Ligações mantidas

| Função | Pino / ligação |
|---|---|
| Potenciômetro: cursor | A0 |
| Potenciômetro: referência | 5 V e GND; calibração considera VREF = 5,00 V |
| Botão esquerda | D2 para GND; INPUT_PULLUP |
| Botão direita | D4 para GND; INPUT_PULLUP |
| BTS7960 RPWM | D3 |
| BTS7960 LPWM | D5 |
| BTS7960 R_EN / L_EN | 5 V, conforme versão 1.0 |
| ST7789 CS / DC / RST | D10 / D9 / D8 |
| ST7789 MOSI / SCK | SPI do Uno: D11 / D13 |
| GND | Comum entre Uno e lógica do driver, conforme montagem existente |

A alimentação do motor continua na entrada de potência do driver. A alimentação e os níveis lógicos do display continuam os da montagem que já funciona; a tabela não autoriza aplicar 5 V diretamente a um display que exija 3,3 V.

## 2. Instalar e abrir no Windows

Programa em Python/Tk, com scripts para Windows 10/11. O pacote contém o código completo; o executável Windows pode ser gerado no próprio Windows.

1. Extraia o ZIP inteiro para uma pasta local, por exemplo `Documentos\Rotor_PU2PTU_1.1`. Não execute os atalhos dentro da visualização do ZIP.
2. Instale o **Python 3.11 ou 3.12** em [python.org](https://www.python.org/downloads/windows/), mantendo **Python Launcher** e **Tcl/Tk**. O Launcher fornece o comando `py` usado nos scripts.
3. Abra a pasta `Windows` e execute **INSTALAR.bat** uma vez. Esse script cria um ambiente local e instala `pyserial==3.5`. Precisa de internet nesta primeira instalação.
4. Execute **SIMULAR.bat** para conhecer a interface sem Arduino.
5. Para controlar o rotor, execute **INICIAR.bat**, selecione a COM e clique **Conectar**. Aguarde a inicialização e a identificação do firmware.

Abrir a porta pode reiniciar o Uno. O programa espera a resposta do firmware e envia STOP antes de habilitar o movimento. Nenhum movimento automático é retomado ao reconectar. Depois da instalação, a operação USB não precisa de internet.

### Gerar um executável independente

Execute **GERAR_EXE.bat** após instalar. O script usa PyInstaller e cria `Windows/dist/Rotor_PU2PTU.exe`. A geração precisa de internet para instalar o empacotador; o arquivo gerado pode ser usado em um Windows compatível sem instalar Python. O `.exe` não é assinado digitalmente.

O pacote desta entrega não contém um `.exe` Windows já compilado: a geração deve ser feita no Windows, conforme o procedimento acima. O teste da interface nesta entrega foi executado em Linux, com o mesmo código Tk; a apresentação das fontes e dos controles pode variar no Windows.

## 3. Como o movimento funciona

### Manual

Os botões físicos mantêm a rampa original: PWM **70, 90, 110, 140, 175 e 220**, a cada aproximadamente 0,5 s. O JOG do PC usa os mesmos níveis. Soltar um botão desliga a saída imediatamente, sem uma rampa de parada que prolongue o movimento. A inércia mecânica pode continuar deslocando o eixo depois de desligar o PWM.

Qualquer pressão de um botão físico cancela o movimento remoto e assume o controle local. Soltar não retoma o alvo do PC. Pressionar os dois botões físicos para e exige soltar ambos antes de voltar a movimentar. Um STOP recebido enquanto um botão físico estiver pressionado mantém a parada até esse botão ser solto.

Na tela do Arduino, a indicação original de cinco setas com vermelho no PWM máximo foi preservada exatamente. No aplicativo, a indicação tem até seis setas e fica vermelha no máximo.

### Automático

O Arduino lê a posição a cada aproximadamente 20 ms. Inicia pelo PWM mínimo 70, necessário como ponto de partida da montagem existente, e aumenta em passos de 1 até no máximo 220. Ao entrar na região de desaceleração, reduz a referência de PWM proporcionalmente à distância restante, com passos de redução de até 1. No fim, desliga a saída ao entrar na tolerância de 1° ou cruzar o alvo. Não faz inversões sucessivas para caçar a posição.

A região de redução começa a aproximadamente **31°** do alvo: 30° de desaceleração mais 1° de tolerância. A configuração inicial deve ser ajustada em bancada. O mecanismo não tem frenagem ativa adicional nesta versão. A precisão final depende do potenciômetro, folgas, carga, velocidade e inércia; exibir décimos de grau não implica essa precisão física.

### Norte e limites mecânicos

A calibração foi preservada: **4,80 V = primeiro Norte**, **0,40 V = segundo Norte**, com azimute aumentando ao girar para a direita. A posição mecânica é contínua entre essas referências, mesmo quando o azimute volta a 0°.

O firmware considera as posições equivalentes do alvo que cabem no curso e escolhe a mais próxima. 0° e 360° representam o mesmo apontamento, e não uma escolha obrigatória de extremidade. Exemplos:

| Posição mecânica atual | Alvo digitado | Resultado |
|---|---|---|
| 358° | 0° | Vai para a posição mecânica 360°, próxima do segundo Norte |
| 1° | 359° | Pode ir para a posição mecânica −1°, dentro da pequena sobreposição disponível |
| 5° | 355° | Vai para 355° pelo curso longo; −5° fica fora da margem adotada |

A margem dos alvos usa os limiares de liberação dos fins de curso: 0,35 V e 4,85 V. Isso permite alvos mecânicos aproximadamente entre −4,1° e 364,1°. Os bloqueios elétricos continuam em **≤0,30 V para direita** e **≥4,90 V para esquerda**, com histerese. É possível movimentar no sentido de afastamento do limite. A barra representa o curso físico, não um círculo de azimutes.

## 4. Primeiro ensaio e ajustes

1. Primeiro alimente o Uno e o sensor, com a alimentação de potência do motor desligada. Confira display, COM e mudança do azimute/barra ao variar o sensor.
2. Depois, com o rotor em posição intermediária, teste brevemente esquerda e direita. Direita deve diminuir a tensão e aumentar a posição mecânica; esquerda deve fazer o contrário. Confira isso antes de solicitar um alvo.
3. Verifique os dois limites eletrônicos e o afastamento de cada limite.
4. Teste um apontamento curto e depois um longo. Observe o ponto em que o rotor começa a reduzir a velocidade e a posição após a parada.
5. Se ultrapassar o alvo por inércia, aumente `AUTO_DESACELERACAO` ou diminua `PWM_MAX`. Se não partir ou travar ao chegar perto do alvo, ajuste `AUTO_PWM_MIN` de acordo com o motor.
6. Teste PARAR, Esc, soltura dos botões, desconexão USB, comando físico durante movimento automático e perda de comunicação.

O botão PARAR desliga o acionamento por software; ele não substitui uma interrupção elétrica da alimentação. O tempo morto de inversão de **100 ms** foi mantido da versão 1.0; confirme se ele atende ao motor e à mecânica antes de inversões frequentes.

### Parâmetros principais no `.ino`

| Constante | Inicial | O que ajustar |
|---|---:|---|
| `AUTO_TOLERANCIA` | 1,0° | Janela de parada; não garante erro final de 1° |
| `AUTO_DESACELERACAO` | 30,0° | Distância de redução do PWM, além da tolerância |
| `AUTO_PWM_MIN` | 70 | Menor PWM usado no automático |
| `AUTO_ACEL_PASSO` | 1 / ciclo | Rapidez da subida do PWM |
| `AUTO_DESACEL_PASSO` | 1 / ciclo | Rapidez da redução do PWM |
| `PWM_MAX` | 220 / 255 | Velocidade máxima; também afeta controle manual |
| `SEM_MOVIMENTO_MS` | 8.000 ms | Falha se a posição não mudar pelo menos 0,5° nesse intervalo |
| `MAX_MOVIMENTO_MS` | 180.000 ms | Limite de tempo de um comando contínuo |
| `LINK_TIMEOUT_MS` | 1.000 ms | Sem contato válido do PC, cancela movimento remoto |
| `JOG_TIMEOUT_MS` | 550 ms | Sem renovação de JOG, cancela o movimento manual remoto |

Se o rotor for muito lento, pode ser necessário aumentar os tempos de detecção de falta de movimento ou de duração máxima. Não configure valores que escondam um travamento da mecânica.

## 5. Falhas e comunicação

- O aplicativo renova PING a cada aproximadamente 200 ms e JOG a cada 150 ms. A janela precisa continuar processando eventos para renovar os comandos.
- O Arduino para o comando remoto se o contato expirar; o JOG também exige sua própria renovação. Voltar a receber PING não retoma o movimento cancelado.
- O controle físico funciona sem computador, inclusive após perda de USB.
- Uma tensão fora de 0,15–4,98 V trava uma falha de sensor. Falta de mudança de posição por 8 s ou movimento contínuo acima de 180 s também travam uma falha.
- Para liberar uma falha, corrija a causa e pressione PARAR. Uma leitura inválida ainda presente não é liberada pelo STOP.
- Leituras dentro da faixa não provam que o potenciômetro esteja funcionando: fio aberto, ruído ou falhas que produzam valores plausíveis precisam de proteção e diagnóstico adicionais no hardware. Esta versão não mede corrente do motor.
- O watchdog reinicia o Uno se o programa deixar de atendê-lo por aproximadamente 1 s. Ao reiniciar, os comandos remotos não são preservados; o aplicativo exige reconexão.

Mensagens comuns: COM ocupada (feche Monitor Serial e outros programas), firmware incompatível (grave o `.ino` 1.1), sem telemetria (confira USB/alimentação), controle local (solte os botões físicos), ou falha (corrija e pressione PARAR).

## 6. Arquivos

- `Arduino/rotor_1_1/rotor_1_1.ino`: firmware completo.
- `Arduino/Original_1.0/rotor_1.0.ino`: arquivo original fornecido, sem modificações.
- `Windows/rotor_pc.py`: programa completo.
- `Windows/*.bat`: instalação, execução, simulação e geração do executável.
- `PROTOCOLO.md`: comandos e telemetria para futuras integrações.
- `VALIDACAO.md`: verificações realizadas e seus limites.
- `Testes`: testes de lógica e transporte para manutenção do código.

Esta versão não implementa protocolo GS-232 nem integração N1MM+. O protocolo USB documentado permite acrescentar essas funções em uma etapa posterior.

Documentação das ferramentas: [pySerial](https://pyserial.readthedocs.io/en/latest/pyserial_api.html) e [PyInstaller](https://www.pyinstaller.org/en/stable/).

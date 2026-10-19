# Validação da versão 1.1 — 10/10/2026

## Verificações realizadas

### Firmware AVR

Correção de compatibilidade com a IDE em 10/10/2026: as assinaturas de `iniciarComando` e `encerrarMovimento` usam `uint8_t`, evitando dependência de enums nos protótipos antecipados gerados pelo Arduino. Os enums internos e o comportamento de movimento foram mantidos. O sketch corrigido passou pelo pré-processamento do Arduino CLI; o C++ produzido por essa etapa foi compilado e ligado para o Uno.

O sketch completo foi compilado e ligado para **ATmega328P / Uno de 16 MHz**, com o núcleo Arduino AVR 1.8.6, avr-gcc 7.3.0-atmel3.6.1-arduino7, Adafruit GFX 1.12.6, Adafruit ST7735/ST7789 1.11.0 e Adafruit BusIO 1.17.4. A compilação de verificação usou otimização `-Os`, seções de funções/dados e descarte de seções não utilizadas, **sem LTO**.

- Programa: **25.110 bytes**.
- Dados estáticos: **1.030 bytes**, de 2.048 bytes de SRAM.

Esses números não incluem o uso dinâmico de pilha/heap durante operação. A compilação padrão pela IDE com LTO não foi concluída neste ambiente: a ferramenta de otimização encerrou com falha interna. A verificação sem LTO confirma compilação, ligação e adequação de tamanho do código para o chip, mas o usuário ainda deve compilar pela sua IDE e testar a placa.

### Lógica do `.ino` real

O próprio sketch foi incluído e compilado com g++ nativo, substituindo somente Arduino, display e serial por IO de teste. Foram aprovados **17 cenários**:

1. Rampa manual local e parada ao soltar.
2. JOG remoto com renovação, preservando a rampa.
3. Expiração de JOG mesmo com PING presente.
4. Expiração de contato no automático, sem retomada pelo PING.
5. Aceleração, PWM máximo, redução próxima do alvo e parada no automático.
6. Escolha do Norte próximo e uso da sobreposição acessível.
7. Recusa de caminho circular que excederia o curso mecânico.
8. Tempo morto de inversão inclusive depois de STOP seguido de JOG contrário.
9. Prioridade física e cancelamento definitivo do alvo remoto.
10. Parada com os dois botões físicos e liberação ao soltar ambos.
11. Ambos os limites eletrônicos, permitindo afastamento do limite.
12. Falha de sensor travada, com liberação apenas após leitura válida e STOP.
13. Falha por falta de mudança de posição.
14. Limite de duração de movimento contínuo.
15. STOP durante botão físico pressionado, sem religamento até soltar.
16. Rejeição de ângulos inválidos, NaN, infinito, linhas longas e fragmentos antigos.
17. Emissão da telemetria no protocolo especificado.

O stub de PWM verifica em toda escrita que as saídas de sentidos opostos não fiquem simultaneamente energizadas. A simulação mecânica é simplificada; não foi usada para afirmar a precisão física do rotor.

### Programa do computador

- Verificação de sintaxe do Python.
- Sete testes automatizados aprovados: validação de ângulos, telemetria, controle da simulação, prioridade do STOP na fila, identificação serial, reinicialização do Arduino e fragmentação de pacotes.
- Os testes do transporte usaram **pySerial real** e uma porta pseudo-terminal Linux. Confirmaram que o worker serial não mantém PING automaticamente.
- A interface Tk foi aberta em display virtual e testada com conexão simulada, JOG, soltura, apontamento, STOP e desconexão. Foi feita inspeção visual do layout.

## Ajuste da desaceleração após o primeiro ensaio físico

Em 10/10/2026, após relato de desaceleração brusca, `AUTO_DESACELERACAO` passou de 15° para 30° e `AUTO_DESACEL_PASSO` de 4 para 1. A demonstração do PC foi ajustada para corresponder a esses parâmetros. Na nova configuração foram repetidos e aprovados os cenários de perfil automático, apontamento próximo ao Norte e expiração de contato. Os sete testes Python também passaram. O sketch atualizado foi novamente pré-processado pelo Arduino CLI e compilado/ligado para Uno sem LTO; os valores de memória acima correspondem a esse ajuste. A suavidade física ainda precisa de ensaio no rotor.

## Limites desta validação

Não houve acesso ao rotor, ao Arduino físico nem a uma máquina Windows. Não foi gerado ou ensaiado um `.exe` Windows neste ambiente. Os scripts de instalação/empacotamento estão incluídos; a execução no Windows e o ensaio do mecanismo são as próximas verificações necessárias.

Não foram medidos corrente, torque, frenagem, ruído de ADC, erro final nem tempo de parada do rotor. As distâncias de desaceleração, PWM mínimo, tolerância e prazos de proteção são parâmetros iniciais para ajuste em bancada.

## Repetir os testes de manutenção

Na raiz do pacote, com Python, pySerial e g++ instalados:

```
python3 -m unittest discover -s Testes -v
python3 Testes/executar_firmware.py
```

Em Windows, use `py -3` no lugar de `python3`. Os três testes de pseudo-terminal são específicos de POSIX e serão ignorados no Windows. Os demais testes Python podem ser executados no Windows. O teste C++ precisa de g++ (por exemplo, MinGW); isso não é necessário para usar o aplicativo nem para gravar pela IDE Arduino.

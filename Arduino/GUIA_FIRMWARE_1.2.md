# Rotor — Mario Pin / PU2PTU · firmware 1.2

A versão 1.2 mantém pinos, calibração, limites e rampas da 1.1, acrescentando um teto global de PWM salvo na EEPROM e ajuste pelos dois botões. É a versão usada pela interface Windows 1.3.0, com protocolo serial 2. Os sketches anteriores estão preservados.

## Gravar

1. Abra `Arduino/rotor_1_2/rotor_1_2.ino` na IDE Arduino e selecione **Arduino Uno** e a COM correta.
2. Instale **Adafruit GFX Library**, **Adafruit ST7735 and ST7789 Library** e **Adafruit BusIO**. EEPROM, SPI e Wire são do pacote AVR.
3. Compile e grave. Não é necessário alterar ligações para esta atualização.
4. Feche o Monitor Serial antes de conectar pelo Windows 1.3.0. A porta reinicia o Uno; aguarde identificação e limite de velocidade.

O watchdog de aproximadamente 1 s continua exigindo Uno com bootloader compatível, como Optiboot.

## Ligações preservadas

| Função | Pino / ligação |
|---|---|
| Potenciômetro: cursor | A0 |
| Referência do potenciômetro | 5 V e GND; calibração VREF=5,00 V |
| Botão esquerda | D2 para GND, INPUT_PULLUP |
| Botão direita | D4 para GND, INPUT_PULLUP |
| BTS7960 RPWM / LPWM | D3 / D5 |
| BTS7960 R_EN / L_EN | 5 V na montagem existente |
| ST7789 CS / DC / RST | D10 / D9 / D8 |
| ST7789 MOSI / SCK | D11 / D13, SPI do Uno |
| GND | Comum entre Uno e lógica do driver |

Mantenha a alimentação e os níveis lógicos do display já usados na montagem; a tabela não autoriza aplicar 5 V em um display que exija 3,3 V. A potência do motor continua na entrada própria do BTS7960.

## Ajustar velocidade no display

Com o rotor **já parado**, mantenha ambos os botões por aproximadamente dois segundos. O pequeno intervalo inicial de reconhecimento do par evita um pulso do motor ao tentar abrir o menu.

Na tela **CONFIGURACAO / VELOCIDADE MAXIMA**, solte ambos os botões antes de editar. Cada toque em ESQ diminui um nível; DIR aumenta. Não há repetição automática por manter pressionado. Pressione ambos para confirmar e salvar; solte-os antes de voltar a movimentar.

Se ambos forem pressionados durante movimento, o rotor para imediatamente e permanece bloqueado até soltura. Esse gesto não se transforma em configuração por continuar segurando. Para entrar no menu, solte e faça uma nova pressão com o rotor parado.

Dentro do menu, PWM fica desligado e JOG/MOVE remotos são rejeitados. STOP permanece funcional, sem fechar o menu. A tela normal mostra `MAX n/6`; ao sair, os valores normais são redesenhados.

| Nível | PWM máximo / 255 |
|---|---:|
| 1 | 70 |
| 2 | 90 |
| 3 | 110 |
| 4 | 140 |
| 5 | 175 |
| 6 | 220 |

O teto vale para botões físicos, JOG USB e automático. Diminuir durante movimento corta imediatamente o excesso; aumentar permite subida gradual. Os níveis limitam PWM, não medem graus por segundo.

## Persistência e Windows

São usados os primeiros 12 bytes da EEPROM, em dois registros alternados de seis bytes, com assinatura, sequência, nível, complemento, checksum e versão. A assinatura é escrita por último. Uma escrita interrompida conserva o outro registro válido; o teste cobre a volta do contador de sequência. Salvar o mesmo nível não regrava.

EEPROM virgem inicia em 6 para preservar o máximo anterior. Se nenhum registro for válido e a área não estiver virgem, o limite passa a 1. Gravar um novo sketch normalmente preserva EEPROM; confira o nível mostrado após atualizar.

Ao conectar, o Windows lê o nível real do Arduino; não restaura um valor antigo do computador. Alterações locais são publicadas periodicamente pela serial. A escrita remota de velocidade é bloqueada durante o menu; consultas continuam disponíveis. O protocolo está em `PROTOCOLO.md`.

## Movimento e proteções mantidas

- Manual: níveis 70, 90, 110, 140, 175 e 220 a intervalos de aproximadamente 0,5 s, até o teto escolhido. Soltar desliga PWM imediatamente.
- Automático: PWM mínimo 70, subida/redução de 1 por ciclo de cerca de 20 ms, desaceleração proporcional nos 30° além da tolerância de 1°; corte ao atingir/cruzar o alvo. O ajuste do corte final não foi alterado.
- Calibração: 4,80 V=primeiro Norte e 0,40 V=segundo Norte; direita diminui tensão e aumenta posição mecânica.
- Limites: direita bloqueada em ≤0,30 V; esquerda em ≥4,90 V, com histerese. O afastamento do limite continua permitido.
- Alvo equivalente mais próximo dentro da sobreposição, aproximadamente −4,1° a 364,1°; 0° e 360° indicam o mesmo azimute.
- Botões físicos assumem prioridade e cancelam alvo remoto. Retornar o contato não retoma movimento anterior.
- Link remoto: prazo de 1.000 ms; renovação específica JOG antes de 550 ms.
- Falhas travadas: sensor fora de 0,15–4,98 V, ausência de mudança de 0,5° em 8 s, ou movimento contínuo maior que 180 s. Corrija a causa e pressione PARAR; sensor ainda inválido continua travado.
- Tempo morto de inversão de 100 ms e watchdog de aproximadamente 1 s preservados.

Com as entradas de habilitação ligadas a 5 V na montagem BTS7960, ambos os PWMs em zero podem produzir frenagem dinâmica; não se deve presumir roda livre. Esta versão não acrescenta controle de corrente, freio independente ou sensor de temperatura.

## Primeiro ensaio

1. Com potência do motor desligada, confira azimute, limites, tela normal e entrada/saída do menu. Verifique que nenhum PWM é aplicado durante configuração.
2. Escolha nível 1, salve, reinicie e confirme o mesmo nível no display e ao conectar pelo Windows.
3. Em posição intermediária, aplique potência e faça pulsos curtos ESQ/DIR. Direita deve diminuir tensão e aumentar posição mecânica.
4. Teste ambos durante movimento, soltura, PARAR, perda de USB, fim de curso e retorno do limite.
5. Teste apontamento curto em nível 1 e avance gradualmente. Compare níveis e reduza o teto durante um movimento de bancada.
6. Verifique que um ajuste local aparece no PC e que reconectar não o substitui por outro valor.

A velocidade e a precisão dependem de motor, alimentação, carga, folga e inércia; décimos no display não garantem precisão física. PARAR é um comando de software. Os ensaios automatizados e a compilação estão em `VALIDACAO_FIRMWARE_1.2.md`; não substituem o teste no equipamento.

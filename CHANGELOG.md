# Histórico

As versões do aplicativo Windows e do firmware são independentes.

## Windows 1.3.0 / firmware 1.2 — 20/10/2026

- Coluna de comandos reduzida de 390 para 234 px, com rolagem quando necessário.
- Configuração da estação e abertura total −3 dB dentro da janela principal.
- Português, inglês, espanhol, alemão e russo com seleção por bandeiras e idioma salvo.
- Limite de PWM em seis níveis na interface, aplicado globalmente pelo Arduino.
- Menu local com ambos os botões por dois segundos, ajuste ESQ/DIR, confirmação conjunta e bloqueio até soltura.
- Dois botões durante movimento continuam parando imediatamente, sem abrir o menu.
- Persistência EEPROM com dois registros e sincronização do nível ao conectar.
- Protocolo 2 com SPEED?, SPEED,n e novo estado de configuração; exige atualizar aplicativo e firmware juntos.
- Instalador Windows 1.3.0 mantendo o host e os ícones da correção 1.2.1.
- Novos testes de idiomas, interface, comunicação, limites e EEPROM; sketches antigos preservados.

## Windows 1.2.1

- Correção da aplicação do ícone ao título da janela e à barra de tarefas.
- Executável de inicialização `Rotor_PU2PTU.exe` com ícone e metadados próprios.
- Aplicação dos ícones pequeno e grande ao HWND externo do Tk.
- Atalhos atualizados e log de inicialização para diagnóstico.

## Windows 1.2

- Mapa OpenStreetMap centrado na estação e escala ajustável.
- Estação definida por coordenadas ou grid locator.
- Cone transparente de apontamento, com largura total de −3 dB e opacidade configuráveis.
- Cálculo de direção/distância e apontamento por grid de até 6 caracteres.
- Ícone do aplicativo e instalador com runtime incluído.

## Firmware 1.1 e interface USB

- Comunicação serial para identificação, telemetria, JOG, STOP e MOVE.
- Controle remoto com prioridade dos botões físicos e parada por perda de comunicação.
- Aceleração e desaceleração para apontamento automático.
- Ajuste da aproximação para 30° e passo de redução de PWM 1.
- Correção dos protótipos automáticos de funções na IDE Arduino.

## Firmware 1.0

- Versão original fornecida pelo autor, preservada no repositório.

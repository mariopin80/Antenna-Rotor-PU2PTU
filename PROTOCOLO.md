# Protocolo USB — Rotor PU2PTU 1.1

115200 baud, 8 bits, sem paridade, 1 stop bit, sem controle de fluxo. Texto ASCII; cada comando termina em LF (`\n`); CR anterior é ignorado. Até 39 caracteres por linha. Não use vírgula decimal no protocolo; a interface converte para ponto.

## Comandos

| Linha | Ação / resposta |
|---|---|
| `HELLO` | Responde `ROTOR,1,1.1`: produto, versão do protocolo, versão do firmware |
| `PING` | Renova contato do computador, sem resposta e sem iniciar movimento |
| `STOP` | Cancela comando, desliga PWM e responde `OK,STOP`. Falha de sensor persistente permanece travada |
| `JOG,L` | Gira para esquerda; renovar em intervalos menores que 550 ms |
| `JOG,R` | Gira para direita; renovar em intervalos menores que 550 ms |
| `MOVE,135.5` | Aponta automaticamente; responde `OK,MOVE`. Manter PING para renovar contato |

JOG e MOVE válidos também renovam contato. HELLO e comandos inválidos não renovam. Erros: `ERR,ANGLE`, `ERR,LOCAL`, `ERR,FAULT`, `ERR,COMMAND`, `ERR,LINE`. Linhas muito longas, caracteres de controle e fragmentos que ficam incompletos por mais de 250 ms são descartados até o próximo LF. Os comandos não usam IDs de transação nem checksum; o transporte é USB serial local. Não há confirmação individual de JOG ou PING.

Na inicialização o Uno envia `BOOT,1.1` e `ROTOR,1,1.1`. A identificação em resposta a HELLO pode se repetir normalmente. BOOT após conectar significa reinicialização da placa; o aplicativo encerra a conexão.

## Telemetria periódica

Aproximadamente 10 linhas por segundo:

```
STAT,120.0,120.0,34.1,0,0,0,NA,0,0
```

| Campo após STAT | Significado |
|---|---|
| 1 | Azimute filtrado em graus, 0 a 360 |
| 2 | Posição mecânica atual em graus, sem redução módulo 360 |
| 3 | Posição na barra em %, esquerda = 0, direita = 100 |
| 4 | Modo: 0 parado; 1 local; 2 JOG USB; 3 automático USB; 4 falha travada |
| 5 | Motor: −1 esquerda; 0 parado; +1 direita |
| 6 | PWM aplicado, 0 a 220 na configuração inicial |
| 7 | Alvo mecânico do modo automático, ou NA |
| 8 | Fim de curso: −1 baixa tensão/direito; 0 normal; +1 alta tensão/esquerdo |
| 9 | Motivo: 0 operador; 1 alvo; 2 limite; 3 link; 4 sensor; 5 travamento; 6 tempo; 7 local; 8 dois botões |

Exemplo em movimento automático perto do primeiro Norte:

```
STAT,359.0,-1.0,1.9,3,-1,70,-2.0,0,0
```

Alvos podem usar a pequena sobreposição mecânica. Use campo 2 para calcular distância física e campo 1 para exibir apontamento cardinal. O movimento remoto requer contato contínuo e é cancelado quando o prazo expira; PING não o retoma.

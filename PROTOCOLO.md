# Protocolo USB 2 — Rotor PU2PTU / firmware 1.2

115200 baud, 8 bits, sem paridade, 1 stop bit, sem controle de fluxo. Texto ASCII com LF (`\n`); CR anterior é ignorado. Até 39 caracteres por linha. Números usam ponto decimal.

## Comandos

| Linha | Ação / resposta |
|---|---|
| `HELLO` | `ROTOR,2,1.2`, seguido de `SPEED,n` |
| `PING` | Renova contato do computador, sem resposta ou movimento |
| `STOP` | Cancela movimento e desliga PWM; `OK,STOP`. Não fecha o menu local e não libera sensor ainda inválido |
| `JOG,L` / `JOG,R` | Manual USB; renovar antes de 550 ms |
| `MOVE,135.5` | Automático; `OK,MOVE`; manter contato via PING |
| `SPEED?` | Consulta o nível salvo; responde `SPEED,n` |
| `SPEED,n` | Salva nível inteiro 1–6, confirma `OK,SPEED` e `SPEED,n`; não inicia movimento |

`n` deve ser exatamente um dígito de 1 a 6, sem espaços, casas decimais ou zeros à esquerda. Níveis e PWM máximos: 1=70, 2=90, 3=110, 4=140, 5=175, 6=220. O teto é aplicado no Arduino a todos os modos. Reduzi-lo corta imediatamente o excesso de PWM; elevar permite subida gradual.

Apenas JOG/MOVE válidos e PING renovam o contato remoto. HELLO, consultas, alterações de velocidade e comandos inválidos não prolongam movimento remoto. Não há IDs de transação nem checksum no transporte USB local; JOG e PING não têm confirmação individual.

Erros: `ERR,ANGLE`, `ERR,SPEED`, `ERR,LOCAL`, `ERR,FAULT`, `ERR,CONFIG`, `ERR,COMMAND`, `ERR,LINE`. No menu local, JOG, MOVE e escrita SPEED são rejeitados com CONFIG; SPEED? e STOP continuam disponíveis. Botões físicos têm prioridade sobre movimento remoto.

Linhas longas, caracteres de controle ou fragmentos incompletos por mais de 250 ms são descartados até o próximo LF.

Ao iniciar, o Uno envia `BOOT,1.2`, `ROTOR,2,1.2` e o nível. Uma resposta HELLO repetida é normal; BOOT após conexão estabelecida significa reinício e exige nova conexão. O aplicativo Windows 1.3.0 exige identidade `ROTOR,2,1.2` e lê SPEED antes de habilitar comandos. Não aplica configuração de velocidade armazenada no PC.

## Telemetria

STAT continua com os mesmos nove campos, cerca de 10 vezes por segundo:

```text
STAT,120.0,120.0,34.1,0,0,0,NA,0,0
```

| Campo após STAT | Significado |
|---|---|
| 1 | Azimute filtrado em graus, 0–360 |
| 2 | Posição mecânica contínua em graus |
| 3 | Posição na barra em %, esquerda=0, direita=100 |
| 4 | Modo: 0 parado; 1 local; 2 JOG USB; 3 automático USB; 4 falha; **5 configuração local** |
| 5 | Motor: −1 esquerda; 0 parado; +1 direita |
| 6 | PWM aplicado; nunca supera o teto do nível salvo |
| 7 | Alvo mecânico do automático, ou NA |
| 8 | Fim de curso: −1 baixa tensão/direito; 0 normal; +1 alta tensão/esquerdo |
| 9 | Motivo: 0 operador; 1 alvo; 2 limite; 3 link; 4 sensor; 5 travamento; 6 tempo; 7 local; 8 dois botões; **9 configuração local** |

Uma linha independente `SPEED,n` é enviada aproximadamente a cada segundo e ao alterar o nível/consultar. Ela evita mudar a estrutura STAT e sincroniza alterações feitas pelos botões.

Alvos podem usar a pequena sobreposição mecânica. Use posição mecânica para distância física e azimute para indicação cardinal. O prazo de contato remoto expira em 1.000 ms; PING posterior não retoma um comando cancelado. O ajuste de velocidade não altera o destino nem remove os limites de curso.

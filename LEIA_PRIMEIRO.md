# Rotor PU2PTU — Windows 1.3.0 / Arduino 1.2

Autor: Mario Pin – PU2PTU

A versão 1.3.0 traz coluna de comandos mais estreita, configuração de estação na própria janela, cinco idiomas e limite global de velocidade. O firmware 1.2 permite ajustar esse limite também pelos dois botões físicos e o mantém salvo sem computador.

## Instalar ou atualizar

1. Feche o aplicativo aberto.
2. Grave `Arduino/rotor_1_2/rotor_1_2.ino` na placa **Arduino Uno**, conforme `Arduino/GUIA_FIRMWARE_1.2.md`.
3. Execute **Rotor_PU2PTU_1.3.0_Setup_x64.exe** em Windows 10/11 x64. Use a mesma pasta para atualizar.
4. Abra pelo atalho **Rotor PU2PTU**. Para experimentar sem Arduino, use **Rotor PU2PTU - Simulacao** no menu Iniciar.
5. Selecione a COM e conecte. Feche antes o Monitor Serial da IDE. Aguarde a identificação e a leitura do limite salvo.

O aplicativo 1.3.0 exige o firmware 1.2 e protocolo 2. A interface antiga 1.2.1 não é compatível com esse novo protocolo. O instalador inclui Python, Tcl/Tk e as bibliotecas, mas não grava o Arduino.

A pasta inicial é `%LOCALAPPDATA%\Programs\RotorPU2PTU`, por usuário. As configurações anteriores são reutilizadas em `%APPDATA%\RotorPU2PTU`; o desinstalador preserva essa pasta. Não é necessário Python instalado para usar o instalador.

Para executar pelos fontes, instale Python 3.11/3.12 com Tcl/Tk e execute `Windows/INSTALAR.bat`, depois `Windows/INICIAR.bat` ou `Windows/SIMULAR.bat`.

## Painel de comandos e idiomas

A coluna esquerda tem 234 px, 60% dos 390 px anteriores. ESQ, PARAR e DIR continuam lado a lado. Em janelas baixas o painel pode ser rolado para alcançar os itens inferiores. O mapa aproveita a largura restante.

As pequenas bandeiras no canto inferior direito selecionam inglês (EUA), português (Brasil), espanhol (Espanha), alemão (Alemanha) e russo (Rússia). A troca é imediata e não apaga campos em edição. O idioma fica salvo entre execuções; os códigos do protocolo e os dados da estação independem dele.

## Configurar a estação e o feixe

Clique **Configurar estação** no alto do mapa. O formulário aparece na própria janela, no lugar do mapa, e contém:

- Nome ou indicativo da estação.
- Coordenadas WGS84 em graus decimais, com Sul e Oeste negativos; aceita ponto ou vírgula.
- Alternativa por grid Maidenhead de 2, 4 ou 6 caracteres, como `GG66dr`; usa o centro da célula.
- **Abertura total do feixe −3 dB**, de 1° a 360°. Por exemplo, 60° corresponde a ±30° em relação ao centro.

**Aplicar configuração** salva e volta ao mapa. **Cancelar / Voltar ao mapa** descarta as alterações do formulário. Abrir a configuração solicita parada; aplicar os campos não movimenta o rotor. O formulário impede comandos de movimento enquanto estiver aberto.

A estação permanece no centro e o Norte fica para cima. A calibração do rotor deve usar Norte verdadeiro para coincidir com o mapa. Estação, feixe, raio, opacidade, último grid e idioma ficam em `%APPDATA%\RotorPU2PTU\mapa.json`.

## Velocidade máxima

Escolha **Velocidade máxima** na coluna esquerda. O valor só é considerado confirmado após a resposta do Arduino. O mesmo limite vale para controle manual no PC, botões físicos e automático.

| Nível | PWM máximo / 255 |
|---|---:|
| 1 | 70 |
| 2 | 90 |
| 3 | 110 |
| 4 | 140 |
| 5 | 175 |
| 6 | 220 |

Diminuir o limite durante movimento reduz imediatamente o PWM que estiver acima dele. Aumentá-lo libera uma subida gradual. O limite representa PWM, e não graus por segundo medidos: carga e alimentação influenciam a velocidade real.

O valor é salvo na EEPROM do Arduino e reaplicado após ligar. Ao conectar, o Windows consulta esse valor e não envia um ajuste antigo do PC. Uma alteração feita no display aparece também no Windows. A seleção fica indisponível enquanto o Arduino está em configuração local, controle físico ou falha. Se a confirmação de uma alteração não chegar, o aplicativo encerra a conexão e pede reconexão para conferir o valor real.

### Ajuste pelos dois botões do Arduino

1. Com o rotor já parado, mantenha **os dois botões pressionados por aproximadamente 2 s**.
2. Na tela de configuração, solte ambos antes de editar.
3. Pressione ESQ para diminuir ou DIR para aumentar; cada toque muda um nível, entre 1 e 6.
4. Pressione ambos para salvar e sair. Solte os dois antes de voltar a movimentar.

Pressionar ambos **durante movimento** para imediatamente. Continuar segurando nessa situação não abre o menu: é necessário soltar e iniciar uma nova pressão com o rotor já parado. Dentro do menu nenhum comando de movimento é aceito, e PARAR continua disponível sem fechar a configuração.

Um Uno com EEPROM sem uso começa no nível 6, igual ao máximo anterior. Se os registros de configuração estiverem inválidos, o firmware adota nível 1. A gravação usa dois registros alternados; salvar o mesmo nível não regrava a EEPROM. O guia do firmware detalha o procedimento de ensaio.

## Escala e cone no mapa

**Raio (km)** define a distância de referência entre 1 e 3.000 km. Selecione um valor ou digite e aplique. **+ / −** e a roda do mouse aproximam/afastam mantendo a estação no centro. A projeção Web Mercator aceita estação entre −85° e +85° de latitude.

O cone azul acompanha o azimute atual recebido do Arduino. A linha central indica o eixo e a largura representa a abertura total configurada na estação. A opacidade começa em 22% e pode ser ajustada de 5% a 60% no mapa. Sem telemetria válida, o cone é ocultado; em simulação segue o rotor simulado.

A extensão do cone acompanha o raio de referência do mapa. Não é uma previsão de alcance, cobertura, propagação ou sinal, e não inclui lóbulos secundários nem um diagrama medido da antena.

## Apontar por ângulo ou grid

Digite um ângulo de 0° a 360° e pressione **APONTAR** ou Enter no campo. Para grid:

1. Configure a estação.
2. Digite um destino Maidenhead de até 6 caracteres e clique **Calcular**. Isso só calcula azimute e distância.
3. Confira o resultado e clique **APONTAR PARA O GRID**.

O cálculo usa a menor geodésica WGS84 até o centro da célula. O destino aparece em laranja; o cone continua mostrando o apontamento atual. Grids mais curtos representam áreas maiores. Um destino coincidente com a estação é rejeitado por não definir direção. O cálculo funciona sem internet.

ESQ/DIR giram enquanto pressionados. Soltar, retirar o mouse ou perder o foco interrompe o JOG. PARAR e Esc cancelam o movimento. As setas do teclado dentro de campos de edição não comandam o rotor. Limites, escolha do caminho mecânico, rampas e tempo máximo são aplicados pelo firmware.

## Mapas, conexão e ícone

A porta pode reiniciar o Uno ao abrir. O aplicativo espera a identificação, solicita parada e lê o limite antes de habilitar movimento; um alvo anterior nunca é retomado automaticamente.

Os mosaicos OpenStreetMap são carregados por duas threads independentes da comunicação serial. O cache local mantém imagens por pelo menos sete dias e revalida por HTTP. Somente a vista atual é solicitada, sem download antecipado de regiões. Sem rede, mosaicos disponíveis continuam aparecendo; áreas ausentes são sinalizadas. O controle USB continua funcionando. O cache não acompanha o pacote, e a atribuição permanece visível no mapa.

O instalador mantém o host `Python/Rotor_PU2PTU.exe`, ícone próprio nos atalhos e aplicação explícita dos ícones pequeno/grande ao título da janela. Erros de inicialização ficam em `%APPDATA%\RotorPU2PTU\startup.log`. A receita está em `Windows/Instalador/REBUILD.md`.

## Arquivos e validação

| Arquivo | Função |
|---|---|
| `Windows/rotor_pc.py` | Interface e comunicação |
| `Windows/rotor_i18n.py` | Traduções e bandeiras |
| `Windows/rotor_map.py` | Mapa, configuração e cache |
| `Windows/rotor_geo.py` | Grid, projeção e geodésicas |
| `Windows/rotor_windows.py` | Identidade e ícones nativos |
| `Arduino/rotor_1_2/rotor_1_2.ino` | Firmware completo desta versão |
| `Arduino/GUIA_FIRMWARE_1.2.md` | Ligações, operação local e ensaio |
| `VALIDACAO.md` | Resultados e limites dos testes |

A interface, o protocolo e a lógica foram testados em Linux; o firmware compilou para Uno. O equipamento físico e o Windows não estavam disponíveis nesta preparação. O ajuste do corte final de PWM discutido anteriormente não foi alterado nesta atualização.

Dados de mapa: [OpenStreetMap contributors](https://www.openstreetmap.org/copyright). Avisos de terceiros: `Windows/Instalador/CREDITOS.txt`.

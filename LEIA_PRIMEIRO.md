# Rotor PU2PTU — Windows 1.2.1

Autor: Mario Pin – PU2PTU

A versão 1.2.1 corrige a identificação visual no Windows: ícone do rotor no título da janela, na barra de tarefas e nos atalhos. Mantém o mapa OpenStreetMap, feixe transparente, estação e apontamento por grid locator da versão 1.2. O firmware continua sendo 1.1.

## Instalar ou atualizar

1. Feche o Rotor aberto.
2. Execute **Rotor_PU2PTU_1.2.1_Setup_x64.exe** em Windows 10/11 de 64 bits e instale sobre a versão anterior, usando a mesma pasta.
3. Mantenha **Atalho na área de trabalho** selecionado. Abra pelo atalho novo **Rotor PU2PTU**.
4. Se o ícone antigo do Python estiver fixado na barra de tarefas, desafixe-o. Depois de abrir pelo novo atalho, fixe a nova entrada do Rotor se desejar.

O instalador inclui Python e todas as bibliotecas. Há também o atalho **Rotor PU2PTU - Simulacao** no menu Iniciar, que abre sem comandar o Arduino. A instalação funciona sem internet; novas áreas do mapa exigem acesso à rede.

A pasta inicial é `%LOCALAPPDATA%\Programs\RotorPU2PTU`, para o usuário atual. Estação, escala e demais configurações existentes são reutilizadas em `%APPDATA%\RotorPU2PTU`. O desinstalador permanece em Configurações → Aplicativos.

Para executar os fontes, instale Python 3.11/3.12 com Tcl/Tk, execute `Windows/INSTALAR.bat` e depois `Windows/INICIAR.bat` ou `Windows/SIMULAR.bat`. A instalação de dependências por essa alternativa exige internet.

## Configurar a estação

Clique **Configurar estação** no alto do mapa. Há duas opções:

- Coordenadas WGS84 em graus decimais, com Sul e Oeste negativos. Aceita ponto ou vírgula decimal nos campos separados.
- Grid locator Maidenhead com 2, 4 ou 6 caracteres, como `GG66dr`. Nesse caso é usado o **centro da célula**, e não uma posição exata dentro dela.

O nome/indicativo é apenas uma identificação no mapa. A estação fica sempre no centro; o mapa mantém o Norte para cima. Para os azimutes do rotor e do mapa coincidirem, a calibração do rotor deve usar Norte verdadeiro.

As configurações da estação, abertura do feixe, raio, opacidade e último grid são salvas entre execuções. No Windows ficam em `%APPDATA%\RotorPU2PTU\mapa.json`.

## Escala do mapa

O campo **Raio (km)** define a distância de referência que cabe na vista, entre 1 e 3.000 km. A lista oferece valores comuns; também é possível digitar outro valor e clicar **Aplicar**. Os botões **+ / −** e a roda do mouse aproximam/afastam mantendo a estação no centro.

O círculo geodésico desse raio cabe na área visível; a janela pode mostrar áreas adicionais nas laterais. A barra de escala no mapa mostra a distância local. A projeção do mapa é Web Mercator e não cobre os polos; a estação aceita latitudes entre −85° e +85°.

## Cone de apontamento

No campo **Feixe −3 dB (°)**, informe a **largura angular total do feixe no plano horizontal**, entre os dois pontos a −3 dB. Exemplo: um feixe de 48° tem bordas a ±24° do eixo de apontamento.

- O cone azul acompanha o **azimute atual recebido do Arduino**, o mesmo exibido no painel esquerdo.
- A opacidade inicial é 22%. O controle inferior permite ajustar entre 5% e 60%, mantendo o mapa legível por baixo.
- A linha central azul indica o eixo do feixe. O cone não é uma estimativa de propagação, cobertura, sinal ou alcance: sua extensão acompanha apenas o raio de referência do mapa.
- Sem telemetria válida ou após desconectar, o cone é ocultado. Em SIMULAÇÃO ele acompanha o rotor simulado, identificado na janela.

A abertura configurada é uma representação angular simplificada; não representa lóbulos laterais/traseiros nem um diagrama de radiação medido.

## Apontar por grid locator

1. Configure a estação.
2. Digite o grid de destino no painel esquerdo, com até 6 caracteres.
3. Clique **Calcular** para obter azimute verdadeiro e distância até o **centro** do grid. Isso não movimenta o rotor.
4. Confira o resultado e clique **APONTAR PARA O GRID** para enviar o azimute ao Arduino.

O destino aparece em laranja, com uma linha tracejada até ele. O cone azul continua mostrando o apontamento atual, permitindo acompanhar a aproximação ao destino. Quando o destino fica fora da escala, aparece a indicação **fora da vista**; a estação permanece no centro. A posição de destino não exige internet para o cálculo.

O cálculo usa a menor geodésica no elipsoide WGS84. O grid é normalizado automaticamente, por exemplo `gg66DR` vira `GG66dr`. Um grid igual à posição central da estação é rejeitado por não definir uma direção. Grids de 2 ou 4 caracteres representam áreas maiores e dão um apontamento mais aproximado para uma estação real desconhecida dentro da célula.

A caixa de ângulo e o botão APONTAR continuam disponíveis. ESQ/DIR funcionam enquanto pressionados; PARAR e Esc cancelam o movimento. A escolha do caminho mecânico, os limites e a aceleração/desaceleração continuam a cargo do firmware.

## Conexão e mapas

Selecione a COM e clique **Conectar**. Feche antes o Monitor Serial da IDE Arduino. Ao abrir a porta, o Uno pode reiniciar; aguarde a identificação do firmware.

Os mosaicos do OpenStreetMap são carregados em duas threads, separados da interface serial. Somente os tiles da vista atual são solicitados. O programa mantém cache local por pelo menos sete dias e usa requisições condicionais para renovar imagens antigas. Não há download antecipado de regiões ou mapas offline. O cache não é incluído neste pacote.

Se a internet falhar, áreas já disponíveis podem continuar aparecendo; as partes ausentes são sinalizadas. O comando do rotor e os cálculos de grid continuam funcionando independentemente da rede. A atribuição ao OpenStreetMap fica visível na parte inferior do painel.

## Ícone e instalador Windows

Os atalhos desta versão abrem `Python/Rotor_PU2PTU.exe`, um host GUI com nome, descrição, versão e os sete tamanhos do ícone do rotor incorporados. Ele deriva de uma cópia de `pythonw.exe`, preservando seu código e suas importações; o original também permanece incluído. Essa identificação vale para o processo em execução, além do arquivo de atalho.

Na janela, `rotor_windows.py` aplica o ICO explicitamente ao Tk e, pela API do Windows, os ícones pequeno e grande ao HWND externo que possui a barra de título. A aplicação é repetida quando a janela aparece. Os ícones nativos permanecem alocados enquanto a janela existir. A falha de um carregador de imagem não impede o outro, e eventuais erros são registrados em `%APPDATA%\RotorPU2PTU\startup.log`.

A versão 1.2 anterior foi executada pelo operador, que identificou os ícones genéricos no título e na barra de tarefas. O instalador 1.2.1 foi compilado e conferido em Linux; **a exibição final no Windows ainda precisa ser confirmada**. O teste de GUI e comunicação em Linux não substitui essa confirmação.

A receita de build está em `Windows/Instalador/REBUILD.md`. O manifesto registra os hashes do instalador e do host. O script `Windows/GERAR_EXE.bat` para PyInstaller também permanece disponível.

## Arquivos principais

| Arquivo | Função |
|---|---|
| `Windows/rotor_pc.py` | Interface e comunicação serial |
| `Windows/rotor_map.py` | Mapa, cone, configuração e cache |
| `Windows/rotor_windows.py` | Ícones da janela e identidade do processo Windows |
| `Windows/rotor_geo.py` | Grid locator, projeção e geodésicas |
| `Windows/assets/rotor_icon.ico` | Ícone Windows em múltiplos tamanhos |
| `Windows/Instalador/` | Fontes do instalador, receita de build e manifesto |
| `Windows/GERAR_INSTALADOR.bat` | Recria o instalador no Windows |
| `Windows/assets/ICON.md` | Descrição e prompt do ícone |
| `Interface_1.2.png` | Prévia da disposição da interface 1.2 com estação e rotor simulados |
| `VALIDACAO.md` | Verificações desta versão |
| `Arduino/` | Firmware e documentos anteriores, preservados |
| `Testes/` | Testes de cálculo, cache, interface e comunicação |

O firmware incluído é exatamente o anterior, com aproximação de 30° e passo de redução de PWM 1. Esta atualização não altera o corte final do PWM mínimo; o ajuste do pequeno tranco discutido anteriormente permanece separado.

Fontes e créditos: [OpenStreetMap](https://www.openstreetmap.org/copyright), [política de tiles](https://operations.osmfoundation.org/policies/tiles/), [GeographicLib](https://geographiclib.sourceforge.io/html/python/), [Pillow](https://pillow.readthedocs.io/) e [pySerial](https://pyserial.readthedocs.io/).

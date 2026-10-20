Autor: **Mario Pin – PU2PTU**.

## Instalação e atualização

Baixe **Rotor_PU2PTU_1.3.0_Setup_x64.exe** em Assets. O instalador inclui Python e bibliotecas para Windows 10/11 x64.

**Esta versão exige atualizar também o Arduino para o firmware 1.2.** O protocolo agora é 2; Windows 1.3.0 e firmware 1.1 não se conectam. O instalador não grava o Arduino. Abra `Arduino/rotor_1_2/rotor_1_2.ino` na IDE Arduino com a placa Uno.

- **Rotor_PU2PTU_1.3.0_Fontes.zip**: código completo da interface, firmware 1.2, versões anteriores preservadas, testes, documentação e receita do instalador.
- **Rotor_PU2PTU_Firmware_1.2.zip**: sketch completo, guia do hardware, operação pelos botões e protocolo.
- **SHA256SUMS.txt**: hashes dos três arquivos acima.

As configurações anteriores de estação/mapa são reaproveitadas. O limite de velocidade é lido da EEPROM do Arduino ao conectar, sem restaurar um limite antigo do computador.

## Novidades

- Coluna esquerda com 60% da largura anterior; ESQ/PARAR/DIR continuam lado a lado e o mapa ganha espaço.
- Configuração de estação dentro da janela principal, incluindo abertura **total** do feixe −3 dB.
- Português, inglês, espanhol, alemão e russo com seleção pelas bandeiras no canto inferior direito e idioma salvo.
- Limite global de velocidade em seis níveis, aplicado pelo Arduino ao manual local, manual USB e automático.
- Configuração no display: com o rotor já parado, segure ambos os botões por cerca de 2 s, solte, ajuste por ESQ/DIR e pressione ambos para salvar. Solte-os antes de voltar a movimentar.
- Ambos durante movimento continuam parando imediatamente; continuar segurando não abre o menu.
- Persistência em dois registros EEPROM e sincronização com a interface Windows.
- Ícones próprios no programa, título, atalhos e instalador preservados.

O teto é de PWM (70, 90, 110, 140, 175 ou 220), não uma velocidade mecânica medida. O ajuste do corte final/desaceleração permanece o anterior.

## Validação

34 testes Python aprovados, um específico de Windows ignorado; 25 cenários do firmware aprovados. Compilação AVR real para Uno aprovada, com 27.498 bytes de programa e 1.073 bytes de dados estáticos. Interface inspecionada nos cinco idiomas e instalador conferido por análise estática, incluindo módulos, runtime x64 e ícones.

Não houve ensaio no rotor físico nem execução em Windows neste ambiente. Consulte `VALIDACAO.md` e o guia de bancada antes do ensaio no equipamento.

## Integridade do instalador

`Rotor_PU2PTU_1.3.0_Setup_x64.exe` — 16.190.563 bytes.

SHA-256: `43c9ea577590496c666b9159aca0a75d636e1a9bfabb629244077be11eba10cf`.

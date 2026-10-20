# Validação do firmware 1.2 — 20/10/2026

Autor do projeto: Mario Pin – PU2PTU.

O sketch completo `rotor_1_2/rotor_1_2.ino` passou por **25 cenários de teste nativo**, usando o próprio código do firmware com substitutos de IO, display e EEPROM em `Testes/stubs`. Execute na raiz:

```sh
python Testes/executar_firmware.py
```

Os cenários mantêm as regressões da 1.1 e cobrem seis limites de PWM nos três controles, redução imediata/aumento gradual, parser SPEED, menu pelos dois botões, ausência de movimento durante configuração, prioridade local e falhas. A EEPROM é testada com escrita interrompida, registros inválidos, ausência de regravação e 300 gravações com volta do contador.

Também foi feita compilação AVR real para **Arduino Uno / ATmega328P**, com core Arduino AVR e bibliotecas Adafruit GFX, ST7735/ST7789 e BusIO, totalizando 41 unidades. Resultado: **27.498 bytes de programa e 1.073 bytes de dados estáticos**. Esse resultado não mede o pico da pilha em execução.

Não houve gravação nem teste no rotor físico nesta preparação. O primeiro ensaio deve seguir `GUIA_FIRMWARE_1.2.md`, começando com potência do motor desligada e conferindo o teto após reiniciar e reconectar.

Os sketches 1.0 e 1.1 foram preservados. O ajuste de desaceleração de 30°, passo 1, tolerância de 1° e corte final permanecem da versão anterior; não se afirma correção do pequeno tranco final relatado anteriormente.

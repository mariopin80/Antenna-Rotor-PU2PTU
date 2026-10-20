#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <SPI.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <avr/wdt.h>
#include <EEPROM.h>

bool forcarDisplay = false;

// =====================================================
// DISPLAY ST7789
// =====================================================

#define TFT_CS   10
#define TFT_DC    9
#define TFT_RST   8

Adafruit_ST7789 tft =
  Adafruit_ST7789(TFT_CS, TFT_DC, TFT_RST);


// =====================================================
// SENSOR DE POSIÇÃO
// =====================================================

#define VOLTAGE_PIN A0

#define VREF 5.00


// =====================================================
// CALIBRAÇÃO DO AZIMUTE
// =====================================================
//
// 4,80 V =   0°
// 0,40 V = 360°
//

#define V_NORTE_0    4.80
#define V_NORTE_360  0.40


// =====================================================
// FILTRO DA LEITURA
// =====================================================

#define FILTRO_ALPHA 0.4


// =====================================================
// BOTÕES
// =====================================================
//
// Botões ligados entre pino e GND.
//
// solto       = HIGH
// pressionado = LOW
//

#define BTN_ESQ 2
#define BTN_DIR 4


// =====================================================
// BTS7960 / IBT-2
// =====================================================
//
// R_EN -> 5 V
// L_EN -> 5 V
//
// RPWM -> D3
// LPWM -> D5
//

#define BTS_RPWM 3
#define BTS_LPWM 5


// =====================================================
// SENTIDO
// =====================================================

#define SENTIDO_ESQUERDA -1
#define SENTIDO_PARADO    0
#define SENTIDO_DIREITA   1


// =====================================================
// VELOCIDADES PWM
// =====================================================
//
// 0,0 - 0,5 s  -> 70
// 0,5 - 1,0 s  -> 90
// 1,0 - 1,5 s  -> 110
// 1,5 - 2,0 s  -> 140
// 2,0 - 2,5 s  -> 175
// > 2,5 s      -> 220
//

#define PWM_FINE_1   70
#define PWM_FINE_2   90
#define PWM_MED_1   110
#define PWM_MED_2   140
#define PWM_HIGH    175
#define PWM_MAX     220


// =====================================================
// TEMPOS DA RAMPA
// =====================================================

#define T1  500UL
#define T2 1000UL
#define T3 1500UL
#define T4 2000UL
#define T5 2500UL


// =====================================================
// TEMPO MORTO PARA INVERSÃO
// =====================================================

#define TEMPO_MORTO 100UL


// =====================================================
// FIM DE CURSO ELETRÔNICO
// =====================================================
//
// DIREITA  -> tensão diminui
// ESQUERDA -> tensão aumenta
//
// <= 0,30 V:
// bloqueia DIREITA
//
// >= 4,90 V:
// bloqueia ESQUERDA
//

#define LIMITE_BAIXO          0.30
#define LIMITE_BAIXO_LIBERA   0.35

#define LIMITE_ALTO           4.90
#define LIMITE_ALTO_LIBERA    4.85


// =====================================================
// BARRA DE POSIÇÃO
// =====================================================
//
// 4,90 V = extremo esquerdo
// 0,30 V = extremo direito
//

#define BARRA_X          25
#define BARRA_Y         217
#define BARRA_LARGURA   190
#define BARRA_ALTURA     12

#define MARCADOR_LARGURA  8
#define MARCADOR_ALTURA    8


// =====================================================
// VARIÁVEIS DO SENSOR / DISPLAY
// =====================================================

float tensaoFiltrada = 0.0;

int ultimoAzimute = -999;
int ultimaDirecao = -1;

int ultimaPosicaoBarra = -999;


// =====================================================
// VARIÁVEIS DO MOTOR
// =====================================================

int sentidoMotor = SENTIDO_PARADO;
int sentidoSolicitado = SENTIDO_PARADO;

unsigned long inicioMovimento = 0;
unsigned long inicioTempoMorto = 0;

bool aguardandoTempoMorto = false;


// =====================================================
// ESTADO DO FIM DE CURSO
// =====================================================
//
// -1 = limite de baixa tensão
//  0 = normal
// +1 = limite de alta tensão
//

int fimDeCurso = 0;


// =====================================================
// ROSA DOS VENTOS
// =====================================================

const char* nomesDirecoes[16] = {
  "N",
  "NNE",
  "NE",
  "ENE",
  "E",
  "ESE",
  "SE",
  "SSE",
  "S",
  "SSW",
  "SW",
  "WSW",
  "W",
  "WNW",
  "NW",
  "NNW"
};


// =====================================================
// LEITURA DA TENSÃO
// =====================================================

float lerTensao()
{
  const uint8_t NUM_AMOSTRAS = 16;

  uint32_t soma = 0;

  for (uint8_t i = 0; i < NUM_AMOSTRAS; i++) {
    soma += analogRead(VOLTAGE_PIN);
  }

  float adcMedio =
    soma / (float)NUM_AMOSTRAS;

  return adcMedio * VREF / 1023.0;
}


// =====================================================
// TENSÃO -> AZIMUTE
// =====================================================

float calcularAzimute(float tensao)
{
  float azimuteBruto =
    (V_NORTE_0 - tensao) *
    360.0 /
    (V_NORTE_0 - V_NORTE_360);


  float azimute =
    fmod(azimuteBruto, 360.0);


  if (azimute < 0.0) {
    azimute += 360.0;
  }


  // Mantém especificamente o segundo Norte como 360°

  if (fabs(azimuteBruto - 360.0) < 0.5) {
    azimute = 360.0;
  }


  return azimute;
}


// =====================================================
// DIREÇÃO CARDEAL
// =====================================================

int calcularDirecao(float azimute)
{
  if (azimute >= 360.0) {
    azimute = 0.0;
  }


  int setor =
    (int)((azimute + 11.25) / 22.5);


  setor %= 16;


  return setor;
}


// =====================================================
// FIM DE CURSO
// =====================================================

void atualizarFimDeCurso(float tensao)
{
  if (fimDeCurso == 0) {

    if (tensao <= LIMITE_BAIXO) {
      fimDeCurso = -1;
    }

    else if (tensao >= LIMITE_ALTO) {
      fimDeCurso = 1;
    }
  }


  else if (fimDeCurso == -1) {

    if (tensao >= LIMITE_BAIXO_LIBERA) {
      fimDeCurso = 0;
    }
  }


  else if (fimDeCurso == 1) {

    if (tensao <= LIMITE_ALTO_LIBERA) {
      fimDeCurso = 0;
    }
  }
}


// =====================================================
// DESENHO FIXO DA TELA
// =====================================================

void desenharTela()
{
  tft.fillScreen(ST77XX_BLACK);

  tft.setTextWrap(false);


  // ===================================================
  // CABEÇALHO
  // ===================================================

  tft.setTextSize(2);
  tft.setTextColor(ST77XX_WHITE);

  tft.setCursor(36, 12);
  tft.print("ROTOR - PU2PTU");


  tft.drawFastHLine(
    15,
    38,
    210,
    ST77XX_WHITE
  );


  // ===================================================
  // SEPARADOR INFERIOR
  // ===================================================

  tft.drawFastHLine(
    15,
    205,
    210,
    ST77XX_WHITE
  );


  // ===================================================
  // BARRA DE POSIÇÃO
  // ===================================================
  //
  // Agora usamos SOMENTE o retângulo.
  // Não existem mais as linhas verticais maiores
  // nas extremidades.
  //

  tft.drawRect(
    BARRA_X,
    BARRA_Y,
    BARRA_LARGURA,
    BARRA_ALTURA,
    ST77XX_WHITE
  );
}


// =====================================================
// MOSTRAR AZIMUTE
// =====================================================

void mostrarAzimute(float azimute)
{
  int graus =
    (int)(azimute + 0.5);


  if (graus < 0) {
    graus = 0;
  }


  if (graus > 360) {
    graus = 360;
  }


  if (graus == ultimoAzimute && !forcarDisplay) {
    return;
  }


  ultimoAzimute = graus;


  char buffer[6];


  sprintf(
    buffer,
    "%3d",
    graus
  );


  // ===================================================
  // NÚMERO GRANDE
  // ===================================================

  tft.setTextSize(6);

  tft.setTextColor(
    ST77XX_CYAN,
    ST77XX_BLACK
  );


  tft.setCursor(
    48,
    52
  );


  tft.print(buffer);


  // Símbolo de grau

  tft.setTextSize(3);

  tft.print((char)247);

  tft.print(" ");
}


// =====================================================
// MOSTRAR DIREÇÃO
// =====================================================

void mostrarDirecao(float azimute)
{
  int direcao =
    calcularDirecao(azimute);


  if (direcao == ultimaDirecao && !forcarDisplay) {
    return;
  }


  ultimaDirecao = direcao;


  char buffer[5];


  snprintf(
    buffer,
    sizeof(buffer),
    "%-3s",
    nomesDirecoes[direcao]
  );


  tft.setTextSize(5);

  tft.setTextColor(
    ST77XX_YELLOW,
    ST77XX_BLACK
  );


  tft.setCursor(
    75,
    122
  );


  tft.print(buffer);
}


// =====================================================
// BARRA DE POSIÇÃO
// =====================================================
//
// Visual:
//
// ESQUERDA                           DIREITA
//
// | ■-------------------------------- |
// | -----------■--------------------- |
// | -----------------------------■--- |
//
// 4,90 V                              0,30 V
//

void mostrarBarraPosicao(float tensao)
{
  // ---------------------------------------------------
  // Limita apenas a representação gráfica
  // ---------------------------------------------------

  float tensaoBarra = tensao;


  if (tensaoBarra > LIMITE_ALTO) {
    tensaoBarra = LIMITE_ALTO;
  }


  if (tensaoBarra < LIMITE_BAIXO) {
    tensaoBarra = LIMITE_BAIXO;
  }


  // ===================================================
  // LIMITES INTERNOS DA BARRA
  // ===================================================

  int xMin =
    BARRA_X + 2;


  int xMax =
    BARRA_X +
    BARRA_LARGURA -
    MARCADOR_LARGURA -
    2;


  // ===================================================
  // CONVERTE TENSÃO PARA POSIÇÃO
  // ===================================================
  //
  // 4,90 V -> esquerda
  // 0,30 V -> direita
  //

  float proporcao =
    (LIMITE_ALTO - tensaoBarra) /
    (LIMITE_ALTO - LIMITE_BAIXO);


  int posicao =
    xMin +
    (int)(
      proporcao *
      (xMax - xMin)
    );


  // ===================================================
  // NÃO REDESENHA SE NÃO MUDOU DE PIXEL
  // ===================================================

  if (posicao == ultimaPosicaoBarra && !forcarDisplay) {
    return;
  }


  // ===================================================
  // APAGA MARCADOR ANTERIOR
  // ===================================================

  if (ultimaPosicaoBarra != -999) {

    tft.fillRect(
      ultimaPosicaoBarra,
      BARRA_Y + 2,
      MARCADOR_LARGURA,
      MARCADOR_ALTURA,
      ST77XX_BLACK
    );
  }


  // ===================================================
  // DESENHA NOVO MARCADOR
  // ===================================================

  tft.fillRect(
    posicao,
    BARRA_Y + 2,
    MARCADOR_LARGURA,
    MARCADOR_ALTURA,
    ST77XX_GREEN
  );


  ultimaPosicaoBarra =
    posicao;
}


// =====================================================
// INDICAÇÃO DE MOVIMENTO / VELOCIDADE
// =====================================================
//
// PWM 70  -> >
// PWM 90  -> >>
// PWM 110 -> >>>
// PWM 140 -> >>>>
// PWM 175 -> >>>>>
// PWM 220 -> >>>>> VERMELHO
//
//
// Para esquerda:
//
//     <
//    <<
//   <<<
//  <<<<
// <<<<<
//

void mostrarMovimento(
  int sentido,
  uint8_t pwm
)
{
  static int ultimoSentido = 99;
  static uint8_t ultimoNivel = 99;
  static bool ultimoMaximo = false;


  uint8_t nivel = 0;

  bool maximo = false;


  // ===================================================
  // DETERMINA NÍVEL
  // ===================================================

  if (sentido != SENTIDO_PARADO) {

    if (pwm >= PWM_MAX) {

      nivel = 5;
      maximo = true;

    }

    else if (pwm >= PWM_HIGH) {

      nivel = 5;

    }

    else if (pwm >= PWM_MED_2) {

      nivel = 4;

    }

    else if (pwm >= PWM_MED_1) {

      nivel = 3;

    }

    else if (pwm >= PWM_FINE_2) {

      nivel = 2;

    }

    else {

      nivel = 1;

    }
  }


  // ===================================================
  // EVITA REDESENHO
  // ===================================================

  if (
    !forcarDisplay && sentido == ultimoSentido &&
    nivel == ultimoNivel &&
    maximo == ultimoMaximo
  ) {

    return;
  }


  ultimoSentido = sentido;
  ultimoNivel = nivel;
  ultimoMaximo = maximo;


  // ===================================================
  // CAMPO FIXO DE CINCO CARACTERES
  // ===================================================

  char texto[6] = "     ";


  // ===================================================
  // ESQUERDA
  // ===================================================

  if (sentido == SENTIDO_ESQUERDA) {

    switch (nivel) {

      case 1:
        strcpy(texto, "    <");
        break;

      case 2:
        strcpy(texto, "   <<");
        break;

      case 3:
        strcpy(texto, "  <<<");
        break;

      case 4:
        strcpy(texto, " <<<<");
        break;

      case 5:
        strcpy(texto, "<<<<<");
        break;
    }
  }


  // ===================================================
  // DIREITA
  // ===================================================

  else if (sentido == SENTIDO_DIREITA) {

    switch (nivel) {

      case 1:
        strcpy(texto, ">    ");
        break;

      case 2:
        strcpy(texto, ">>   ");
        break;

      case 3:
        strcpy(texto, ">>>  ");
        break;

      case 4:
        strcpy(texto, ">>>> ");
        break;

      case 5:
        strcpy(texto, ">>>>>");
        break;
    }
  }


  // ===================================================
  // COR
  // ===================================================

  uint16_t cor =
    maximo
      ? ST77XX_RED
      : ST77XX_WHITE;


  // ===================================================
  // DESENHA
  // ===================================================

  tft.setTextSize(3);

  tft.setTextColor(
    cor,
    ST77XX_BLACK
  );


  tft.setCursor(
    75,
    174
  );


  tft.print(texto);
}


// =====================================================
// ROTOR PU2PTU 1.2 - CONTROLE LOCAL + USB (115200, 8N1)
// Protocolo 2; comandos ASCII terminados por \n.
// O controle automatico trabalha em posicao mecanica, sem
// presumir giro ilimitado. Display e pinos mantidos da 1.0.
// =====================================================

#define CONTROLE_MS              20UL
#define TELEMETRIA_MS           100UL
#define LINK_TIMEOUT_MS        1000UL
#define JOG_TIMEOUT_MS          550UL
#define AUTO_TOLERANCIA            1.0f
#define AUTO_DESACELERACAO        30.0f
#define AUTO_PWM_MIN             PWM_FINE_1
#define AUTO_ACEL_PASSO             1
#define AUTO_DESACEL_PASSO          1
#define SENSOR_MIN_VALIDO          0.15f
#define SENSOR_MAX_VALIDO          4.98f
#define SEM_MOVIMENTO_MS        8000UL
#define MIN_MOVIMENTO_GRAUS        0.5f
#define MAX_MOVIMENTO_MS      180000UL

// Modos transmitidos: 0 parado, 1 local, 2 jog USB,
// 3 automatico USB, 4 falha travada ate STOP.
enum ModoControle { PARADO, LOCAL, JOG_USB, AUTO_USB, FALHA, CONFIGURACAO };
// Motivos: 0 parada, 1 alvo, 2 limite, 3 link, 4 sensor,
// 5 sem movimento, 6 tempo excedido, 7 local, 8 dois botoes, 9 configuracao local.
enum MotivoParada { OPERADOR, ALVO, LIMITE, LINK, SENSOR,
                    TRAVADO, TEMPO, BOTAO_LOCAL, DOIS_BOTOES, CONFIG_LOCAL };
// Assinaturas com tipo padrao: prototipos gerados pela IDE Arduino
// continuam validos mesmo quando aparecem antes dos enums acima.
void encerrarMovimento(uint8_t novoMotivo, bool falha = false);
void iniciarComando(uint8_t novoModo);

ModoControle modo = PARADO;
MotivoParada motivo = OPERADOR;
uint8_t pwmAtual = 0;
float tensaoAtual = 0.0f;
float posicaoMecanica = 0.0f;
float alvoMecanico = 0.0f;
float posicaoProgresso = 0.0f;
int sentidoJog = SENTIDO_PARADO;
int sentidoAuto = SENTIDO_PARADO;
int ultimoSentidoEnergizado = SENTIDO_PARADO;
unsigned long ultimaParada = 0;
unsigned long ultimoContato = 0;
unsigned long ultimoJog = 0;
unsigned long ultimoControle = 0;
unsigned long ultimaTelemetria = 0;
unsigned long ultimoDisplay = 0;
unsigned long inicioComando = 0;
unsigned long ultimoProgresso = 0;
bool sensorValido = true;
bool bloquearLocalAteSoltar = false;
uint8_t botoesBrutos = 0;
uint8_t botoesAnteriores = 0;
uint8_t botoesEstaveis = 0;
unsigned long botoesMudaram = 0;
char linhaSerial[40];
// O limite tem seis niveis e pertence ao Arduino, nao ao PC.
const uint8_t niveisPWM[6] = {70, 90, 110, 140, 175, 220};
uint8_t nivelMaximo = 6;
bool suavizarAumentoMaximo = false;
uint8_t nivelEdicao = 6;
uint8_t ultimoNivelMaximoDesenhado = 0;
uint8_t ultimaTeclaMenu = 0;
bool gestoPodeConfigurar = false;
bool menuAguardarSoltar = true;
bool telaConfiguracao = false;
bool menuRedesenhar = true;
unsigned long inicioGesto = 0;
unsigned long inicioDoisBotoes = 0;
unsigned long ultimaConfiguracao = 0;

uint8_t tamanhoLinha = 0;
bool descartarLinha = false;
unsigned long ultimoByte = 0;

float calcularPosicaoMecanica(float tensao)
{
  return (V_NORTE_0 - tensao) * 360.0f / (V_NORTE_0 - V_NORTE_360);
}

void desligarMotor()
{
  analogWrite(BTS_RPWM, 0);
  analogWrite(BTS_LPWM, 0);
}

// Desliga imediatamente; o desenho fica fora do controle do motor.
void pararMotor()
{
  if (sentidoMotor != SENTIDO_PARADO) {
    ultimoSentidoEnergizado = sentidoMotor;
    ultimaParada = millis();
  }
  desligarMotor();
  sentidoMotor = SENTIDO_PARADO;
  sentidoSolicitado = SENTIDO_PARADO;
  pwmAtual = 0;
  aguardandoTempoMorto = false;
  suavizarAumentoMaximo = false;
}

void encerrarMovimento(uint8_t novoMotivo, bool falha)
{
  pararMotor();
  sentidoJog = SENTIDO_PARADO;
  sentidoAuto = SENTIDO_PARADO;
  modo = falha ? FALHA : PARADO;
  motivo = (MotivoParada)novoMotivo;
  if (botoesBrutos != 0) bloquearLocalAteSoltar = true;
}

void moverDireita(uint8_t pwm)
{
  analogWrite(BTS_LPWM, 0);
  analogWrite(BTS_RPWM, pwm);
}

void moverEsquerda(uint8_t pwm)
{
  analogWrite(BTS_RPWM, 0);
  analogWrite(BTS_LPWM, pwm);
}

uint8_t calcularPWM(unsigned long tempoPressionado)
{
  if (tempoPressionado < T1) return PWM_FINE_1;
  if (tempoPressionado < T2) return PWM_FINE_2;
  if (tempoPressionado < T3) return PWM_MED_1;
  if (tempoPressionado < T4) return PWM_MED_2;
  if (tempoPressionado < T5) return PWM_HIGH;
  return PWM_MAX;
}

void iniciarComando(uint8_t novoModo)
{
  modo = (ModoControle)novoModo;
  motivo = OPERADOR;
  inicioComando = millis();
  ultimoProgresso = millis();
  posicaoProgresso = posicaoMecanica;
}

// Margem antes dos limites eletricos: usa os limiares de liberacao.
// Exemplo: Norte 0/360 escolhe a extremidade fisica mais proxima.
float escolherAlvo(float azimute)
{
  if (azimute == 360.0f) azimute = 0.0f;
  float minimo = calcularPosicaoMecanica(LIMITE_ALTO_LIBERA);
  float maximo = calcularPosicaoMecanica(LIMITE_BAIXO_LIBERA);
  float melhor = azimute;
  float distancia = 10000.0f;
  for (int8_t volta = -1; volta <= 1; volta++) {
    float candidato = azimute + 360.0f * volta;
    if (candidato >= minimo && candidato <= maximo) {
      float d = fabs(candidato - posicaoMecanica);
      if (d < distancia) { melhor = candidato; distancia = d; }
    }
  }
  return melhor;
}


uint8_t pwmMaximoConfigurado() { return niveisPWM[nivelMaximo - 1]; }

void enviarVelocidade()
{
  Serial.print(F("SPEED,")); Serial.println((int)nivelMaximo);
}

// Dois registros alternados: um gravado por completo so se torna valido
// no ultimo byte. Uma interrupcao na gravacao preserva o registro anterior.
const uint8_t EEPROM_MAGIC = 0xA7;
int8_t slotVelocidade = -1;
uint8_t sequenciaVelocidade = 0;

bool registroVelocidadeValido(uint8_t slot)
{
  int p = slot * 6;
  uint8_t seq = EEPROM.read(p + 1), nivel = EEPROM.read(p + 2);
  return EEPROM.read(p) == EEPROM_MAGIC && nivel >= 1 && nivel <= 6 &&
    EEPROM.read(p + 3) == (uint8_t)~nivel &&
    EEPROM.read(p + 4) == (uint8_t)(seq ^ nivel ^ 0x5C) &&
    EEPROM.read(p + 5) == 1;
}

void carregarVelocidade()
{
  bool a = registroVelocidadeValido(0), b = registroVelocidadeValido(1);
  slotVelocidade = a ? 0 : (b ? 1 : -1);
  if (a && b) {
    uint8_t diferenca = EEPROM.read(7) - EEPROM.read(1);
    if (diferenca != 0 && diferenca < 128) slotVelocidade = 1;
  }
  if (slotVelocidade >= 0) {
    sequenciaVelocidade = EEPROM.read(slotVelocidade * 6 + 1);
    nivelMaximo = EEPROM.read(slotVelocidade * 6 + 2);
  } else {
    bool virgem = true;
    for (uint8_t p = 0; p < 12; ++p) if (EEPROM.read(p) != 0xFF) virgem = false;
    // Placa sem configuracao conserva o maximo anterior; registro corrompido
    // usa o nivel minimo ate o operador confirmar um novo limite.
    nivelMaximo = virgem ? 6 : 1;
  }
}

void salvarVelocidade(uint8_t nivel)
{
  if (nivel == nivelMaximo && slotVelocidade >= 0) return;
  if (nivel > nivelMaximo && sentidoMotor != SENTIDO_PARADO &&
      (modo == LOCAL || modo == JOG_USB)) suavizarAumentoMaximo = true;
  nivelMaximo = nivel;
  // Aplicacao imediata inclusive quando o PC reduz o limite em movimento.
  if (pwmAtual > pwmMaximoConfigurado()) {
    pwmAtual = pwmMaximoConfigurado();
    if (sentidoMotor == SENTIDO_DIREITA) moverDireita(pwmAtual);
    else if (sentidoMotor == SENTIDO_ESQUERDA) moverEsquerda(pwmAtual);
  }
  uint8_t proximo = slotVelocidade == 0 ? 1 : 0;
  uint8_t seq = sequenciaVelocidade + 1;
  int p = proximo * 6;
  EEPROM.update(p, 0); // invalida somente o slot que sera substituido
  EEPROM.update(p + 1, seq);
  EEPROM.update(p + 2, nivel);
  EEPROM.update(p + 3, (uint8_t)~nivel);
  EEPROM.update(p + 4, (uint8_t)(seq ^ nivel ^ 0x5C));
  EEPROM.update(p + 5, 1);
  EEPROM.update(p, EEPROM_MAGIC); // commit
  slotVelocidade = proximo; sequenciaVelocidade = seq;
}

void atualizarMenuLocal()
{
  unsigned long agora = millis();
  if (modo == CONFIGURACAO) {
    pararMotor();
    if (menuAguardarSoltar) {
      if (botoesBrutos == 0) { menuAguardarSoltar = false; ultimaTeclaMenu = 0; }
      return;
    }
    if (botoesBrutos == 0) { ultimaTeclaMenu = 0; return; }
    if (botoesBrutos != botoesEstaveis) return;
    if (botoesBrutos == 3) {
      salvarVelocidade(nivelEdicao);
      modo = PARADO; motivo = OPERADOR;
      bloquearLocalAteSoltar = true; gestoPodeConfigurar = false;
      enviarVelocidade(); return;
    }
    // Janela para reconhecer a combinacao, evitando alterar um nivel ao salvar.
    if (agora - botoesMudaram < 150UL || ultimaTeclaMenu != 0) return;
    ultimaTeclaMenu = botoesBrutos;
    if (botoesBrutos == 1 && nivelEdicao > 1) --nivelEdicao;
    if (botoesBrutos == 2 && nivelEdicao < 6) ++nivelEdicao;
    menuRedesenhar = true;
    return;
  }
  if (botoesBrutos == 3 && gestoPodeConfigurar && modo == PARADO &&
      sensorValido && agora - inicioDoisBotoes >= 2000UL) {
    pararMotor(); modo = CONFIGURACAO; motivo = CONFIG_LOCAL;
    nivelEdicao = nivelMaximo; menuAguardarSoltar = true;
    ultimaTeclaMenu = 0; menuRedesenhar = true; gestoPodeConfigurar = false;
  }
}

void atualizarDisplay()
{
  if (modo == CONFIGURACAO) {
    if (!telaConfiguracao || menuRedesenhar) {
      tft.fillScreen(ST77XX_BLACK);
      tft.setTextWrap(false); tft.setTextColor(ST77XX_WHITE); tft.setTextSize(2);
      tft.setCursor(18, 18); tft.print(F("CONFIGURACAO"));
      tft.drawFastHLine(15, 42, 210, ST77XX_WHITE);
      tft.setCursor(18, 59); tft.print(F("VELOCIDADE MAXIMA"));
      tft.setTextSize(5); tft.setTextColor(ST77XX_CYAN);
      tft.setCursor(72, 94); tft.print((int)nivelEdicao); tft.print(F("/6"));
      tft.setTextColor(ST77XX_YELLOW); tft.setTextSize(2);
      tft.setCursor(18, 158); tft.print(F("ESQ -     DIR +"));
      tft.setTextColor(ST77XX_WHITE); tft.setTextSize(1);
      tft.setCursor(18, 196); tft.print(F("DOIS BOTOES: SALVAR E SAIR"));
      tft.setCursor(18, 214); tft.print(F("Solte os botoes antes de ajustar."));
      telaConfiguracao = true; menuRedesenhar = false;
    }
    return;
  }
  if (telaConfiguracao) {
    desenharTela(); telaConfiguracao = false; forcarDisplay = true;
    ultimoNivelMaximoDesenhado = 0;
  }
  mostrarAzimute(calcularAzimute(tensaoFiltrada));
  mostrarDirecao(calcularAzimute(tensaoFiltrada));
  mostrarBarraPosicao(tensaoFiltrada);
  mostrarMovimento(sentidoMotor, pwmAtual);
  if (ultimoNivelMaximoDesenhado != nivelMaximo || forcarDisplay) {
    tft.setTextSize(1); tft.setTextColor(ST77XX_WHITE, ST77XX_BLACK);
    tft.setCursor(174, 42); tft.print(F("MAX ")); tft.print((int)nivelMaximo); tft.print(F("/6"));
    ultimoNivelMaximoDesenhado = nivelMaximo;
  }
  forcarDisplay = false;
}

void enviarIdentificacao()
{
  Serial.println(F("ROTOR,2,1.2"));
  enviarVelocidade();
}

// Usa Serial.print: sprintf de float nao e habilitado no AVR Uno.
void enviarEstado()
{
  float barra = (LIMITE_ALTO - tensaoFiltrada) * 100.0f /
                (LIMITE_ALTO - LIMITE_BAIXO);
  barra = constrain(barra, 0.0f, 100.0f);
  Serial.print(F("STAT,"));
  Serial.print(calcularAzimute(tensaoFiltrada), 1); Serial.print(',');
  Serial.print(posicaoMecanica, 1); Serial.print(',');
  Serial.print(barra, 1); Serial.print(',');
  Serial.print((int)modo); Serial.print(',');
  Serial.print(sentidoMotor); Serial.print(',');
  Serial.print(pwmAtual); Serial.print(',');
  if (modo == AUTO_USB) Serial.print(alvoMecanico, 1);
  else Serial.print(F("NA"));
  Serial.print(','); Serial.print(fimDeCurso);
  Serial.print(','); Serial.println((int)motivo);
}

void processarComando(char* linha)
{
  if (strcmp(linha, "HELLO") == 0) {
    enviarIdentificacao(); return;
  }
  if (strcmp(linha, "PING") == 0) {
    ultimoContato = millis(); return;
  }
  if (strcmp(linha, "STOP") == 0) {
    // Uma falha de sensor so e liberada depois da leitura voltar a ser valida.
    if (!sensorValido) encerrarMovimento(SENSOR, true);
    else if (modo == CONFIGURACAO) pararMotor();
    else encerrarMovimento(OPERADOR);
    Serial.println(F("OK,STOP")); return;
  }
  if (strcmp(linha, "SPEED?") == 0) { enviarVelocidade(); return; }
  if (strncmp(linha, "SPEED,", 6) == 0) {
    if (strlen(linha) != 7 || linha[6] < '1' || linha[6] > '6') {
      Serial.println(F("ERR,SPEED")); return;
    }
    if (modo == CONFIGURACAO) { Serial.println(F("ERR,CONFIG")); return; }
    salvarVelocidade(linha[6] - '0');
    Serial.println(F("OK,SPEED")); enviarVelocidade(); return;
  }
  if (modo == CONFIGURACAO) { Serial.println(F("ERR,CONFIG")); return; }
  if (botoesBrutos != 0 || bloquearLocalAteSoltar) {
    Serial.println(F("ERR,LOCAL")); return;
  }
  if (modo == FALHA || !sensorValido) {
    Serial.println(F("ERR,FAULT")); return;
  }
  if (strcmp(linha, "JOG,L") == 0 || strcmp(linha, "JOG,R") == 0) {
    int novoSentido = (linha[4] == 'L') ? SENTIDO_ESQUERDA : SENTIDO_DIREITA;
    // Renovar o mesmo JOG preserva a rampa; nao imprime ACK a cada renovacao.
    if (modo != JOG_USB || sentidoJog != novoSentido) {
      pararMotor(); iniciarComando(JOG_USB); sentidoJog = novoSentido;
    }
    ultimoContato = ultimoJog = millis(); return;
  }
  if (strncmp(linha, "MOVE,", 5) == 0) {
    char* fim;
    float valor = strtod(linha + 5, &fim);
    if (fim == linha + 5 || *fim != '\0' || !isfinite(valor) ||
        valor < 0.0f || valor > 360.0f) {
      Serial.println(F("ERR,ANGLE")); return;
    }
    pararMotor();
    alvoMecanico = escolherAlvo(valor);
    iniciarComando(AUTO_USB);
    sentidoAuto = (alvoMecanico >= posicaoMecanica) ? SENTIDO_DIREITA : SENTIDO_ESQUERDA;
    ultimoContato = millis();
    Serial.println(F("OK,MOVE")); return;
  }
  Serial.println(F("ERR,COMMAND"));
}

void receberSerial()
{
  // Limite de trabalho por loop; fluxo serial continuo nao bloqueia o controle.
  uint8_t lidos = 0;
  if (tamanhoLinha && millis() - ultimoByte > 250UL) {
    tamanhoLinha = 0;
    descartarLinha = true; // fragmento antigo nao pode virar um comando novo.
  }
  while (Serial.available() && lidos++ < 32) {
    char c = Serial.read(); ultimoByte = millis();
    if (c == '\r') continue;
    if (c == '\n') {
      if (descartarLinha) Serial.println(F("ERR,LINE"));
      else if (tamanhoLinha) {
        linhaSerial[tamanhoLinha] = '\0'; processarComando(linhaSerial);
      }
      tamanhoLinha = 0; descartarLinha = false;
    } else if (!descartarLinha) {
      if (c < 32 || c > 126 || tamanhoLinha >= sizeof(linhaSerial) - 1) {
        tamanhoLinha = 0; descartarLinha = true;
      } else linhaSerial[tamanhoLinha++] = c;
    }
  }
}

void lerBotoes()
{
  unsigned long agora = millis();
  uint8_t antes = botoesBrutos;
  botoesBrutos = (digitalRead(BTN_ESQ) == LOW ? 1 : 0) |
                 (digitalRead(BTN_DIR) == LOW ? 2 : 0);
  if (antes == 0 && botoesBrutos != 0) {
    gestoPodeConfigurar = modo == PARADO && sentidoMotor == SENTIDO_PARADO &&
                         !bloquearLocalAteSoltar && sensorValido;
    inicioGesto = agora;
  }
  if (botoesBrutos != botoesAnteriores) {
    botoesAnteriores = botoesBrutos; botoesMudaram = agora;
  }
  if (agora - botoesMudaram >= 20UL) botoesEstaveis = botoesBrutos;
  if (botoesBrutos == 3 && antes != 3) {
    inicioDoisBotoes = agora;
    bool elegivel = gestoPodeConfigurar && modo == PARADO && sensorValido;
    if (modo != CONFIGURACAO && modo != FALHA) encerrarMovimento(DOIS_BOTOES);
    else pararMotor();
    gestoPodeConfigurar = elegivel;
  }
  if (botoesBrutos == 0) {
    botoesEstaveis = 0; bloquearLocalAteSoltar = false;
    gestoPodeConfigurar = false;
    if (modo == PARADO && motivo == DOIS_BOTOES) motivo = OPERADOR;
  }
}

void atualizarMotor()
{
  unsigned long agora = millis();
  if (!sensorValido) { encerrarMovimento(SENSOR, true); return; }
  if (modo == FALHA || modo == CONFIGURACAO) { pararMotor(); return; }
  if (botoesBrutos == 3) { encerrarMovimento(DOIS_BOTOES); return; }
  if (bloquearLocalAteSoltar) { pararMotor(); return; }

  // Breve janela de combinacao somente quando a pressao comeca parado.
  if (modo == PARADO && gestoPodeConfigurar && botoesBrutos != 0 &&
      agora - inicioGesto < 150UL) { pararMotor(); return; }

  // Qualquer pressao local cancela o controle remoto; nao retoma ao soltar.
  if (botoesBrutos != 0 && modo != LOCAL) {
    pararMotor(); iniciarComando(LOCAL); motivo = BOTAO_LOCAL;
  }
  if (modo == LOCAL && botoesBrutos == 0) {
    encerrarMovimento(OPERADOR); return;
  }
  if ((modo == JOG_USB || modo == AUTO_USB) &&
      agora - ultimoContato > LINK_TIMEOUT_MS) {
    encerrarMovimento(LINK); return;
  }
  if (modo == JOG_USB && agora - ultimoJog > JOG_TIMEOUT_MS) {
    encerrarMovimento(LINK); return;
  }

  int desejado = SENTIDO_PARADO;
  if (modo == LOCAL && botoesEstaveis == botoesBrutos) {
    if (botoesEstaveis == 1) desejado = SENTIDO_ESQUERDA;
    if (botoesEstaveis == 2) desejado = SENTIDO_DIREITA;
  } else if (modo == JOG_USB) desejado = sentidoJog;
  else if (modo == AUTO_USB) {
    float erro = alvoMecanico - posicaoMecanica;
    // Interrompe ao entrar na tolerancia ou cruzar o alvo; nao fica oscilando.
    if (fabs(erro) <= AUTO_TOLERANCIA || erro * sentidoAuto <= 0.0f) {
      encerrarMovimento(ALVO); return;
    }
    desejado = sentidoAuto;
  }
  if (desejado == SENTIDO_PARADO) { pararMotor(); return; }
  if ((fimDeCurso == -1 && desejado == SENTIDO_DIREITA) ||
      (fimDeCurso == 1 && desejado == SENTIDO_ESQUERDA)) {
    encerrarMovimento(LIMITE); return;
  }
  if (agora - inicioComando > MAX_MOVIMENTO_MS) {
    encerrarMovimento(TEMPO, true); return;
  }
  if (sentidoMotor != SENTIDO_PARADO && sentidoMotor != desejado) pararMotor();

  if (sentidoMotor == SENTIDO_PARADO) {
    if (ultimoSentidoEnergizado != SENTIDO_PARADO &&
        ultimoSentidoEnergizado != desejado && agora - ultimaParada < TEMPO_MORTO) {
      aguardandoTempoMorto = true; return;
    }
    aguardandoTempoMorto = false;
    sentidoMotor = sentidoSolicitado = desejado;
    inicioMovimento = agora;
    pwmAtual = AUTO_PWM_MIN;
    ultimoProgresso = agora; posicaoProgresso = posicaoMecanica;
  }

  if (fabs(posicaoMecanica - posicaoProgresso) >= MIN_MOVIMENTO_GRAUS) {
    posicaoProgresso = posicaoMecanica; ultimoProgresso = agora;
  } else if (agora - ultimoProgresso > SEM_MOVIMENTO_MS) {
    encerrarMovimento(TRAVADO, true); return;
  }

  if (modo == AUTO_USB) {
    float distancia = fabs(alvoMecanico - posicaoMecanica);
    float fracao = constrain((distancia - AUTO_TOLERANCIA) /
                              AUTO_DESACELERACAO, 0.0f, 1.0f);
    int objetivoPWM = AUTO_PWM_MIN + (int)((pwmMaximoConfigurado() - AUTO_PWM_MIN) * fracao);
    if (pwmAtual < objetivoPWM) pwmAtual = min(objetivoPWM, pwmAtual + AUTO_ACEL_PASSO);
    if (pwmAtual > objetivoPWM) pwmAtual = max(objetivoPWM, pwmAtual - AUTO_DESACEL_PASSO);
  } else {
    uint8_t objetivoManual = min(calcularPWM(agora - inicioMovimento), pwmMaximoConfigurado());
    pwmAtual = suavizarAumentoMaximo && objetivoManual > pwmAtual ?
               min(objetivoManual, pwmAtual + 1) : objetivoManual;
    if (pwmAtual >= objetivoManual) suavizarAumentoMaximo = false;
  }
  pwmAtual = min(pwmAtual, pwmMaximoConfigurado());
  if (sentidoMotor == SENTIDO_DIREITA) moverDireita(pwmAtual);
  else moverEsquerda(pwmAtual);
}

void setup()
{
  // Desabilita watchdog antes da inicializacao do display (Uno/Optiboot).
  MCUSR = 0; wdt_disable();
  pinMode(VOLTAGE_PIN, INPUT);
  pinMode(BTN_ESQ, INPUT_PULLUP); pinMode(BTN_DIR, INPUT_PULLUP);
  pinMode(BTS_RPWM, OUTPUT); pinMode(BTS_LPWM, OUTPUT);
  desligarMotor();
  carregarVelocidade();
  Serial.begin(115200);
  tft.init(240, 240); tft.setRotation(2); desenharTela();
  tensaoAtual = tensaoFiltrada = lerTensao();
  sensorValido = tensaoAtual >= SENSOR_MIN_VALIDO && tensaoAtual <= SENSOR_MAX_VALIDO;
  posicaoMecanica = calcularPosicaoMecanica(tensaoAtual);
  atualizarFimDeCurso(tensaoAtual);
  mostrarAzimute(calcularAzimute(tensaoFiltrada));
  mostrarDirecao(calcularAzimute(tensaoFiltrada));
  mostrarBarraPosicao(tensaoFiltrada);
  mostrarMovimento(SENTIDO_PARADO, 0);
  if (!sensorValido) encerrarMovimento(SENSOR, true);
  Serial.println(F("BOOT,1.2"));
  enviarIdentificacao();
  wdt_enable(WDTO_1S);
}

void loop()
{
  wdt_reset();
  lerBotoes();
  atualizarMenuLocal();
  receberSerial();
  unsigned long agora = millis();
  if (agora - ultimoControle >= CONTROLE_MS) {
    ultimoControle = agora;
    tensaoAtual = lerTensao();
    sensorValido = tensaoAtual >= SENSOR_MIN_VALIDO && tensaoAtual <= SENSOR_MAX_VALIDO;
    atualizarFimDeCurso(tensaoAtual); // sempre usa leitura atual sem filtro temporal.
    tensaoFiltrada = tensaoFiltrada * (1.0f - FILTRO_ALPHA) + tensaoAtual * FILTRO_ALPHA;
    posicaoMecanica = calcularPosicaoMecanica(tensaoAtual);
    atualizarMotor();
  }
  if (agora - ultimoDisplay >= 100UL) {
    ultimoDisplay = agora;
    atualizarDisplay();
  }
  if (agora - ultimaTelemetria >= TELEMETRIA_MS) {
    ultimaTelemetria = agora; enviarEstado();
    if (agora - ultimaConfiguracao >= 1000UL) {
      ultimaConfiguracao = agora; enviarVelocidade();
    }
  }
}

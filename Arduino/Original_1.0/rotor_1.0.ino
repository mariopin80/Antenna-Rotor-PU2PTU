#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <SPI.h>
#include <math.h>

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


  if (graus == ultimoAzimute) {
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


  if (direcao == ultimaDirecao) {
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

  if (posicao == ultimaPosicaoBarra) {
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
    sentido == ultimoSentido &&
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
// DESLIGA BTS7960
// =====================================================

void desligarMotor()
{
  analogWrite(
    BTS_RPWM,
    0
  );


  analogWrite(
    BTS_LPWM,
    0
  );
}


// =====================================================
// PARAR MOTOR
// =====================================================

void pararMotor()
{
  desligarMotor();


  sentidoMotor =
    SENTIDO_PARADO;


  sentidoSolicitado =
    SENTIDO_PARADO;


  aguardandoTempoMorto =
    false;


  mostrarMovimento(
    SENTIDO_PARADO,
    0
  );
}


// =====================================================
// MOVER DIREITA
// =====================================================

void moverDireita(uint8_t pwm)
{
  // Primeiro desliga sentido contrário

  analogWrite(
    BTS_LPWM,
    0
  );


  analogWrite(
    BTS_RPWM,
    pwm
  );
}


// =====================================================
// MOVER ESQUERDA
// =====================================================

void moverEsquerda(uint8_t pwm)
{
  // Primeiro desliga sentido contrário

  analogWrite(
    BTS_RPWM,
    0
  );


  analogWrite(
    BTS_LPWM,
    pwm
  );
}


// =====================================================
// RAMPA DE PWM
// =====================================================

uint8_t calcularPWM(
  unsigned long tempoPressionado
)
{
  if (tempoPressionado < T1) {
    return PWM_FINE_1;
  }


  if (tempoPressionado < T2) {
    return PWM_FINE_2;
  }


  if (tempoPressionado < T3) {
    return PWM_MED_1;
  }


  if (tempoPressionado < T4) {
    return PWM_MED_2;
  }


  if (tempoPressionado < T5) {
    return PWM_HIGH;
  }


  return PWM_MAX;
}


// =====================================================
// CONTROLE DO MOTOR
// =====================================================

void atualizarMotor()
{
  bool esquerda =
    digitalRead(BTN_ESQ) == LOW;


  bool direita =
    digitalRead(BTN_DIR) == LOW;


  // ===================================================
  // NENHUM BOTÃO
  // ===================================================

  if (!esquerda && !direita) {

    pararMotor();

    return;
  }


  // ===================================================
  // DOIS BOTÕES
  // ===================================================

  if (esquerda && direita) {

    pararMotor();

    return;
  }


  // ===================================================
  // SENTIDO SOLICITADO
  // ===================================================

  int novoSentido;


  if (esquerda) {

    novoSentido =
      SENTIDO_ESQUERDA;

  }

  else {

    novoSentido =
      SENTIDO_DIREITA;

  }


  // ===================================================
  // FIM DE CURSO BAIXO
  // ===================================================
  //
  // Direita diminui tensão.
  //

  if (
    fimDeCurso == -1 &&
    novoSentido == SENTIDO_DIREITA
  ) {

    pararMotor();

    return;
  }


  // ===================================================
  // FIM DE CURSO ALTO
  // ===================================================
  //
  // Esquerda aumenta tensão.
  //

  if (
    fimDeCurso == 1 &&
    novoSentido == SENTIDO_ESQUERDA
  ) {

    pararMotor();

    return;
  }


  // ===================================================
  // INÍCIO DO MOVIMENTO
  // ===================================================

  if (
    sentidoMotor == SENTIDO_PARADO &&
    !aguardandoTempoMorto
  ) {

    sentidoSolicitado =
      novoSentido;


    sentidoMotor =
      novoSentido;


    inicioMovimento =
      millis();
  }


  // ===================================================
  // INVERSÃO
  // ===================================================

  else if (
    novoSentido != sentidoMotor &&
    !aguardandoTempoMorto
  ) {

    desligarMotor();


    sentidoSolicitado =
      novoSentido;


    sentidoMotor =
      SENTIDO_PARADO;


    aguardandoTempoMorto =
      true;


    inicioTempoMorto =
      millis();


    mostrarMovimento(
      SENTIDO_PARADO,
      0
    );


    return;
  }


  // ===================================================
  // TEMPO MORTO
  // ===================================================

  if (aguardandoTempoMorto) {

    desligarMotor();


    if (
      millis() - inicioTempoMorto <
      TEMPO_MORTO
    ) {

      return;
    }


    bool aindaEsquerda =
      digitalRead(BTN_ESQ) == LOW;


    bool aindaDireita =
      digitalRead(BTN_DIR) == LOW;


    // -------------------------------------------------
    // ESQUERDA
    // -------------------------------------------------

    if (
      aindaEsquerda &&
      !aindaDireita &&
      sentidoSolicitado == SENTIDO_ESQUERDA
    ) {

      if (fimDeCurso == 1) {

        pararMotor();

        return;
      }


      sentidoMotor =
        SENTIDO_ESQUERDA;
    }


    // -------------------------------------------------
    // DIREITA
    // -------------------------------------------------

    else if (
      aindaDireita &&
      !aindaEsquerda &&
      sentidoSolicitado == SENTIDO_DIREITA
    ) {

      if (fimDeCurso == -1) {

        pararMotor();

        return;
      }


      sentidoMotor =
        SENTIDO_DIREITA;
    }


    else {

      pararMotor();

      return;
    }


    aguardandoTempoMorto =
      false;


    inicioMovimento =
      millis();
  }


  // ===================================================
  // PWM
  // ===================================================

  unsigned long tempoPressionado =
    millis() - inicioMovimento;


  uint8_t pwm =
    calcularPWM(
      tempoPressionado
    );


  // ===================================================
  // SETAS
  // ===================================================

  mostrarMovimento(
    sentidoMotor,
    pwm
  );


  // ===================================================
  // BTS7960
  // ===================================================

  if (
    sentidoMotor ==
    SENTIDO_DIREITA
  ) {

    moverDireita(
      pwm
    );

  }


  else if (
    sentidoMotor ==
    SENTIDO_ESQUERDA
  ) {

    moverEsquerda(
      pwm
    );
  }
}


// =====================================================
// SETUP
// =====================================================

void setup()
{
  // ===================================================
  // SENSOR
  // ===================================================

  pinMode(
    VOLTAGE_PIN,
    INPUT
  );


  // ===================================================
  // BOTÕES
  // ===================================================

  pinMode(
    BTN_ESQ,
    INPUT_PULLUP
  );


  pinMode(
    BTN_DIR,
    INPUT_PULLUP
  );


  // ===================================================
  // BTS7960
  // ===================================================

  pinMode(
    BTS_RPWM,
    OUTPUT
  );


  pinMode(
    BTS_LPWM,
    OUTPUT
  );


  desligarMotor();


  // ===================================================
  // DISPLAY
  // ===================================================

  tft.init(
    240,
    240
  );


  tft.setRotation(2);


  desenharTela();


  // ===================================================
  // PRIMEIRA LEITURA
  // ===================================================

  float tensaoInicial =
    lerTensao();


  tensaoFiltrada =
    tensaoInicial;


  atualizarFimDeCurso(
    tensaoInicial
  );


  float azimuteInicial =
    calcularAzimute(
      tensaoFiltrada
    );


  // ===================================================
  // PRIMEIRO DESENHO
  // ===================================================

  mostrarAzimute(
    azimuteInicial
  );


  mostrarDirecao(
    azimuteInicial
  );


  mostrarBarraPosicao(
    tensaoFiltrada
  );


  mostrarMovimento(
    SENTIDO_PARADO,
    0
  );
}


// =====================================================
// LOOP
// =====================================================

void loop()
{
  // ===================================================
  // LEITURA DIRETA DO SENSOR
  // ===================================================

  float tensao =
    lerTensao();


  // ===================================================
  // FIM DE CURSO
  // ===================================================

  atualizarFimDeCurso(
    tensao
  );


  // ===================================================
  // MOTOR
  // ===================================================

  atualizarMotor();


  // ===================================================
  // FILTRO PARA DISPLAY
  // ===================================================

  tensaoFiltrada =
    tensaoFiltrada *
    (1.0 - FILTRO_ALPHA)
    +
    tensao *
    FILTRO_ALPHA;


  // ===================================================
  // AZIMUTE
  // ===================================================

  float azimute =
    calcularAzimute(
      tensaoFiltrada
    );


  // ===================================================
  // DISPLAY
  // ===================================================

  mostrarAzimute(
    azimute
  );


  mostrarDirecao(
    azimute
  );


  mostrarBarraPosicao(
    tensaoFiltrada
  );


  // Sem delay()
}

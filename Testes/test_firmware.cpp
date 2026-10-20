// Compila o .ino real com IO substituido para testar a logica, sem Arduino.
// Nao valida bootloader, temporizacao SPI, circuito, nem inercia real.
#include "stubs/Arduino.h"
#include <iostream>
unsigned long clock_ms=0;
int pins[20]={};
double sensor_voltage=2.6;
uint8_t MCUSR=0;
FakeSerial Serial;
#include "../Arduino/rotor_1_2/rotor_1_2.ino"

void set_position(double p) { sensor_voltage = 4.8-p*4.4/360.0; }
void command(const std::string& s) {
  Serial.inject(s+"\n");
  while (Serial.available()) receberSerial();
}
void step(double speed=0) {
  if (speed && sentidoMotor) {
    double p = (4.8-sensor_voltage)*360.0/4.4;
    p += sentidoMotor * (pwmAtual/220.0) * speed * .020;
    set_position(p);
  }
  clock_ms+=20;
  loop();
}
void advance(unsigned long ms, double speed=0, bool ping=false) {
  for (unsigned long t=0;t<ms;t+=20) {
    if (ping && t%200==0) command("PING");
    step(speed);
  }
}
void stopped() { assert(sentidoMotor==0 && pwmAtual==0 && pins[3]==0 && pins[5]==0); }

int main(int argc, char** argv) {
  assert(argc==2);
  std::string name=argv[1];
  pins[2]=pins[4]=HIGH;
  set_position(120); setup();
  assert(Serial.tx.find("BOOT,1.2\nROTOR,2,1.2")!=std::string::npos);
  Serial.tx.clear();
  if (name=="local_ramp") {
    pins[4]=LOW; advance(200); assert(modo==LOCAL && sentidoMotor==1 && pwmAtual==70);
    advance(520,10); assert(pwmAtual==90);
    advance(2000,10); assert(pwmAtual==220);
    pins[4]=HIGH; step(); stopped();
  } else if (name=="remote_jog") {
    command("JOG,L"); step(); assert(modo==JOG_USB && sentidoMotor==-1);
    for (int i=0;i<20;i++) { command("JOG,L"); advance(150,10,true); }
    assert(pwmAtual==220); command("STOP"); stopped();
  } else if (name=="jog_expiry") {
    command("JOG,R"); advance(600,10,true);
    stopped(); assert(motivo==LINK);
  } else if (name=="link_expiry") {
    command("MOVE,300"); advance(1100,10);
    stopped(); assert(motivo==LINK);
    command("PING"); advance(200); stopped(); // nao retoma apos link voltar.
  } else if (name=="auto_profile") {
    command("MOVE,200"); int peak=0; bool decelerated=false;
    for (int i=0;i<3000 && (modo==AUTO_USB);i++) {
      if(i%10==0) command("PING");
      step(12);
      if(pwmAtual>peak) peak=pwmAtual;
      if(peak==220 && pwmAtual<120 && modo==AUTO_USB) decelerated=true;
    }
    stopped(); assert(motivo==ALVO && peak==220 && decelerated);
    assert(fabs(posicaoMecanica-200)<1.6);
  } else if (name=="north_nearest") {
    set_position(358); advance(100);
    command("MOVE,0"); assert(fabs(alvoMecanico-360)<.01);
    advance(5000,8,true); stopped(); assert(motivo==ALVO);
    set_position(1); advance(100); command("MOVE,359");
    assert(fabs(alvoMecanico+1)<.01); // overlap acessivel; volta curta.
    advance(5000,8,true); stopped(); assert(motivo==ALVO);
  } else if (name=="limited_wrap") {
    set_position(5); advance(100); command("MOVE,355");
    assert(fabs(alvoMecanico-355)<.01); // -5 excede margem: nao gira ilimitado.
    command("STOP"); stopped();
  } else if (name=="inversion") {
    command("JOG,R"); advance(40,10); assert(sentidoMotor==1);
    command("STOP"); command("JOG,L"); advance(80); stopped();
    advance(20); assert(sentidoMotor==-1 && pwmAtual==70);
  } else if (name=="physical_priority") {
    command("MOVE,250"); advance(100,10,true);
    pins[2]=LOW; advance(40); assert(modo==LOCAL);
    command("JOG,R"); assert(modo==LOCAL);
    pins[2]=HIGH; step(); stopped(); assert(modo==PARADO);
    advance(200); stopped();
  } else if (name=="both_buttons") {
    pins[2]=pins[4]=LOW; advance(40); stopped(); assert(motivo==DOIS_BOTOES);
    pins[4]=HIGH; advance(200); stopped();
    pins[2]=HIGH; advance(40); assert(motivo==OPERADOR);
    pins[2]=LOW; advance(200); assert(sentidoMotor==-1);
  } else if (name=="electronic_limits") {
    sensor_voltage=.29; advance(100); command("JOG,R"); step(); stopped(); assert(motivo==LIMITE);
    command("JOG,L"); step(); assert(sentidoMotor==-1); // permite afastar do limite.
    command("STOP"); sensor_voltage=4.91; advance(100);
    command("JOG,L"); step(); stopped(); assert(motivo==LIMITE);
    command("JOG,R"); advance(120); assert(sentidoMotor==1);
  } else if (name=="sensor_fault") {
    command("MOVE,250"); advance(100,10,true);
    sensor_voltage=.05; step(); stopped(); assert(modo==FALHA && motivo==SENSOR);
    command("STOP"); assert(modo==FALHA);
    set_position(130); advance(40); assert(modo==FALHA);
    command("STOP"); assert(modo==PARADO);
  } else if (name=="stall_fault") {
    command("MOVE,250"); advance(8200,0,true);
    stopped(); assert(modo==FALHA && motivo==TRAVADO);
    command("MOVE,180"); assert(modo==FALHA);
    command("STOP"); assert(modo==PARADO);
  } else if (name=="max_time") {
    command("MOVE,350"); advance(181000,1,true);
    stopped(); assert(modo==FALHA && motivo==TEMPO);
  } else if (name=="stop_local_latch") {
    pins[4]=LOW; advance(200); assert(sentidoMotor==1);
    command("STOP"); advance(200); stopped();
    pins[4]=HIGH; advance(40); pins[4]=LOW; advance(200); assert(sentidoMotor==1);
  } else if (name=="invalid_commands") {
    for (auto s: {"MOVE,nan", "MOVE,inf", "MOVE,361", "MOVE,-1", "MOVE,", "MOVE,10x"}) {
      command(s); assert(modo==PARADO);
    }
    command(std::string(80,'X')); assert(Serial.tx.find("ERR,LINE")!=std::string::npos);
    Serial.inject("MOVE,"); receberSerial(); advance(300);
    command("180"); assert(modo==PARADO);
    command("MOVE,180"); assert(modo==AUTO_USB);
  } else if (name=="speed_limits") {
    for (int level=1;level<=6;++level) {
      command("SPEED,"+std::to_string(level));
      for (int direction: {-1,1}) {
        set_position(170); advance(100);
        command(direction<0 ? "JOG,L" : "JOG,R");
        for (int i=0;i<22;++i) { command(direction<0 ? "JOG,L" : "JOG,R"); advance(150,8,true); assert(pwmAtual<=niveisPWM[level-1]); }
        assert(pwmAtual==niveisPWM[level-1]);command("STOP");
        int button=direction<0?2:4;pins[button]=LOW;advance(200);
        for (int i=0;i<160;++i) { step(8);assert(pwmAtual<=niveisPWM[level-1]); }
        assert(pwmAtual==niveisPWM[level-1]);pins[button]=HIGH;step();stopped();
      }
      set_position(80);advance(100);command("MOVE,300");
      advance(3500,8,true);assert(pwmAtual==niveisPWM[level-1]);command("STOP");
    }
  } else if (name=="speed_reduce_moving") {
    command("JOG,R");
    for(int i=0;i<22;++i) { command("JOG,R");advance(150,8,true); }
    assert(pwmAtual==220);command("SPEED,2");
    assert(pwmAtual<=90 && pins[3]<=90);command("STOP");
    command("SPEED,6");command("MOVE,300");advance(3500,8,true);
    assert(pwmAtual==220);command("SPEED,1");assert(pwmAtual<=70 && pins[3]<=70);
  } else if (name=="speed_increase_moving") {
    command("SPEED,1");command("JOG,R");
    for(int i=0;i<22;++i) { command("JOG,R");advance(150,8,true); }
    assert(pwmAtual==70);command("SPEED,6");step(8);assert(pwmAtual<=71);
    for(int i=0;i<22;++i) { command("JOG,R");advance(150,8,true); }
    assert(pwmAtual==220);
  } else if (name=="speed_persistence") {
    command("SPEED,4");int writes=EEPROM.writes;
    command("SPEED,4");assert(EEPROM.writes==writes);
    nivelMaximo=6;carregarVelocidade();assert(nivelMaximo==4);
    command("SPEED,2");nivelMaximo=6;carregarVelocidade();assert(nivelMaximo==2);
    for(int i=0;i<300;++i) { uint8_t level=1+i%6;salvarVelocidade(level);nivelMaximo=6;carregarVelocidade();assert(nivelMaximo==level); }
    command("SPEED,2");
    for(auto bad: {"SPEED,0","SPEED,7","SPEED,-1","SPEED,2x","SPEED,22","SPEED,"}) command(bad);
    assert(nivelMaximo==2);assert(Serial.tx.find("ERR,SPEED")!=std::string::npos);
    command("SPEED?");assert(Serial.tx.find("SPEED,2")!=std::string::npos);
  } else if (name=="speed_power_loss") {
    command("SPEED,2");FakeEEPROM original=EEPROM;
    for(int cut=0;cut<8;++cut) {
      EEPROM=original;carregarVelocidade();EEPROM.cut_after=cut;
      try { salvarVelocidade(5); } catch(const std::runtime_error&) {}
      EEPROM.cut_after=-1;carregarVelocidade();
      assert(nivelMaximo==2 || nivelMaximo==5);
    }
    EEPROM=FakeEEPROM();EEPROM.bytes[0]=42;carregarVelocidade();assert(nivelMaximo==1);
  } else if (name=="speed_menu") {
    pins[2]=LOW;advance(80);stopped(); // combina sem pulso de movimento
    pins[4]=LOW;advance(2100);stopped();assert(modo==CONFIGURACAO);
    command("MOVE,250");assert(modo==CONFIGURACAO);stopped();
    command("JOG,L");assert(modo==CONFIGURACAO);stopped();
    command("SPEED,1");assert(nivelMaximo==6 && modo==CONFIGURACAO);
    advance(500);assert(modo==CONFIGURACAO); // pressao de entrada nao confirma
    pins[2]=pins[4]=HIGH;advance(40);
    pins[2]=LOW;advance(200);assert(nivelEdicao==5);advance(1000);assert(nivelEdicao==5);stopped();
    pins[2]=HIGH;advance(40);pins[2]=LOW;advance(200);assert(nivelEdicao==4);
    pins[2]=pins[4]=HIGH;advance(40);
    pins[2]=pins[4]=LOW;advance(40);assert(modo==PARADO && nivelMaximo==4);stopped();
    pins[4]=HIGH;advance(200);stopped(); // nenhum giro ao soltar apenas uma tecla
    pins[2]=HIGH;advance(40);pins[4]=LOW;advance(200);assert(sentidoMotor==1);
  } else if (name=="moving_both_not_menu") {
    command("JOG,R");advance(100,8,true);assert(sentidoMotor==1);
    pins[2]=pins[4]=LOW;step();stopped();advance(2300);
    assert(modo==PARADO); // parada em movimento nunca abre o menu
    pins[2]=pins[4]=HIGH;advance(40);
    pins[2]=pins[4]=LOW;advance(2100);assert(modo==CONFIGURACAO);stopped();
  } else if (name=="menu_sensor_fault") {
    pins[2]=pins[4]=LOW;advance(2100);assert(modo==CONFIGURACAO);
    sensor_voltage=.02;step();assert(modo==FALHA && motivo==SENSOR);stopped();
    command("STOP");assert(modo==FALHA);
  } else if (name=="telemetry") {
    advance(100);
    assert(Serial.tx.find("STAT,")!=std::string::npos);
    std::cout<<Serial.tx;
  } else { assert(false); }
  std::cout<<"PASS "<<name<<"\n";
}

#pragma once
#include "Arduino.h"
#define ST77XX_BLACK 0
#define ST77XX_WHITE 65535
#define ST77XX_CYAN 2047
#define ST77XX_YELLOW 65504
#define ST77XX_GREEN 2016
#define ST77XX_RED 63488
struct Adafruit_ST7789 {
  Adafruit_ST7789(int,int,int) {}
  void init(int,int) {}
  void setRotation(int) {}
  void fillScreen(int) {}
  void setTextWrap(bool) {}
  void setTextSize(int) {}
  void setTextColor(int,int=0) {}
  void setCursor(int,int) {}
  void drawFastHLine(int,int,int,int) {}
  void drawRect(int,int,int,int,int) {}
  void fillRect(int,int,int,int,int) {}
  template<class T> void print(T) {}
};

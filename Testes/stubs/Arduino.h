#pragma once
#include <cstdint>
#include <cstdio>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <string>
#include <sstream>
#include <iomanip>
#include <cassert>
#define A0 14
#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1
#define INPUT_PULLUP 2
#define F(x) x
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
#define constrain(v,a,b) (min(max((v),(a)),(b)))
using std::isfinite;
extern unsigned long clock_ms;
extern int pins[20];
extern double sensor_voltage;
extern uint8_t MCUSR;
inline unsigned long millis() { return clock_ms; }
inline void pinMode(int, int) {}
inline int digitalRead(int p) { return pins[p]; }
inline int analogRead(int) { return (int)std::round(sensor_voltage*1023.0/5.0); }
inline void analogWrite(int p, int v) {
  pins[p] = v;
  assert(!(pins[3] && pins[5]));
}
struct FakeSerial {
  std::deque<char> rx;
  std::string tx;
  void begin(int) {}
  int available() { return rx.size(); }
  char read() { char c=rx.front(); rx.pop_front(); return c; }
  void inject(const std::string& s) { for (char c:s) rx.push_back(c); }
  void print(const char* s) { tx += s; }
  void print(char c) { tx += c; }
  template<class T> void print(T v) { tx += std::to_string(v); }
  void print(float v, int n) { std::ostringstream o; o<<std::fixed<<std::setprecision(n)<<v; tx+=o.str(); }
  void println() { tx+='\n'; }
  template<class T> void println(T v) { print(v); println(); }
};
extern FakeSerial Serial;

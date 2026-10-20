#pragma once
#include <cstdint>
#include <cstring>
#include <stdexcept>
struct FakeEEPROM {
  uint8_t bytes[1024];
  int writes = 0;
  int cut_after = -1;
  FakeEEPROM() { memset(bytes, 0xFF, sizeof(bytes)); }
  uint8_t read(int p) { return bytes[p]; }
  void update(int p, uint8_t value) {
    if (bytes[p] == value) return;
    if (cut_after == 0) throw std::runtime_error("power loss");
    if (cut_after > 0) --cut_after;
    bytes[p] = value; ++writes;
  }
};
static FakeEEPROM EEPROM;

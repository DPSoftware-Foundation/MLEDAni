# Maxleda Studio (Matrix LED Animator)

![output](https://github.com/user-attachments/assets/4948ad26-1a73-47d5-b362-59cbd853a609)
![20251124_183101(1)](https://github.com/user-attachments/assets/f6c96102-806e-459d-9153-b19bfcafdd5e)

A maxtrix led tools for animate and export to arduino code easier. 


Feature
- [x] In software animator (Beta)
- [x] Preview
- [x] Export to arduino code
- [ ] Layout editing (Still need to edit at project file)
- [ ] Keyframes
- [ ] Audio Visualizer
- [ ] Video to sequence
- [ ] Live preview to real device
- [ ] Text scrolling

Now support export to 
- [DPH_MAX7219](https://github.com/damp11113/DPH_MAX7219)


Supported Protocol
- [x] MAX7219 LED Matrix (Via DPH_MAX7219)
- [ ] 74HC595
- [ ] NeoPixel or WS28xx/SK68xx
- [ ] DMX512
- [ ] Custom (PWM, DAC, Digital Protocol)

Certified MCU for Live Preview
- [x] ESP32- S2, S3, C3, C6 and H2 (Via USB-CDC)
- [x] RP2xxx (Via USB-CDC)
- [x] STM32F103 Bluepill (Via USB-CDC)
- [x] STM32F411 Blackpill (Via USB-CDC)
- [ ] ESP32 (Via Serial)
- [ ] ESP8266 (Via Serial)
- [ ] ATmega328p (Via Serial)

Live preview maybe not work well with Serial because limit of bauds rates.


## Wireless Pulse Monitoring System

A wireless pulse monitoring system using two Raspberry Pi units. This system will capture pulse signals through a sensor, transmit the data over Bluetooth, and display the pulse data along with other relevant health metrics on a GUI at the receiving end.

## Built With

### Hardwares
* Two Raspberry Pi units
* ADC (Analog to Digital Converter) modules
* Pulse sensor
* Necessary cables and accessories

### Structure
* `sender.py`: Get sensor data and send to the receiver
* `receiver.py`: Receive sensor data and show the GUI
* `assets/*.png`: Images for GUI
* `assets/target_bpm_data.json`: Target BPM for different age groups

### Softwares
* Python

### Libraries
* socket
* bluetooth
* smbus


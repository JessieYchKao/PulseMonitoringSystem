from PyQt5.QtWidgets import QApplication, QFrame, QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout, QLineEdit, QVBoxLayout, QFormLayout, QGraphicsDropShadowEffect, QFileDialog, QScrollArea, QColorDialog, QStackedWidget, QMainWindow, QGridLayout, QSpacerItem, QSizePolicy
from PyQt5.QtGui import QPixmap, QImageReader, QIcon, QCursor, QFont, QPainter, QPainterPath, QLinearGradient, QColor, QPen, QBrush, QBitmap, QImage, QMovie
from PyQt5.QtCore import Qt, QSize, QRect, QTimer, QObject, pyqtSignal, QThread, QEasingCurve, QPropertyAnimation
import pyqtgraph as pg
import numpy as np
import math
import random
import sys
import time
import subprocess
import bluetooth
from statistics import *
import smbus
import json

host_mac_address = 'D8:3A:DD:3C:D9:91'  # Replace with the Bluetooth adapter MAC address of the server

port = 4
backlog = 1
size = 1024

PATH = "/home/pi/mu_code/WSAN/Pulse-Monitoring-System/assets/"

# Sliding window data survival time (seconds)
WINDOW_SIZE = 60

bus = smbus.SMBus(1)
adc_address = 0x4b
threshold = 128

username = ""
age = 18
heart_rate_range = {"min": 60,"max": 120}

class BluetoothPairingThread(QThread):
    pairing_complete = pyqtSignal()

    def run(self):
        # Pairing using bluetoothctl
        subprocess.call(['bluetoothctl', 'discoverable', 'yes'])
        subprocess.call(['bluetoothctl', 'pairable', 'yes'])

        server_socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        server_socket.bind((host_mac_address, port))
        server_socket.listen(backlog)

        print("Waiting for connection...")
        global client_socket
        client_socket, client_info = server_socket.accept()
        print(f"Accepted connection from {client_info}")
        self.pairing_complete.emit()

class UserInitializationThread(QThread):
    initialization_complete = pyqtSignal()

    def run(self):
        global threshold
        cur_time = time.time()
        start_time = cur_time
        calcList = np.array([])

        while cur_time - start_time < 20:
            cur_time = time.time()
            data = client_socket.recv(size)
            if data:
                signal = int(data)
                if signal <= 255:
                    calcList = np.append(calcList, signal)

        threshold = ((np.max(calcList) - np.min(calcList)) * 0.9) + np.min(calcList)
        #threshold = np.max(calcList) * 0.9
        print("min: ", np.min(calcList))
        print("max: ", np.max(calcList))
        print("Threshold: ", threshold)

        # Signal that initialization is complete
        self.initialization_complete.emit()

class CalcBPM(QObject):
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super(CalcBPM, self).__init__(parent)
        self.bpmList = np.array([])
        self.running = False
        self.bpm = -1
        self.rmssd = -1
        self.hrstd = -1
        self.time_interval_beat = [] # For calculating RMSSD
        self.TIME_INTERVAL = 10 # Frequency of calculating the BPM (seconds)

    def run(self):
        while True:
            global WINDOW_SIZE, client_socket, threshold
            slide_idx = 0 # current sliding window index
            data_size = 0 # If current data_size exceeds the window size, start to show BPM
            self.time_interval_beat = []
            bmp_sliding_window = np.array([])
            while self.running:
                cur_time = time.time()
                start_time = cur_time
                count = 0
                prev_beat = 0 # For calculating RMSSD
                while cur_time - start_time < self.TIME_INTERVAL:
                    data = client_socket.recv(size)
                    if data:
                        signal = int(data)
                        if signal <= 255:
                            self.bpmList = np.append(self.bpmList, signal)

                            if signal > threshold: # Detect a hearbeat
                                beat = time.time()
                                if count > 0:
                                    self.time_interval_beat.append(round(abs((beat - prev_beat)*1000),2))
                                    # Maintain only last WINDOW_SIZE seconds data
                                    self.time_interval_beat = self.time_interval_beat[int(-1*WINDOW_SIZE/0.25):]

                                prev_beat = beat
                                count += 1

                    cur_time = time.time()

                # Update BPM
                print("count: ", count)
                cur_bpm = count * (60 / self.TIME_INTERVAL)
                print("BPM (10 sec): ", cur_bpm)
                bmp_sliding_window = np.append(bmp_sliding_window, cur_bpm)
                bmp_sliding_window = bmp_sliding_window[(-1*int(WINDOW_SIZE / self.TIME_INTERVAL)):] # Remove old data
                print("sliding windows: ", bmp_sliding_window)

                # Update BPM, RMSSD, HRSTD
                if len(bmp_sliding_window) >= (WINDOW_SIZE / self.TIME_INTERVAL):
                    self.bpm = np.mean(bmp_sliding_window, axis=0)
                    self.rmssd, self.hrstd = self.calculate_rms()
                start_time = time.time()


    #RMSSD( 19ms - 48-50ms ), HRSTD - ideal values
    def calculate_rms(self):
        if len(self.time_interval_beat) == 0:
            return -1, -1
        rms_arr = []
        for i in range(1, len(self.time_interval_beat)):
            rms_arr.append(round(abs(self.time_interval_beat[i] - self.time_interval_beat[i-1]),2))

        rms = round(math.sqrt(np.square(rms_arr).mean()),2)
        hrstd = round(stdev(rms_arr),2)

        return rms, hrstd

class BPMPage(QWidget):
    def __init__(self, parent=None):
        super(BPMPage, self).__init__(parent)
        self.gridWidget = QGridLayout(self)

        self.title = QLabel("Hi there,", self)
        self.title.setAlignment(Qt.AlignCenter)
        self.gridWidget.addWidget(self.title, 0, 0, 1, 6, alignment=Qt.AlignCenter)
        self.title.setStyleSheet("font-size: 35px; font-weight: bold; color: white; background: transparent;")

        self.sugMinLabel = QLabel("Suggest min", self)
        self.gridWidget.addWidget(self.sugMinLabel, 1, 0, 1, 2, alignment=Qt.AlignCenter)
        self.sugMinLabel.setStyleSheet("font-size: 15px; color: #BDBDBD; background: transparent;")

        self.sugMinVal = QLabel("60", self)
        self.gridWidget.addWidget(self.sugMinVal, 2, 0, 1, 2, alignment=Qt.AlignCenter)
        self.sugMinVal.setStyleSheet("font-size: 28px; color: white; background: transparent;")

        self.heartBtn = QPushButton(self)
        self.heartBtn.setCursor(QCursor(Qt.PointingHandCursor))
        self.heartBtn.setStyleSheet("border: none; background: transparent;")
        self.heartBtn.setIcon(QIcon(PATH + 'heart_init.png'))
        self.heartBtn.setIconSize(QSize(160,160))
        self.heartBtn.clicked.connect(self.start_button_clicked)
        self.gridWidget.addWidget(self.heartBtn, 1, 2, 2, 2, alignment=Qt.AlignCenter)

        self.sugMaxLabel = QLabel("Suggest max", self)
        self.gridWidget.addWidget(self.sugMaxLabel, 1, 4, 1, 2, alignment=Qt.AlignCenter)
        self.sugMaxLabel.setStyleSheet("font-size: 15px; color: #BDBDBD; background: transparent;")

        self.sugMaxVal = QLabel("120", self)
        self.gridWidget.addWidget(self.sugMaxVal, 2, 4, 1, 2, alignment=Qt.AlignCenter)
        self.sugMaxVal.setStyleSheet("font-size: 28px; color: white; background: transparent;")


        # BPM value
        self.bpmValue = QLabel("--")
        self.bpmValue.setStyleSheet("font-size: 80px; font-weight: bold; color: white; background: transparent;")
        self.gridWidget.addWidget(self.bpmValue, 3, 2, alignment=Qt.AlignCenter)


        # BPM unit
        self.bpmUnit = QLabel("BPM")
        self.bpmUnit.setStyleSheet("font-size: 20px; font-weight: bold; color: white; background: transparent;")
        self.gridWidget.addWidget(self.bpmUnit, 3, 3, alignment=Qt.AlignCenter)

        # graph
        self.graphWidget = QWidget(self)
        self.gridWidget.addWidget(self.graphWidget, 5, 0, 1, 6, alignment=Qt.AlignCenter)

        # Create a QVBoxLayout for the graphWidget
        self.graphLayout = QVBoxLayout(self.graphWidget)

        # Create a pyqtgraph PlotWidget
        self.plotWidget = pg.PlotWidget()

        # Hide axes and grid lines

        self.plotWidget.getAxis('bottom').setStyle(showValues=False)
        self.plotWidget.getAxis('left').setStyle(showValues=False)
        self.plotWidget.getPlotItem().hideAxis('bottom')  # Hide X-axis completely
        self.plotWidget.getPlotItem().hideAxis('left')    # Hide Y-axis completely

        self.graphLayout.addWidget(self.plotWidget)

        # Initialize pyqtgraph PlotDataItem
        self.curve = self.plotWidget.plot()
        color = QColor(255, 0, 0)
        self.curve.setPen(color)

        self.plotWidget.setXRange(0, (15/0.25), padding=0)
        #self.plotWidget.setYRange(0, 180, padding=0)

        # Other info
        self.impGrid = QGridLayout()
        self.ipmLabel = QLabel("IPM")
        self.ipmLabel.setAlignment(Qt.AlignCenter)
        self.ipmLabel.setStyleSheet("font-size: 14px; color: grey; background: transparent;")
        self.impGrid.addWidget(self.ipmLabel, 0, 0, alignment=Qt.AlignCenter)
        self.ipmValue = QLabel("--")
        self.ipmValue.setStyleSheet("font-size: 28px; color: white; background: transparent;")
        self.impGrid.addWidget(self.ipmValue, 1, 0, alignment=Qt.AlignCenter)
        self.gridWidget.addLayout(self.impGrid, 6, 0)


        self.hrstdGrid = QGridLayout()
        self.hrstdLabel = QLabel("HRSTD")
        self.hrstdLabel.setAlignment(Qt.AlignCenter)
        self.hrstdLabel.setStyleSheet("font-size: 14px; color: grey; background: transparent;")
        self.hrstdGrid.addWidget(self.hrstdLabel, 0, 0, alignment=Qt.AlignCenter)
        self.hrstdValue = QLabel("--")
        self.hrstdValue.setStyleSheet("font-size: 28px; color: white; background: transparent;")
        self.hrstdGrid.addWidget(self.hrstdValue, 1, 0, alignment=Qt.AlignCenter)
        self.gridWidget.addLayout(self.hrstdGrid, 6, 2)


        self.rmssdGrid = QGridLayout()
        self.rmssdLabel = QLabel("RMSSD")
        self.rmssdLabel.setAlignment(Qt.AlignCenter)
        self.rmssdLabel.setStyleSheet("font-size: 14px; color: grey; background: transparent;")
        self.rmssdGrid.addWidget(self.rmssdLabel, 0, 0, alignment=Qt.AlignCenter)
        self.rmssdValue = QLabel("--")
        self.rmssdValue.setStyleSheet("font-size: 28px; color: white; background: transparent;")
        self.rmssdGrid.addWidget(self.rmssdValue, 1, 0, alignment=Qt.AlignCenter)
        self.gridWidget.addLayout(self.rmssdGrid, 6, 4)


        self.calcBPM = CalcBPM()
        self.thread = QThread()
        self.calcBPM.moveToThread(self.thread)


        self.calcBPM.bpmList = np.array([])


        self.thread.started.connect(self.calcBPM.run)
        self.thread.start()

    def showEvent(self, event):
        # This method is called when the widget is shown
        super(BPMPage, self).showEvent(event)

        # Retreive heart_rate_range from JSON file
        global username, age, heart_rate_range

        with open(PATH + 'target_bpm_data.json', 'r') as file:
            heart_rate_data = json.load(file)
        for age_group, rate_range in heart_rate_data.items():
            age_range = list(map(int, age_group.split('-')))
            if age_range[0] <= int(age) < age_range[1]:
                heart_rate_range = rate_range
                print(rate_range)
                break

        self.title.setText("Hi " + username + ",")
        self.sugMinVal.setText(str(heart_rate_range.get('min', 0)))
        self.sugMaxVal.setText(str(heart_rate_range.get('max', 0)))

        self.bpm_timer = QTimer(self)
        self.bpm_timer.timeout.connect(self.update_graph)

    # Update the graph with new dialog data (last 60 seconds)
    def update_graph(self):
        self.calcBPM.bpmList = self.calcBPM.bpmList[int(-1*(15/0.25)):]
        self.curve.setData(np.arange(0, self.calcBPM.bpmList.size, 1), self.calcBPM.bpmList)
        self.bpmValue.setText((str(self.calcBPM.bpm) if self.calcBPM.bpm >= 0 else "--"))
        self.ipmValue.setText((str(self.calcBPM.bpm) if self.calcBPM.bpm >= 0 else "--"))
        self.hrstdValue.setText((str(self.calcBPM.hrstd) if self.calcBPM.hrstd >= 0 else "--"))
        self.rmssdValue.setText((str(self.calcBPM.rmssd) if self.calcBPM.rmssd >= 0 else "--"))


    def start_button_clicked(self):
        self.calcBPM.running = True
        self.bpm_timer.start(200)  # Graph update thread
        self.heartBtn.setIcon(QIcon(PATH + 'heart_stop.png'))
        self.heartBtn.clicked.connect(self.stop_button_clicked)

    def stop_button_clicked(self):
        self.bpm_timer.stop()
        self.calcBPM.running = False

        # Clear the bpmList
        self.calcBPM.bpmList = np.array([])
        self.calcBPM.bpm = -1
        self.curve.setData(np.arange(0, self.calcBPM.bpmList.size, 1), self.calcBPM.bpmList)
        self.bpmValue.setText("--")
        self.heartBtn.setIcon(QIcon(PATH + 'heart_init.png'))
        self.heartBtn.clicked.connect(self.start_button_clicked)

class LandingPage(QWidget):
    def __init__(self, parent=None):
        super(LandingPage, self).__init__(parent)
        self.gridWidget = QGridLayout(self)

        self.title = QLabel("PULSE MONITORING SYSTEM", self)
        self.gridWidget.addWidget(self.title, 0, 0, alignment=Qt.AlignCenter)
        self.title.setStyleSheet("font-size: 24px; font-weight: bold; color: white; background: transparent;")

        self.subtitle = QLabel("Before the measurement,\nplease enter your information, place your finger on the sensor and click \"Go\"", self)
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.gridWidget.addWidget(self.subtitle, 1, 0, alignment=Qt.AlignCenter)
        self.subtitle.setStyleSheet("font-size: 18px; color: white; background: transparent;")

        self.imgBtn = QPushButton(self)
        self.imgBtn.setStyleSheet("border: none; background: transparent;")
        self.imgBtn.setIcon(QIcon(PATH + 'cover.png'))
        self.imgBtn.setIconSize(QSize(160,160))
        self.gridWidget.addWidget(self.imgBtn, 2, 0, alignment=Qt.AlignCenter)

        self.username = QLineEdit()
        self.username.setMaximumWidth(150)
        self.username.setPlaceholderText("Name")
        self.gridWidget.addWidget(self.username, 3, 0, alignment=Qt.AlignCenter)
        self.username.setStyleSheet("background: #373737; border-radius: 5px; outline: one; border: none; height: 40px; color: white; padding: 5px;")

        self.age = QLineEdit()
        self.age.setMaximumWidth(150)
        self.age.setPlaceholderText("Age")
        self.gridWidget.addWidget(self.age, 4, 0, alignment=Qt.AlignCenter)
        self.age.setStyleSheet("background: #373737; border-radius: 5px; outline: one; border: none; height: 40px; color: white; padding: 5px;")

        self.pair_label = QLabel("Pairing Successful", self)
        self.pair_label.setVisible(False)
        self.pair_label.setFixedSize(610, 1200)
        self.pair_label.setAlignment(Qt.AlignCenter)
        self.pair_label.setStyleSheet("font-size: 15px; font-weight: bold; background: transparent; color: green")

        self.initBtn = QPushButton("Go")
        self.initBtn.clicked.connect(self.go_clicked)
        self.gridWidget.addWidget(self.initBtn, 5, 0, alignment=Qt.AlignCenter)
        self.initBtn.setCursor(QCursor(Qt.PointingHandCursor))
        self.initBtn.setStyleSheet("font-size: 18px; font-weight: bold; color: white; background: #6D5ACC; border: none; padding: 10px; border-radius: 15px; width: 200px;")

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.pair_label)
        self.layout.setAlignment(Qt.AlignCenter)

    def go_clicked(self):
        self.username.setEnabled(False)
        self.age.setEnabled(False)
        global username, age
        username = self.username.text()
        age = self.age.text()
        self.bluetooth_pairing()

    def bluetooth_pairing(self):
        self.initBtn.setText("Pairing...")
        self.initBtn.setStyleSheet("font-size: 18px; font-weight: bold; color: grey; background: #6D5ACC; border: none; padding: 10px; border-radius: 15px; width: 200px;")
        self.bt_thread = BluetoothPairingThread()
        self.bt_thread.pairing_complete.connect(self.start_user_initialization)
        self.bt_thread.start()

    def start_user_initialization(self):
        self.pair_label.setVisible(True)
        self.initBtn.setText("Calibrating Sensor..")
        self.init_thread = UserInitializationThread()
        self.init_thread.initialization_complete.connect(self.show_bpm_page)
        self.init_thread.start()

    def show_bpm_page(self):
        self.parent().setCurrentIndex(1)

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        # Create a stacked widget to manage pages
        self.stackedWidget = QStackedWidget(self)

        # Add the Landing page to the stacked widget
        self.landingPage = LandingPage(self.stackedWidget)
        self.stackedWidget.addWidget(self.landingPage)

        # Add the BPM page to the stacked widget
        self.bpmPage = BPMPage(self.stackedWidget)
        self.stackedWidget.addWidget(self.bpmPage)

        # Set the current index to show the landing page initially
        self.stackedWidget.setCurrentIndex(0)

        # Set up the main window
        self.setCentralWidget(self.stackedWidget)
        self.setWindowTitle("Pulse Monitoring System")
        self.setGeometry(100, 100, 500, 700)




if __name__ == "__main__":
    app = QApplication(sys.argv)
    style = """
        QWidget{
            background: black;
        }
        QPushButton{
            outline: none;
        }
    """
    app.setStyleSheet(style)


    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
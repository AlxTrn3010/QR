import sys
from datetime import time
import csv

import pandas as pd
import PyQt5 as Qt
import cv2
import numpy as np
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

def get_adict() -> dict:
    out = {}
    data = pd.read_csv("/home/pi/QR/resources/adict.csv", header=0).T.reset_index()
    data.columns = data.loc[0, :]
    data = data.drop(0, axis=0)
    for ind in data.index:
        out[data["ID"][ind]] = {"NAME":data["NAME"][ind], "PIC": data["PIC"][ind]}
    return out


def get_approve() -> list:
    results = []
    with open('/home/pi/QR/resources/approve.csv', newline='') as inputfile:
        for row in csv.reader(inputfile):
            results.append(row[0])
    return results

approvedict = get_adict()
approve = get_approve()

def crop_rect(img, rect, offset: int):
    # get the parameter of the small rectangle
    center = rect[0]
    size = rect[1]
    angle = rect[2]
    center, size = tuple(map(int, center)), tuple(map(int, size))

    new = []
    for item in size:
        new.append(item + offset)

    size = tuple(new)
    # get row and col num in img
    rows, cols = img.shape[0], img.shape[1]

    M = cv2.getRotationMatrix2D(center, angle, 1)
    img_rot = cv2.warpAffine(img, M, (cols, rows))
    out = cv2.getRectSubPix(img_rot, size, center)

    return out, img_rot


class Thread(QThread):
    VFrameUpdate = pyqtSignal(QImage)
    QRFrameUpdate = pyqtSignal(QImage)
    DATAUpdate = pyqtSignal(list, bool)
    
    def __init__(self, parent=None):
        QThread.__init__(self, parent)
        self.QR = None
        self.cap = True

    def run(self):
        print(4)
        counter = 100
        self.cap = cv2.VideoCapture("http://localhost:5000/VFEED");
        while self.cap:
           detector = cv2.QRCodeDetector()
           ret, frame = self.cap.read()
           ret, img = self.cap.read()
           # get bounding box coords and data
           data, bbox, _ = detector.detectAndDecode(frame)
           if not ret:
               continue

            # if there is a bounding box, draw one, along with the data
           if bbox is not None:
               counter = 0
               bbox = np.around(bbox).astype(int)
               for i in range(len(bbox[0])):
                   cv2.line(frame, bbox[0][i], bbox[0][(i + 1) % len(bbox[0])], color=(255, 0, 255), thickness=1)

           if data:
               rect = cv2.minAreaRect(bbox)
               box = cv2.boxPoints(rect)
               box = np.int0(box)
               im_crop, img_rot = crop_rect(img, rect, 5)

               datacheck, bbox, _ = detector.detectAndDecode(im_crop)
               if datacheck == data:
                   QR_frame = cv2.cvtColor(im_crop, cv2.COLOR_BGR2RGB)

                    # Creating QR and scaling QImage
                   h, w, ch = im_crop.shape
                   img = QImage(QR_frame.data, w, h, ch * w, QImage.Format_RGB888)
                   QR_img = img.scaled(150, 150, Qt.KeepAspectRatio)
                   self.QRFrameUpdate.emit(QR_img)
                   data = str(data).split('\n')
                   if len(data) == 1:
                       print("PIC: " + approvedict[data[0]]["PIC"])
                       print("ID: " + data[0])
                       print("NAME: " + approvedict[data[0]]["NAME"])
                       self.DATAUpdate.emit(data, 1)
                   else:
                       self.DATAUpdate.emit([], 1)

           else:
               counter += 1
               if counter > 30:
                   QR_frame = cv2.imread("/home/pi/QR/resources/QR_NO.jpg")
                   h, w, ch = QR_frame.shape
                   img = QImage(QR_frame.data, w, h, ch * w, QImage.Format_RGB888)
                   QR_img = img.scaled(150, 150, Qt.KeepAspectRatio)
                   self.QRFrameUpdate.emit(QR_img)
                   self.DATAUpdate.emit([], 0)

            # Reading the image in RGB to display it
           VFEED_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Creating VFEED and scaling QImage
           h, w, ch = frame.shape
           img = QImage(VFEED_frame.data, w, h, ch * w, QImage.Format_RGB888)
           VFEED_img = img.scaled(640, 480, Qt.KeepAspectRatio)

            # Emit signal
           self.VFrameUpdate.emit(VFEED_img)

        sys.exit(-1)


class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Thread in charge of updating the image
        self.th = Thread(self)
        self.th.start()
        self.th.finished.connect(self.close)
        self.th.VFrameUpdate.connect(self.setVF)
        self.th.QRFrameUpdate.connect(self.setQR)
        self.th.DATAUpdate.connect(self.setDATA)

        # Title and dimensions
        self.setWindowTitle("QR Detector")

        # Main menu bar
        self.menu = self.menuBar()
        self.menu_file = self.menu.addMenu("File")
        p_exit = QAction("Exit", self, triggered = qApp.quit)
        self.menu_file.addAction(p_exit)

        # Group VF and QR
        self.top_model = QGroupBox()
        self.top_model.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self.cam_layout = QHBoxLayout()
        # Create a label for the display camera
        self.VF_model = QGroupBox("QR SCANNER")
        self.VF_box = QVBoxLayout()
        self.VF = QLabel()  # CAM FEED
        self.VF_model.setLayout(self.VF_box)
        self.VF_box.addWidget(self.VF)
        # Create a label for the display QR
        self.QR_model = QGroupBox("QR VERIFICATION")
        self.QR_column = QVBoxLayout()
        self.QR_model.setLayout(self.QR_column)
        self.QR = QLabel()  # QR PIC FEED
        self.QR_PIC = QLabel()  # AVATA PIC FEED
        self.QR_ID = QLabel()  # QR DATA FEED
        self.QR_NAME = QLabel()  # QR DATA FEED
        self.QR_ID.setFont(QFont("Arial", 18, weight=QFont.Bold))
        self.QR_NAME.setFont(QFont("Arial", 18, weight=QFont.Bold))

        self.QR_column.addWidget(self.QR_PIC, 30, Qt.AlignCenter)
        self.QR_column.addWidget(self.QR, 30, Qt.AlignCenter)
        self.QR_column.addWidget(self.QR_ID,20)
        self.QR_column.addWidget(self.QR_NAME,20)
        ######
        self.cam_layout.addWidget(self.VF_model, 70)
        self.cam_layout.addWidget(self.QR_model, 30)
        self.top_model.setLayout(self.cam_layout)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.top_model)
        #######################################
        self.bot_model = QGroupBox("QR VERIFICATION")
        self.bot_model.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # Verification group
        self.veri_detail_layout = QHBoxLayout()
        self.veri_stat_color = QLabel()
        self.veri_stat_color.setFont(QFont("Arial", 30, weight=QFont.Bold))
        self.veri_stat_color.setAlignment(Qt.AlignCenter)
        self.veri_stat_color.setStyleSheet("QLabel { background-color : white}")
        self.veri_stat_color.autoFillBackground()
        self.veri_detail_layout.addWidget(self.veri_stat_color)

        self.bot_model.setLayout(self.veri_detail_layout)

        bot_layout = QHBoxLayout()
        bot_layout.addWidget(self.bot_model)

        # Main layout
        layout = QVBoxLayout()
        # cam
        layout.addLayout(top_layout, 70)
        # verification detail
        layout.addLayout(bot_layout, 30)

        # Central widget
        widget = QWidget(self)
        widget.setLayout(layout)
        self.setCentralWidget(widget)



    @pyqtSlot(QImage)
    def setVF(self, image):
        self.VF.setPixmap(QPixmap.fromImage(image))

    @pyqtSlot(QImage)
    def setQR(self, image):
        self.QR.setPixmap(QPixmap.fromImage(image))

    @pyqtSlot(list, bool)
    def setDATA(self, list, good):
        if len(list) == 1:
            print("Get New Data")
            print(list)
            if list[0] in approve:
                print("APPROVED")
                self.veri_stat_color.setStyleSheet("QLabel { background-color : green}")
                self.veri_stat_color.setText("PLEASE COME IN")
            else:
                print("DENIED")
                self.veri_stat_color.setStyleSheet("QLabel { background-color : red}")
                self.veri_stat_color.setText("CHECK YOUR ID PLEASE")

            img = QImage("/home/pi/QR/resources/"+approvedict[list[0]]["PIC"])
            self.QR_PIC.setPixmap(QPixmap.fromImage(img.scaled(round(300), round(300), Qt.KeepAspectRatio)))
            self.QR_ID.setText("ID: " + list[0])
            self.QR_NAME.setText("NAME: " + approvedict[list[0]]["NAME"])
        else:
            if good:
                print("Check QR")
                self.veri_stat_color.setStyleSheet("QLabel { background-color : red}")
                self.veri_stat_color.setText("CHECK YOUR QR CODE")
            else:
                print("Default")
                self.veri_stat_color.setStyleSheet("QLabel { background-color : white}")
                self.veri_stat_color.setText("SCAN YOUR QR CODE")
                self.QR.setStyleSheet("background-color: black")

            img = QImage("/home/pi/QR/resources/avata.jpg")
            self.QR_PIC.setPixmap(QPixmap.fromImage(img.scaled(round(300), round(300), Qt.KeepAspectRatio)))
            self.QR_ID.setText("ID: ")
            self.QR_NAME.setText("NAME: ")


    def closeEvent(self, event):
        close = QMessageBox()
        close.setText("Please Confirm")
        close.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        close = close.exec()

        if close == QMessageBox.Yes:
            self.th.cap.release()
            self.th.terminate()
            event.accept()
            # Give time for the thread to finish
            time.sleep(1)
        else:
            event.ignore()


if __name__ == "__main__":
    app = QApplication([])
    w = AppWindow()
    w.showFullScreen()
    w.show()
    sys.exit(app.exec())

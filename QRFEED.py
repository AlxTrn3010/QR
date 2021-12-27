from __future__ import print_function
from rpi_lcd import LCD
from flask import Flask, Response, jsonify
from signal import signal, SIGTERM, SIGHUP, pause

import numpy as np
import cv2
import csv
import random
import time
import threading


active = False

envdata = {"pcount": 0, "env1": 1, "env2": 2, "env3": 3, "active": active}
qrdata = {"ID":"", "Status": ""}
default = {"ID":"", "Status": ""}
pre = {"ID":"", "Status": ""}


def safe_exit(signum, frame):
    exit(1)
    
    
def get_approve() -> list:
    results = []
    with open('approve.csv', newline='') as inputfile:
        for row in csv.reader(inputfile):
            results.append(row[0])
    return results


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


class VideoCamera(object):
    def __init__(self):
        self.video = cv2.VideoCapture(-1)
        self.video.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def isOpened(self):
        return self.video.isOpened()

    def __del__(self):
        self.video.release()

    def get_frame(self):
        success, image = self.video.read()
        ret, jpeg = cv2.imencode('.jpg', image)
        return image, jpeg.tobytes()


def gen(camera):
    global active, qrdata
    
    while 1:
        if active:
            if not camera.isOpened():
                camera.__init__()
            frame, feed = camera.get_frame()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + feed + b'\r\n\r\n')

            qr_decoder(frame, envdata["pcount"])
        else:
            IDLE = cv2.imread("IDLE.png")
            _, feed = cv2.imencode('.jpg', IDLE)
            feed = feed.tobytes()
            camera.__del__()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + feed + b'\r\n\r\n')


def qr_decoder(camera, pcount):
    global qrdata, pre

    detector = cv2.QRCodeDetector()
    img = camera
    data = []
    # get bounding box coords and data
    data, bbox, _ = detector.detectAndDecode(camera)
    # if there is a bounding box, draw one, along with the data
    if bbox is not None:
        # print("QR")
        bbox = np.around(bbox).astype(int)
        for i in range(len(bbox[0])):
            cv2.line(camera, bbox[0][i], bbox[0][(i + 1) % len(bbox[0])], color=(255, 0, 255), thickness=2)

        if data:
            # print("DATA")
            if pcount < 5:
                if data in get_approve():
                    # print("Approved")
                    qrdata = {"ID": data, "Status": "Approved"}
                else:
                    # print("Denied")
                    qrdata = {"ID": data, "Status": "Denied"}
            else:
                # print("Full")
                qrdata = {"ID": data, "Status": "Full"}
        else:
            qrdata = default


app = Flask(__name__)


def runfeed():
    app.run(debug=True, use_reloader=False, port=5000, host='0.0.0.0')

def idle():
    global qrdata, active, pre
    while 1:
        if active & VideoCamera().isOpened():
            pre = qrdata
            if (qrdata == default) & (pre != default):
                start = time.time()
                while(time.time() - start < 30):
                    print(time.time() - start)
                    if qrdata != default:
                        break
                if qrdata == default & pre != default:
                    active = 0
                    pre = default


def control():
    while 1:
        if active:
            print(active)
            lcd.text(int(((16-8)/2))*"" +qrdata["ID"], 1)
            lcd.text(int((16-len(qrdata["Status"]))/2)*""+qrdata["Status"], 2)
        else:
            print(active)
            lcd.text(5*" "+"Station",1)
            lcd.text(6*" "+"IDLE", 2)
        
        
def safe_exit(signum, frame):
        exit(1)
        
        
if __name__ == '__main__':
    lcd = LCD()
    signal(SIGTERM, safe_exit)
    signal(SIGHUP, safe_exit)
    cth = threading.Thread(target=control).start() ##CONTROL
    vth = threading.Thread(target=runfeed).start() ##FEED
    idleth = threading.Thread(target=idle).start() ##idle-toggle
    


@app.route('/ACTIVE-IDLE-TOGGLE')
def toogle_actived():
    global active, qrdata
    active = not active
    return str(active)


@app.route('/VFEED')
def video_feed():
    return Response(gen(VideoCamera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/ENDATA')
def env_feed():
    global envdata
    envdata = {"pcount": 0, "env1": 1, "env2": 2, "env3": 3, "active": active}
    return jsonify(envdata)


@app.route('/QRDATA')
def qrdata_feed():
    return jsonify(qrdata)
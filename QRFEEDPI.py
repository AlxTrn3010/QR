from __future__ import print_function

import threading

from flask import Flask, Response, jsonify
from PIL import Image

import numpy as np
import cv2
import csv
import random
import time

active = False

envdata = {"pcount": 0, "env1": 1, "env2": 2, "env3": 3, "active": active}
qrdata = {"ID":"", "Status": ""}
default = {"ID":"", "Status": ""}
pre = {"ID":"", "Status": ""}





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
        self.video = cv2.VideoCapture(-1, cv2.CAP_V4L)
        self.video.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
        self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)

    def isOpened(self):
        return self.video.isOpened()

    def __del__(self):
        self.video.release()

    def get_frame(self):
        success, image = self.video.read()
        if success:
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
            camera.__del__()
            IDLE = cv2.imread("/home/pi/QR/IDLE.png")
            _, idle = cv2.imencode('.jpg', IDLE)
            idle = idle.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + idle + b'\r\n\r\n')


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
    app.run(debug=False, use_reloader=False, port=5000, host='0.0.0.0')

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
    pass


if __name__ == '__main__':
    vth = threading.Thread(target=runfeed).start() ##FEED
    idleth = threading.Thread(target=idle).start() ##idle-toggle
    cth = threading.Thread(target=control).start() ##CONTROL


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
    return jsonify(envdata)


@app.route('/QRDATA')
def qrdata_feed():
    return jsonify(qrdata)

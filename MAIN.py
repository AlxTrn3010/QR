from __future__ import print_function
from pyngrok import ngrok

from flask import Flask, Response, jsonify, send_file
from signal import signal, SIGTERM, SIGHUP, pause
#GROVE MODULE LIB
from grove import display
from seeed_dht import DHT
from grove.grove_ultrasonic_ranger import GroveUltrasonicRanger
from grove.grove_mini_pir_motion_sensor import GroveMiniPIRMotionSensor

import sys
import atexit 
import numpy as np
import cv2
import csv
import random
import time
import threading
import logging
import json
import requests
from os import system, name


    
def get_ngrok_url():
    url = "http://localhost:4040/api/tunnels"
    res = requests.get(url)
    res_unicode = res.content.decode("utf-8")
    res_json = json.loads(res_unicode)
    return res_json["tunnels"][0]["public_url"]


active = False
temp = 0
humid = 0
pcount = 0

envdata = {"pcount": pcount, "Temperature": temp, "Humidity": humid, "active": active}
qrdata = {"ID":"", "Status": ""}
default = {"ID":"", "Status": ""}
pre = {"ID":"", "Status": ""}


class VideoCamera(object):
    def __init__(self):
        self.video = cv2.VideoCapture("/dev/video0", cv2.CAP_V4L2)
        self.video.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def isOpened(self):
        return self.video.isOpened()

    def release(self):
        self.video.release()

    def get_frame(self):
        _, image = self.video.read()
        return _, image


def safe_exit(signum, frame):
    exit(1)


def get_approve() -> list:
    results = []
    with open('/home/pi/QR/resources/approve.csv', newline='') as inputfile:
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


def qr_decoder(frame, pcount):    
        global qrdata, pre, img_crop

        detector = cv2.QRCodeDetector()
        img = frame
        data = []
        # get bounding box coords and data
        data, bbox, _ = detector.detectAndDecode(frame)
        # if there is a bounding box, draw one, along with the data
        if bbox is not None:
            # print("QR")
            bbox = np.around(bbox).astype(int)
            for i in range(len(bbox[0])):
                cv2.line(img, bbox[0][i], bbox[0][(i + 1) % len(bbox[0])], color=(255, 0, 255), thickness=2)
            data = data.upper()
            if data:
                # print("DATA")
                if pcount < 5:
                    if data in get_approve():
                        print("Approved")
                        qrdata = {"ID": data, "Status": "Approved"}
                    else:
                        print("Denied")
                        qrdata = {"ID": data, "Status": "Denied"}
                else:
                    print("Full")
                    qrdata = {"ID": data, "Status": "Full"}
            else:
                qrdata = default


def gen(camera):
    global qrdata
    IDLE = cv2.imread("/home/pi/QR/resources/IDLE.jpg")
    _, idle = cv2.imencode('.jpg', IDLE)
    idle = idle.tobytes()
    
    while 1:
        _, frame = camera.get_frame()
        if _:
            feed = cv2.imencode('.jpg', frame)[1].tobytes()
        if active:
            qr_decoder(frame, envdata["pcount"])
        else:
            feed = idle

        
        yield (b'--frame\r\n'
           b'Content-Type:image/jpeg\r\n'
           b'Content-Length: ' + f"{len(feed)}".encode() + b'\r\n'
           b'\r\n' + feed + b'\r\n')
    #camera.release()
    
    


app = Flask(__name__)


def runfeed():
    app.run(debug=True, use_reloader=False, port=5000, host='0.0.0.0')
    
# def geturl():
#     app.run(debug=True, use_reloader=False, port=3000, host='0.0.0.0')

def idle():
    global qrdata, active, pre
    idle_time = 30
    while 1:
        #print(active, VideoCamera().isOpened())
        if active:
            #print(active)
            pre = qrdata
            if (qrdata == default):
                start = time.time()
                while(time.time() - start < idle_time):
                    #print("IDLE IN: " + str(int(idle_time - (time.time() - start))))
                    
                    if qrdata != default:
                        start = time.time()
                        
                active = False
                qrdata = default
                pre = default
                print("SWITCH TO IDLE")


def control():
    global qrdata
    while 1:
        if active:
            if qrdata != default:
                start = time.time()
                lcd.clear()
                lcd.setCursor(0,0)
                lcd.write(4*" " +qrdata["ID"])
                lcd.setCursor(1,0)
                lcd.write(int((16-len(qrdata["Status"]))/2)*" "+qrdata["Status"])
                while (time.time()-start < 5):
                    #print("{:.2f}".format(time.time() - start))
                    continue
                qrdata = default
            else:
                lcd.clear()
                lcd.setCursor(0,0)
                lcd.write("  SCAN YOUR QR")
        else:
            #print(active)
            lcd.clear()
            lcd.setCursor(0,0)
            lcd.write("     Station")
            lcd.setCursor(1,0)
            lcd.write("      IDLE")
        time.sleep(0.3)


def sensors():
    global temp, humid, pcount, active
    def Sonicdetechmotion(distance):
        if distance < 50:
            check = True
        else:
            check = False

        return check


    
    # Connect sensor to the pin.
    sonic_sensor1 = GroveUltrasonicRanger(5)
    sonic_sensor2 = GroveUltrasonicRanger(16)
    environment_sensor = DHT('11', 22)
    # Loop
    while True:
        #print(0)
        Distance1 = sonic_sensor1.get_distance()
        Distance2 = sonic_sensor2.get_distance()
        # Check for motion
        motion1 = Sonicdetechmotion(Distance1)
        motion2 = Sonicdetechmotion(Distance2)
        # Measure the tempeture and humidity
 #       humid, temp = environment_sensor.read()

        # People coming in
        start = time.time()
        while motion1:
            #print(2)
            stop = time.time()
            Distance2 = sonic_sensor2.get_distance()
            motion2 = Sonicdetechmotion(Distance2)
            if motion2:
                print("People coming in")
                pcount += 1
                active = not active
                motion1 = False
                motion2 = False
                time.sleep(0.5)

            if (stop - start > 2):
                motion1 = False
                motion2 = False
                time.sleep(0.5)


        # People coming out
        start = time.time()
        while motion2:
            #print(3)
            stop = time.time()
            Distance1 = sonic_sensor1.get_distance()
            motion1 = Sonicdetechmotion(Distance1)
            if motion1:
                print("People coming out")
                pcount -= 1
                motion1 = False
                motion2 = False
                time.sleep(0.5)

            if (stop - start > 2):
                motion1 = False
                motion2 = False
                time.sleep(0.5)
                

        # Value of tempeture and Humidity in this variable
        #print(temp)
        #print(humid)
    

@atexit.register 
def goodbye():
    lcd.clear()
    system("killall ngrok")
    print("Exiting Python Script!")
    

if __name__ == '__main__':
    lcd = display.JHD1802()
    lcd.backlight(True) 
    lcd.clear()
    lcd.setCursor(0,0)
    lcd.write("   Initiation")
    camera = VideoCamera()
    signal(SIGTERM, safe_exit)
    signal(SIGHUP, safe_exit)
    http = ngrok.connect(5000, "http")
    print(get_ngrok_url())
#     lcd.clear()
#     lcd.setCursor(0,0)
#     lcd.write(get_ngrok_url())
#     time.sleep(5)
    
    cth = threading.Thread(target=control).start() ##CONTROL
    vth = threading.Thread(target=runfeed).start() ##FEED
    #urlth = threading.Thread(target=geturl).start() ##socketXP get ngrok URL
    idleth = threading.Thread(target=idle).start() ##idle-toggle
    sensorsth = threading.Thread(target=sensors).start() ##sensors   


@app.route('/')
def intro():
    return (
        "url: Return NGROK's Public Domain<br/>"+
        "VFEED: Return Video Feed From QR Station<br/>"+
        "TOGGLE: Manually Toggle Active/Idle State<br/>"+
        "QRDATA: Return Current QR Code's Data and Approvement's Status<br/>"+
        "ENDATA: Return Enviroment's Data Readed by Sensors"
        )


@app.route('/url')
def get_url():
    response = jsonify(get_ngrok_url())
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


@app.route('/TOGGLE')
def toogle_actived():
    global active
    active = not active
    response = jsonify({"active":True})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


@app.route('/VFEED')
def video_feed():
    return Response(gen(camera), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/ENDATA')
def env_feed():
    global envdata
    envdata = {"pcount": pcount, "Temperature": temp, "Humidity": humid, "active": active}
    response = jsonify(envdata)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


@app.route('/QRDATA')
def qrdata_feed():
    response = jsonify(qrdata)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

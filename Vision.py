# USAGE
# python real_time_object_detection.py --prototxt b.prototxt.txt --model a.caffemodel

# import the necessary packages

from imutils.video import VideoStream
from imutils.video import FPS
import numpy as np
import argparse
import imutils
import time
import cv2

import queue
import signal
import threading
from time import sleep

import http.client
import paho.mqtt.client as mqtt
from time import sleep

delta = 0

def on_log(client, userdata, level, buf):
    print("log " + buf)


def on_connect(client, userdata, flags, rc):
    if rc==0:
        print("connected ok")
    else:
        print("Bad connection Returned code ", rc)


def on_disconnect(client, userdata, flags, rc=0):
    print("Disconnected code " + str(rc))


def on_message(client, userdata, msg):
    topic = msg.topic
    m_decode = str(msg.payload.decode("utf-8"))
    print("message received " + m_decode)


def client(something, simultaneous_launcher):
    global delta
    try:
        print("wait update")
        simultaneous_launcher.wait()
    except threading.BrokenBarrierError as msg:
        print("[recorder] thread couldn't fully start up")
    broker = "test.mosquitto.org"
    client = mqtt.Client("sensor1")
    client.on_connect = on_connect
    client.connect(broker)
    client.loop_start()
    while True:
        client.publish("deck/entry1", "delta={0}".format(delta))
        delta = 0
        time.sleep(120)
    client.disconnect()
    client.loop_stop()


def updater(something,simultaneous_launcher):
    global delta
    try:
        print("wait update")
        simultaneous_launcher.wait()
    except threading.BrokenBarrierError as msg:
        print("[recorder] thread couldn't fully start up")
    while True:
        h1 = http.client.HTTPConnection('localhost:8080')
        try:
            h1.request("PUT", "/update/1?delta={0}".format(delta))
            r1 = h1.getresponse()
            print(r1.status, r1.reason)
            print(r1.read().decode("utf-8"))
            if r1.status == 200:
                delta = 0
        except:
            print("error")
        sleep(120)


def rtod(something, simultaneous_launcher):
    # construct the argument parse and parse the arguments
    global delta
    ap = argparse.ArgumentParser()
    ap.add_argument("-p", "--prototxt", required=True,
                    help="path to Caffe 'deploy' prototxt file")
    ap.add_argument("-m", "--model", required=True,
                    help="path to Caffe pre-trained model")
    ap.add_argument("-c", "--confidence", type=float, default=0.2,
                    help="minimum probability to filter weak detections")
    args = vars(ap.parse_args())

    # initialize the list of class labels MobileNet SSD was trained to
    # detect, then generate a set of bounding box colors for each class
    CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
               "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
               "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
               "sofa", "train", "tvmonitor"]
    COLORS = np.random.uniform(0, 255, size=(len(CLASSES), 3))

    # load our serialized model from disk
    print("[INFO] loading model...")
    net = cv2.dnn.readNetFromCaffe(args["prototxt"], args["model"])

    # initialize the video stream, allow the cammera sensor to warmup,
    # and initialize the FPS counter
    print("[INFO] starting video stream...")
    vs = VideoStream(src=0).start()
    # vs = VideoStream(usePiCamera=True).start()
    time.sleep(2.0)
    fps = FPS().start()

    print("Chose a object to find: ")
    for i in CLASSES:
        print("{}: {}".format(CLASSES.index(i), i))

    goal = 7

    try:
        print("wait rtod")
        simultaneous_launcher.wait()
    except threading.BrokenBarrierError as msg:
        print("[recorder] thread couldn't fully start up")

    # loop over the frames from the video stream
    while True:
        # grab the frame from the threaded video stream and resize it
        # to have a maximum width of 400 pixels
        frame = vs.read()
        frame = imutils.resize(frame, width=400)

        # grab the frame dimensions and convert it to a blob
        (h, w) = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)),
                                     0.007843, (300, 300), 127.5)

        # pass the blob through the network and obtain the detections and
        # predictions
        net.setInput(blob)
        detections = net.forward()

        # loop over the detections
        for i in np.arange(0, detections.shape[2]):
            # extract the confidence (i.e., probability) associated with
            # the prediction
            confidence = detections[0, 0, i, 2]

            # filter out weak detections by ensuring the `confidence` is
            # greater than the minimum confidence
            if confidence > args["confidence"]:
                # extract the index of the class label from the
                # `detections`, then compute the (x, y)-coordinates of
                # the bounding box for the object
                idx = int(detections[0, 0, i, 1])
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (startX, startY, endX, endY) = box.astype("int")

                # draw the prediction on the frame
                label = "{}: {:.2f}%".format(CLASSES[idx],
                                             confidence * 100)
                cv2.rectangle(frame, (startX, startY), (endX, endY),
                              COLORS[idx], 2)
                y = startY - 15 if startY - 15 > 15 else startY + 15
                cv2.putText(frame, label, (startX, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS[idx], 2)
                if idx == goal:
                    delta += 1
                    print("found goal")
                    #cv2.imwrite("found_img.jpg", frame)

        # show the output frame
        cv2.imshow("Frame", frame)
        key = cv2.waitKey(1) & 0xFF

        # if the `q` key was pressed, break from the loop
        if key == ord("q"):
            break

        # update the FPS counter
        fps.update()

    # stop the timer and display FPS information
    fps.stop()
    print("[INFO] elapsed time: {:.2f}".format(fps.elapsed()))
    print("[INFO] approx. FPS: {:.2f}".format(fps.fps()))

    # do a bit of cleanup
    cv2.destroyAllWindows()
    vs.stop()


def Main(trigger):
    """
    Main thread where the other 2 threads are started, where the keyboard is being read and
    where everything is brought together.
    :param trigger: CTRL-C event. When it's set, it means CTRL-C was pressed and all threads are ended.
    :return: Nothing.
    """
    simultaneous_launcher = threading.Barrier(3)  # synchronization object


    # starting the workers/threads
    updater_thread = threading.Thread(target=client, args=(1, simultaneous_launcher))
    rtod_thread = threading.Thread(target=rtod, args=(1, simultaneous_launcher))
    rtod_thread.start()
    updater_thread.start()

    # if the threads couldn't be launched, then don't display anything else
    try:
        simultaneous_launcher.wait()
    except threading.BrokenBarrierError:
        pass

    # exit codes depending on the issue
    #if simultaneous_launcher.broken:
        #sys.exit(1)
    #sys.exit(0)


if __name__ == "__main__":
    trigger = threading.Event()  # event used when CTRL-C is pressed
    signal.signal(signal.SIGINT, lambda signum, frame: trigger.set())  # SIGINT (CTRL-C) signal handler
    Main(trigger)
import cv2
import time

# GStreamer pipeline string forcing MJPG with desired parameters.
pipeline = ("v4l2src device=/dev/video0 ! image/jpeg,framerate=30/1,width=1280,height=960 ! "
            "jpegparse ! jpegdec ! videoconvert ! appsink")

cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

if not cap.isOpened():
    print("Camera not opened")
    exit(1)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
start = time.time()
frame_count = 0
while frame_count < 100:
    ret, frame = cap.read()
    if not ret:
        break
    frame_count += 1
    print(frame_count)
end = time.time()
print("Avg FPS:", frame_count / (end - start))
cap.release()

import cv2
import zmq
import base64
import json
import time

def main():
    # Set up ZeroMQ context and publisher.
    context = zmq.Context()
    publisher = context.socket(zmq.PUB)
    publisher.bind("tcp://*:5555")
    print("ZeroMQ publisher bound to tcp://*:5555")
    
    # Open the default camera (usually /dev/video0)
    pipeline = ("v4l2src device=/dev/video0 ! image/jpeg,framerate=30/1,width=1280,height=960 ! "
            "jpegparse ! jpegdec ! videoconvert ! appsink")

    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

    if not cap.isOpened():
        print("Camera not opened")
        exit(1)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))

    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            break
        
        frame_count += 1
        
        #Encode the frame as JPEG.
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            print("Error: Could not encode frame.")
            continue
        
        # Base64 encode the JPEG data.
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Create a JSON object with frame number, an empty detections list, and the image.
        message = {
            "frame": frame_count,
            "detections": [],
            "image": image_base64
        }
        message_json = json.dumps(message)
        
        # Publish the JSON message.
        publisher.send_string(message_json)
        print(f"Published frame {frame_count}")
        
        # Delay to control the frame rate (adjust as needed).
        #time.sleep(0.03)  # ~30 fps if processing is fast enough

    cap.release()
    publisher.close()
    context.term()
    print("Camera stream ended.")

if __name__ == "__main__":
    main()

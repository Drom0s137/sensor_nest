#!/usr/bin/env python3
import cv2
import sys
import zmq
import json
import base64
import time
import numpy as np

def main():
    if len(sys.argv) < 2:
        print("Usage: {} <input_source> [output_video]".format(sys.argv[0]))
        sys.exit(1)

    input_source = sys.argv[1]
    save_to_file = (len(sys.argv) >= 3)
    output_video = sys.argv[2] if save_to_file else ""

    # Open input source
    if input_source.lower() in ["camera", "0"]:
        # Use a GStreamer pipeline to force MJPG at 1280x960 at 30 fps
        pipeline = ("v4l2src device=/dev/video0 ! image/jpeg,framerate=30/1,width=1280,height=960 ! "
                    "jpegparse ! jpegdec ! videoconvert ! appsink")
        cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        print("Using live camera feed from /dev/video0.")
    else:
        cap = cv2.VideoCapture(input_source)
        print("Using video file:", input_source)
    
    if not cap.isOpened():
        print("Error: Could not open input source:", input_source)
        sys.exit(1)
    
    # Get video properties
    frame_width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0  # default FPS

    if save_to_file:
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        writer = cv2.VideoWriter(output_video, fourcc, fps, (frame_width, frame_height))
        if not writer.isOpened():
            print("Error: Could not open output video file for writing:", output_video)
            sys.exit(1)
        print("Saving output to:", output_video)

    # Set up ZeroMQ publisher on TCP port 5555
    context = zmq.Context()
    publisher = context.socket(zmq.PUB)
    publisher.bind("tcp://*:5555")
    print("ZeroMQ publisher bound to tcp://*:5555")
    
    # Load the ONNX model
    onnx_model = "model_zoo/ssd_mobilenet_v1_10.onnx"
    net = cv2.dnn.readNetFromONNX(onnx_model)
    if net.empty():
        print("Error: Could not load the network from the ONNX model file:", onnx_model)
        sys.exit(1)
    
    # Set preferable backend/target.
    # If TensorRT is available, use it; otherwise fall back to CUDA.
    try:
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_TENSORRT)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
    except Exception as e:
        # If TensorRT isn't available, fall back:
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA_FP16)
    
    # Define class labels.
    labels = ["background", "aeroplane", "bicycle", "bird", "boat",
              "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
              "dog", "horse", "motorbike", "person", "pottedplant",
              "sheep", "sofa", "train", "tvmonitor"]

    confidence_threshold = 0.2
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            print("End of input or error reading frame.")
            break

        frame_count += 1

        # Create blob; note many ONNX SSD models expect a 300x300 input.
        blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), (127.5, 127.5, 127.5), swapRB=False, crop=False)
        # If your model requires a specific input node name, set it here (e.g., "input")
        net.setInput(blob, "input")
        detections = net.forward()

        # The detections shape is typically [1, 1, N, 7]. Reshape to [N, 7]
        detectionMat = detections.reshape(detections.shape[2], detections.shape[3])
        detections_list = []

        # Loop through each detection.
        for i in range(detectionMat.shape[0]):
            confidence = float(detectionMat[i, 2])
            if confidence > confidence_threshold:
                class_id = int(detectionMat[i, 1])
                x_left_bottom = int(detectionMat[i, 3] * frame.shape[1])
                y_left_bottom = int(detectionMat[i, 4] * frame.shape[0])
                x_right_top   = int(detectionMat[i, 5] * frame.shape[1])
                y_right_top   = int(detectionMat[i, 6] * frame.shape[0])
                
                # Draw bounding box on the frame.
                cv2.rectangle(frame, (x_left_bottom, y_left_bottom), (x_right_top, y_right_top), (0, 255, 0), 2)
                
                # Prepare label text.
                label_text = "{}: {:.2f}".format(labels[class_id] if class_id < len(labels) else "Unknown", confidence)
                (label_width, label_height), baseline = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                y_left_bottom = max(y_left_bottom, label_height)
                cv2.rectangle(frame, (x_left_bottom, y_left_bottom - label_height),
                              (x_left_bottom + label_width, y_left_bottom + baseline), (255, 255, 255), cv2.FILLED)
                cv2.putText(frame, label_text, (x_left_bottom, y_left_bottom),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                
                # Add detection info to our list.
                detection_info = {
                    "class_id": class_id,
                    "label": labels[class_id] if class_id < len(labels) else "Unknown",
                    "confidence": confidence,
                    "bbox": [x_left_bottom, y_left_bottom, x_right_top, y_right_top]
                }
                detections_list.append(detection_info)
        
        # Encode the processed frame to JPEG.
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            print("Error encoding frame to JPEG.")
            continue
        
        # Base64-encode the JPEG data.
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Build a combined JSON message.
        message = {
            "frame": frame_count,
            "detections": detections_list,
            "image": image_base64
        }
        message_json = json.dumps(message)
        
        # Publish the JSON message via ZeroMQ.
        publisher.send_string(message_json)
        print("Processed frame: {}".format(frame_count), end="\r", flush=True)
        
        # Optionally, if saving is enabled, write the frame to the output video.
        if save_to_file:
            writer.write(frame)
        
        # Optionally, insert a small delay if needed:
        # time.sleep(0.03)

    cap.release()
    if save_to_file:
        writer.release()
    print("\nProcessing complete.")

if __name__ == "__main__":
    main()

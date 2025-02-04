#include <opencv2/opencv.hpp>
#include <opencv2/dnn.hpp>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <vector>
#include <string>

// ZeroMQ and JSON headers
#include <zmq.hpp>
#include <nlohmann/json.hpp>

using namespace cv;
using namespace dnn;
using namespace std;
using json = nlohmann::json;

// Helper function to convert detection data to JSON.
string formatDetectionsToJSON(int frameNum, const vector<json>& detectionsList, const string& imageBase64) {
    json j;
    j["frame"] = frameNum;
    j["detections"] = detectionsList;
    j["image"] = imageBase64; // Add the processed frame (as base64-encoded JPEG)
    return j.dump();
}

int main(int argc, char** argv) {
    // Usage: object_detection_zmq <input_source> [output_video_optional]
    // input_source can be a file path or "camera" (or "0") for live feed.
    bool saveToFile = (argc >= 3);
    string outputVideo = "";
    VideoWriter writer;
    
    if (argc < 2) {
        cerr << "Usage: " << argv[0] << " <input_source> [output_video]" << endl;
        return -1;
    }
    
    string inputSource = argv[1];
    VideoCapture cap;
    // If the input source is "camera" or "0", open the default camera (/dev/video0).
    if (inputSource == "camera" || inputSource == "0") {
        string pipeline = "v4l2src device=/dev/video0 ! image/jpeg,framerate=30/1,width=1280,height=960 ! jpegparse ! jpegdec ! videoconvert ! appsink";
        cap.open(pipeline, CAP_GSTREAMER);
   
        cout << "Using live camera feed from /dev/video0" << endl;
    } else {
        cap.open(inputSource);
        cout << "Using video file: " << inputSource << endl;
    }
    
    if (!cap.isOpened()) {
        cerr << "Error: Could not open input source: " << inputSource << endl;
        return -1;
    }

    // Get video properties.
    int frameWidth  = static_cast<int>(cap.get(CAP_PROP_FRAME_WIDTH));
    int frameHeight = static_cast<int>(cap.get(CAP_PROP_FRAME_HEIGHT));
    double fps      = cap.get(CAP_PROP_FPS);
    // When using a camera, fps may not be set properly.
    if (fps <= 0) fps = 30.0;
    
    if (saveToFile) {
        outputVideo = argv[2];
        int fourcc = VideoWriter::fourcc('M','J','P','G');
        writer.open(outputVideo, fourcc, fps, Size(frameWidth, frameHeight));
        if (!writer.isOpened()) {
            cerr << "Error: Could not open output video file for writing: " << outputVideo << endl;
            return -1;
        }
        cout << "Saving output to: " << outputVideo << endl;
    }
    
    // Setup ZeroMQ publisher on TCP port 5555.
    zmq::context_t context(1);
    zmq::socket_t publisher(context, zmq::socket_type::pub);
    try {
        publisher.bind("tcp://*:5555");
        cout << "ZeroMQ publisher bound to tcp://*:5555" << endl;
    } catch (zmq::error_t &e) {
        cerr << "Error binding ZeroMQ publisher: " << e.what() << endl;
        return -1;
    }
    
    // Load the pre-trained MobileNet SSD model.
    string protoFile = "model_zoo/MobileNetSSD_deploy.prototxt";
    string modelFile = "model_zoo/MobileNetSSD_deploy.caffemodel";
    Net net = readNetFromCaffe(protoFile, modelFile);
    if (net.empty()) {
        cerr << "Error: Could not load the network using the given model files." << endl;
        return -1;
    }
    
    // Set the network to use the GPU.
    net.setPreferableBackend(DNN_BACKEND_CUDA);
    net.setPreferableTarget(DNN_TARGET_CUDA_FP16);
    
    // Define class labels.
    vector<string> labels = {"background", "aeroplane", "bicycle", "bird", "boat",
                             "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
                             "dog", "horse", "motorbike", "person", "pottedplant",
                             "sheep", "sofa", "train", "tvmonitor"};
    
    float confidenceThreshold = 0.2f;
    Mat frame;
    int frameCount = 0;
    
    // Process each frame.
    while (cap.read(frame)) {
        if (frame.empty())
            break;
        
        // Prepare blob and run forward pass.
        Mat blob = blobFromImage(frame, 0.007843, Size(300, 300),
                                 Scalar(127.5, 127.5, 127.5), false);
        net.setInput(blob);
        Mat detections = net.forward();
        
        // Reshape detections into a 2D matrix.
        Mat detectionMat(detections.size[2], detections.size[3], CV_32F, detections.ptr<float>());
        vector<json> detectionsList;
        
        for (int i = 0; i < detectionMat.rows; i++) {
            float confidence = detectionMat.at<float>(i, 2);
            if (confidence > confidenceThreshold) {
                int classId = static_cast<int>(detectionMat.at<float>(i, 1));
                int xLeftBottom = static_cast<int>(detectionMat.at<float>(i, 3) * frame.cols);
                int yLeftBottom = static_cast<int>(detectionMat.at<float>(i, 4) * frame.rows);
                int xRightTop   = static_cast<int>(detectionMat.at<float>(i, 5) * frame.cols);
                int yRightTop   = static_cast<int>(detectionMat.at<float>(i, 6) * frame.rows);
                
                // Draw bounding box.
                rectangle(frame, Point(xLeftBottom, yLeftBottom),
                          Point(xRightTop, yRightTop), Scalar(0,255,0), 2);
                
                // Prepare label text.
                string label = (classId < labels.size() ? labels[classId] : "Unknown");
                label = format("%s: %.2f", label.c_str(), confidence);
                
                int baseLine = 0;
                Size labelSize = getTextSize(label, FONT_HERSHEY_SIMPLEX, 0.5, 1, &baseLine);
                yLeftBottom = max(yLeftBottom, labelSize.height);
                rectangle(frame, Point(xLeftBottom, yLeftBottom - labelSize.height),
                          Point(xLeftBottom + labelSize.width, yLeftBottom + baseLine),
                          Scalar(255,255,255), FILLED);
                putText(frame, label, Point(xLeftBottom, yLeftBottom),
                        FONT_HERSHEY_SIMPLEX, 0.5, Scalar(0,0,0));
                
                // Prepare detection info in JSON.
                json detectionInfo;
                detectionInfo["class_id"] = classId;
                detectionInfo["label"] = (classId < labels.size() ? labels[classId] : "Unknown");
                detectionInfo["confidence"] = confidence;
                detectionInfo["bbox"] = { xLeftBottom, yLeftBottom, xRightTop, yRightTop };
                detectionsList.push_back(detectionInfo);
            }
        }
        
        // Encode the processed frame to JPEG.
        vector<uchar> buf;
        vector<int> params = {IMWRITE_JPEG_QUALITY, 80};
        if (!imencode(".jpg", frame, buf, params)) {
            cerr << "Error encoding frame to JPEG." << endl;
            continue;
        }
        // Base64-encode the JPEG data.
        string imageBase64;
        {
            static const string base64_chars =
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "abcdefghijklmnopqrstuvwxyz"
                "0123456789+/";
            int i = 0, j = 0;
            unsigned char char_array_3[3];
            unsigned char char_array_4[4];
            for (size_t pos = 0; pos < buf.size(); pos++) {
                char_array_3[i++] = buf[pos];
                if (i == 3) {
                    char_array_4[0] = (char_array_3[0] & 0xfc) >> 2;
                    char_array_4[1] = ((char_array_3[0] & 0x03) << 4) + ((char_array_3[1] & 0xf0) >> 4);
                    char_array_4[2] = ((char_array_3[1] & 0x0f) << 2) + ((char_array_3[2] & 0xc0) >> 6);
                    char_array_4[3] = char_array_3[2] & 0x3f;
                    for(i = 0; i < 4; i++)
                        imageBase64 += base64_chars[char_array_4[i]];
                    i = 0;
                }
            }
            if (i) {
                for(j = i; j < 3; j++)
                    char_array_3[j] = '\0';
                char_array_4[0] = (char_array_3[0] & 0xfc) >> 2;
                char_array_4[1] = ((char_array_3[0] & 0x03) << 4) + ((char_array_3[1] & 0xf0) >> 4);
                char_array_4[2] = ((char_array_3[1] & 0x0f) << 2) + ((char_array_3[2] & 0xc0) >> 6);
                char_array_4[3] = char_array_3[2] & 0x3f;
                for(j = 0; j < i + 1; j++)
                    imageBase64 += base64_chars[char_array_4[j]];
                while((i++ < 3))
                    imageBase64 += '=';
            }
        }
        
        // Build a combined JSON message containing detection data and the image.
        string jsonMsg = formatDetectionsToJSON(frameCount, detectionsList, imageBase64);
        zmq::message_t zmqMsg(jsonMsg.size());
        memcpy(zmqMsg.data(), jsonMsg.c_str(), jsonMsg.size());
        try {
            publisher.send(zmqMsg, 0);
        } catch (zmq::error_t &e) {
            cerr << "Error publishing detection data: " << e.what() << endl;
        }
        
#ifdef SAVE_MODE
        writer.write(frame);
#endif

        frameCount++;
        cout << "Processed frame: " << frameCount << "\r" << flush;
    }
    
    cap.release();
#ifdef SAVE_MODE
    writer.release();
#endif

    cout << "\nProcessing complete." << endl;
    return 0;
}

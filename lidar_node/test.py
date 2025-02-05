import serial
import zmq
import json

# Initialize ZeroMQ Publisher
context = zmq.Context()
publisher = context.socket(zmq.PUB)
publisher.bind("tcp://*:5556")  # Different port for LiDAR data

# Initialize LiDAR
lidar = serial.Serial('/dev/ttyUSB0', 128000, timeout=1)
lidar.write(b'\xA5\x60')  # Start scanning

print("LiDAR Publisher Started on tcp://*:5556")

while True:
    lidar_data = []
    for _ in range(360):  # Read 360 degrees
        line = lidar.readline().decode().strip()
        if line:
            lidar_data.append(line)

    # Create and send message
    message = {
        "lidar": lidar_data
    }
    publisher.send_json(message)

    print(f"Sent {len(lidar_data)} LiDAR points", end="\r")

lidar.write(b'\xA5\x65')  # Stop scanning
lidar.close()

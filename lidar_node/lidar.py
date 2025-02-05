import os
import ydlidar
import zmq
import json
import time

if __name__ == "__main__":
    # Initialize ZeroMQ Publisher
    context = zmq.Context()
    publisher = context.socket(zmq.PUB)
    publisher.bind("tcp://*:5556")  # Port for LiDAR data

    # Initialize LiDAR
    ydlidar.os_init()
    ports = ydlidar.lidarPortList()
    port = "/dev/ttyUSB0"
    for key, value in ports.items():
        port = value
        print(f"Detected LiDAR on: {port}")

    laser = ydlidar.CYdLidar()
    laser.setlidaropt(ydlidar.LidarPropSerialPort, port)
    laser.setlidaropt(ydlidar.LidarPropSerialBaudrate, 128000)
    laser.setlidaropt(ydlidar.LidarPropLidarType, ydlidar.TYPE_TRIANGLE)
    laser.setlidaropt(ydlidar.LidarPropDeviceType, ydlidar.YDLIDAR_TYPE_SERIAL)
    laser.setlidaropt(ydlidar.LidarPropScanFrequency, 6.0)
    laser.setlidaropt(ydlidar.LidarPropSampleRate, 5)
    laser.setlidaropt(ydlidar.LidarPropSingleChannel, False)
    laser.setlidaropt(ydlidar.LidarPropMaxAngle, 180.0)
    laser.setlidaropt(ydlidar.LidarPropMinAngle, -180.0)
    laser.setlidaropt(ydlidar.LidarPropMaxRange, 10.0)
    laser.setlidaropt(ydlidar.LidarPropMinRange, 0.12)
    laser.setlidaropt(ydlidar.LidarPropIntenstiy, False)

    if not laser.initialize():
        print("Failed to initialize YDLIDAR.")
        exit(1)

    if not laser.turnOn():
        print("Failed to start LiDAR scanning.")
        exit(1)

    scan = ydlidar.LaserScan()
    print("LiDAR scanning started...")

    while laser.doProcessSimple(scan) and ydlidar.os_isOk():
        if scan.config.scan_time == 0.0:
            scan_time = 1
        else:
            scan_time = scan.config.scan_time

        scan_data = {
            "timestamp": scan.stamp,
            "scan_frequency": 1.0 / scan_time,
            "points": [{"angle": p.angle, "range": p.range} for p in scan.points]
        }

        publisher.send_json(scan_data)
        print(f"Sent LiDAR data with {len(scan.points)} points", end="\r")

        time.sleep(0.05)

    laser.turnOff()
    laser.disconnecting()

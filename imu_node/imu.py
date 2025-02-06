import smbus2
import time
import math
import json
import os
import zmq
from collections import deque

IMU_ADDR = 0x68
bus = smbus2.SMBus(1)
bus.write_byte_data(IMU_ADDR, 0x6B, 0)  # Wake up IMU

def read_word(reg):
    high = bus.read_byte_data(IMU_ADDR, reg)
    low  = bus.read_byte_data(IMU_ADDR, reg + 1)
    val  = (high << 8) + low
    if val >= 0x8000:
        val = -((65535 - val) + 1)
    return val

def get_imu_data():
    # Read raw accelerometer
    accel_x = read_word(0x3B) / 16384.0
    accel_y = read_word(0x3D) / 16384.0
    accel_z = read_word(0x3F) / 16384.0

    # Read raw gyro
    gyro_x  = read_word(0x43) / 131.0
    gyro_y  = read_word(0x45) / 131.0
    gyro_z  = read_word(0x47) / 131.0

    # Simple computations
    roll  = math.atan2(accel_y, accel_z) * 180.0 / math.pi
    pitch = math.atan2(-accel_x, math.sqrt(accel_y**2 + accel_z**2)) * 180.0 / math.pi
    yaw   = gyro_z  # Quick, unintegrated

    return roll, pitch, yaw

# ------------ LOAD OFFSETS -------------
offset_file = "imu_offsets.json"
if os.path.exists(offset_file):
    with open(offset_file, "r") as f:
        offsets = json.load(f)
    ROLL_OFFSET  = offsets.get("roll_offset", 0.0)
    PITCH_OFFSET = offsets.get("pitch_offset", 0.0)
    YAW_OFFSET   = offsets.get("yaw_offset", 0.0)
    print(f"Loaded calibration offsets from {offset_file}:")
    print(f"  ROLL_OFFSET={ROLL_OFFSET}, PITCH_OFFSET={PITCH_OFFSET}, YAW_OFFSET={YAW_OFFSET}")
else:
    ROLL_OFFSET  = 0.0
    PITCH_OFFSET = 0.0
    YAW_OFFSET   = 0.0
    print("No calibration file found. Using default (zero) offsets.")
# ----------------------------------------

# --- Set up moving average buffers ---
ROLL_BUF_SIZE = 5   # Adjust as desired (larger => smoother but more lag)
PITCH_BUF_SIZE = 5
YAW_BUF_SIZE = 5

roll_buffer  = deque(maxlen=ROLL_BUF_SIZE)
pitch_buffer = deque(maxlen=PITCH_BUF_SIZE)
yaw_buffer   = deque(maxlen=YAW_BUF_SIZE)

# Setup ZMQ
context = zmq.Context()
publisher = context.socket(zmq.PUB)
publisher.bind("tcp://*:5557")

print("MPU6050 IMU Publisher started on tcp://*:5557")

while True:
    roll_raw, pitch_raw, yaw_raw = get_imu_data()

    # Subtract calibration offsets
    roll_cal  = roll_raw  - ROLL_OFFSET
    pitch_cal = pitch_raw - PITCH_OFFSET
    yaw_cal   = yaw_raw   - YAW_OFFSET

    # Add to rolling buffers
    roll_buffer.append(roll_cal)
    pitch_buffer.append(pitch_cal)
    yaw_buffer.append(yaw_cal)

    # Compute moving average
    roll_avg  = sum(roll_buffer)  / len(roll_buffer)
    pitch_avg = sum(pitch_buffer) / len(pitch_buffer)
    yaw_avg   = sum(yaw_buffer)   / len(yaw_buffer)

    # Publish smoothed data
    imu_data = {
        "roll":  roll_avg,
        "pitch": pitch_avg,
        "yaw":   yaw_avg
    }

    publisher.send_json(imu_data)
    print("Sent IMU Data:", imu_data)

    time.sleep(0.05)  # Adjust rate as needed (20 Hz in this case)

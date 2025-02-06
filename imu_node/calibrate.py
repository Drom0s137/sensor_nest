import smbus2
import time
import math
import json

IMU_ADDR = 0x68

def read_word(bus, reg):
    high = bus.read_byte_data(IMU_ADDR, reg)
    low  = bus.read_byte_data(IMU_ADDR, reg + 1)
    val  = (high << 8) + low
    if val >= 0x8000:
        val = -((65535 - val) + 1)
    return val

def get_imu_data(bus):
    # Read raw accelerometer
    accel_x = read_word(bus, 0x3B) / 16384.0
    accel_y = read_word(bus, 0x3D) / 16384.0
    accel_z = read_word(bus, 0x3F) / 16384.0

    # Read raw gyro
    gyro_x  = read_word(bus, 0x43) / 131.0
    gyro_y  = read_word(bus, 0x45) / 131.0
    gyro_z  = read_word(bus, 0x47) / 131.0

    # Simple computations
    roll  = math.atan2(accel_y, accel_z) * 180.0 / math.pi
    pitch = math.atan2(-accel_x, math.sqrt(accel_y**2 + accel_z**2)) * 180.0 / math.pi
    yaw   = gyro_z  # Quick, not integrated or corrected for drift

    return roll, pitch, yaw

if __name__ == "__main__":
    bus = smbus2.SMBus(1)
    # Wake up the MPU6050
    bus.write_byte_data(IMU_ADDR, 0x6B, 0)

    print("Measuring IMU orientation for calibration... Please keep the IMU still/level.")

    duration = 2.0  # seconds
    end_time = time.time() + duration

    roll_sum, pitch_sum, yaw_sum = 0.0, 0.0, 0.0
    count = 0

    # Collect samples for 'duration' seconds
    while time.time() < end_time:
        roll, pitch, yaw = get_imu_data(bus)
        roll_sum  += roll
        pitch_sum += pitch
        yaw_sum   += yaw
        count += 1
        time.sleep(0.05)  # 20 Hz

    # Compute average
    if count > 0:
        roll_offset  = roll_sum / count
        pitch_offset = pitch_sum / count
        yaw_offset   = yaw_sum / count
    else:
        roll_offset, pitch_offset, yaw_offset = 0, 0, 0

    print("Calibration complete!")
    print(f"Roll Offset:  {roll_offset:.3f}")
    print(f"Pitch Offset: {pitch_offset:.3f}")
    print(f"Yaw Offset:   {yaw_offset:.3f}")

    # Write offsets to JSON file
    offsets = {
        "roll_offset":  roll_offset,
        "pitch_offset": pitch_offset,
        "yaw_offset":   yaw_offset
    }
    
    with open("imu_offsets.json", "w") as f:
        json.dump(offsets, f, indent=2)

    print("\nSaved offsets to imu_offsets.json")

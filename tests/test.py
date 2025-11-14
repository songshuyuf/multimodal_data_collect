from pyshimmer import ShimmerBluetooth
import serial

ser = serial.Serial('COM6', 115200, timeout=None)
shimmer = ShimmerBluetooth(ser)
shimmer.initialize()

print("=== ShimmerBluetooth 可用方法 ===")
for attr in dir(shimmer):
    if not attr.startswith('_') and callable(getattr(shimmer, attr)):
        print(f"  {attr}")

ser.close()
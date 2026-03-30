import sounddevice as sd

print("=== 默认输入设备 ===")
try:
    dev = sd.query_devices(kind='input')
    print("名称:", dev["name"])
    print("输入通道数:", dev["max_input_channels"])
except Exception as e:
    print("无默认输入设备:", e)

print()
print("=== 全部有输入通道的设备 ===")
found = False
for i, d in enumerate(sd.query_devices()):
    ch = int(d.get('max_input_channels', 0))
    if ch > 0:
        print(f"  [{i}] {d['name']}  输入通道={ch}")
        found = True
if not found:
    print("  (未找到任何输入设备)")

"""
Shimmer Device Scanner
扫描和查找可用的Shimmer设备
"""

import sys
import platform

def scan_bluetooth_devices():
    """扫描蓝牙设备"""
    print("="*60)
    print("Shimmer Device Scanner")
    print("="*60)
    print(f"\nOperating System: {platform.system()}")
    
    system = platform.system()
    
    if system == "Windows":
        scan_windows()
    elif system == "Linux":
        scan_linux()
    elif system == "Darwin":  # macOS
        scan_macos()
    else:
        print(f"Unsupported operating system: {system}")

def scan_windows():
    """扫描Windows上的蓝牙设备"""
    print("\n--- Windows Bluetooth Device Scan ---\n")
    
    print("Step 1: Check paired devices in Windows Settings")
    print("  1. Open 'Settings' > 'Devices' > 'Bluetooth & other devices'")
    print("  2. Look for your Shimmer device (usually named 'Shimmer3-XXXX')")
    print("  3. If not paired, click 'Add Bluetooth or other device' and pair it")
    print("     (Default PIN is usually 1234)\n")
    
    print("Step 2: Find the COM port")
    print("  1. Open 'Device Manager'")
    print("  2. Expand 'Ports (COM & LPT)'")
    print("  3. Look for 'Standard Serial over Bluetooth link (COMxx)'")
    print("  4. Note the COM port number (e.g., COM14)\n")
    
    # 尝试列出串口
    try:
        import serial.tools.list_ports
        
        ports = serial.tools.list_ports.comports()
        if ports:
            print("Available COM ports:")
            for port in ports:
                print(f"  - {port.device}: {port.description}")
                if "bluetooth" in port.description.lower():
                    print(f"    ^ This looks like a Bluetooth device!")
        else:
            print("No COM ports detected")
    except ImportError:
        print("Install pyserial to automatically detect COM ports:")
        print("  pip install pyserial")
    
    print("\nUsage: python main.py --port COM14")

def scan_linux():
    """扫描Linux上的蓝牙设备"""
    print("\n--- Linux Bluetooth Device Scan ---\n")
    
    print("Step 1: Install required tools")
    print("  sudo apt-get install bluez bluez-tools")
    print()
    
    print("Step 2: Scan for Shimmer devices")
    print("  Run: hcitool scan")
    print("  Look for device with name like 'Shimmer3-XXXX'")
    print("  Note the MAC address (e.g., 00:06:66:XX:XX:XX)")
    print()
    
    # 尝试运行hcitool scan
    print("Attempting to scan...")
    try:
        import subprocess
        result = subprocess.run(['hcitool', 'scan'], 
                              capture_output=True, 
                              text=True, 
                              timeout=10)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("Could not run hcitool. Make sure bluez is installed.")
    except FileNotFoundError:
        print("hcitool not found. Install bluez:")
        print("  sudo apt-get install bluez")
    except Exception as e:
        print(f"Error scanning: {e}")
    
    print("\nStep 3: Bind the device to a serial port")
    print("  sudo rfcomm bind 0 00:06:66:XX:XX:XX 1")
    print("  This creates /dev/rfcomm0")
    print()
    
    print("Step 4: Set permissions (if needed)")
    print("  sudo chmod 666 /dev/rfcomm0")
    print("  OR add your user to dialout group:")
    print("  sudo usermod -a -G dialout $USER")
    print("  (then logout and login again)")
    print()
    
    # 检查是否已经有rfcomm设备
    try:
        import glob
        rfcomm_devices = glob.glob('/dev/rfcomm*')
        if rfcomm_devices:
            print("Existing rfcomm devices:")
            for device in rfcomm_devices:
                print(f"  - {device}")
        else:
            print("No rfcomm devices found yet")
    except Exception as e:
        print(f"Error checking devices: {e}")
    
    print("\nUsage: python main.py --port /dev/rfcomm0")

def scan_macos():
    """扫描macOS上的蓝牙设备"""
    print("\n--- macOS Bluetooth Device Scan ---\n")
    
    print("Step 1: Pair the Shimmer device")
    print("  1. Open 'System Preferences' > 'Bluetooth'")
    print("  2. Make sure Shimmer is powered on and in pairing mode")
    print("  3. Click 'Pair' when device appears")
    print("  4. Enter PIN if requested (usually 1234)")
    print()
    
    print("Step 2: Find the device path")
    print("  Open Terminal and run:")
    print("    ls /dev/tty.*")
    print("  Look for something like: /dev/tty.Shimmer3-XXXX-RN-SPP")
    print()
    
    # 尝试列出tty设备
    try:
        import glob
        tty_devices = glob.glob('/dev/tty.*')
        if tty_devices:
            print("Available TTY devices:")
            shimmer_found = False
            for device in tty_devices:
                if 'shimmer' in device.lower() or 'bluetooth' in device.lower():
                    print(f"  - {device} <-- Looks like Shimmer!")
                    shimmer_found = True
                else:
                    print(f"  - {device}")
            
            if not shimmer_found:
                print("\n  No obvious Shimmer device found.")
                print("  The device path might be /dev/cu.Shimmer3-* or /dev/tty.Shimmer3-*")
    except Exception as e:
        print(f"Error listing devices: {e}")
    
    print("\nUsage: python main.py --port /dev/tty.Shimmer3-XXXX-RN-SPP")

def list_serial_ports():
    """列出所有串口"""
    print("\n" + "="*60)
    print("Serial Port Listing")
    print("="*60 + "\n")
    
    try:
        import serial.tools.list_ports
        
        ports = serial.tools.list_ports.comports()
        if ports:
            print("All available serial ports:")
            for i, port in enumerate(ports, 1):
                print(f"\n{i}. {port.device}")
                print(f"   Description: {port.description}")
                print(f"   Hardware ID: {port.hwid}")
                
                # 高亮可能的Shimmer设备
                keywords = ['shimmer', 'bluetooth', 'bt', 'rfcomm']
                if any(kw in port.description.lower() or kw in port.device.lower() 
                       for kw in keywords):
                    print("   >>> This might be your Shimmer device!")
        else:
            print("No serial ports found")
    
    except ImportError:
        print("pyserial not installed. Install it with:")
        print("  pip install pyserial")

if __name__ == "__main__":
    scan_bluetooth_devices()
    print()
    list_serial_ports()
    
    print("\n" + "="*60)
    print("Next Steps:")
    print("="*60)
    print("1. Note your device's port/path from above")
    print("2. Update config.py with the correct port")
    print("3. Run: python main.py --port YOUR_PORT")
    print("="*60)

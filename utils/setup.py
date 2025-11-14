#!/usr/bin/env python3
"""
Installation and Setup Script
自动安装依赖并检查系统配置
"""

import sys
import subprocess
import platform
import os

def print_header(text):
    """打印格式化的标题"""
    print("\n" + "="*60)
    print(text)
    print("="*60 + "\n")

def check_python_version():
    """检查Python版本"""
    print_header("Checking Python Version")
    
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print("❌ Error: Python 3.7 or higher is required")
        print("Please upgrade Python and try again")
        return False
    else:
        print("✓ Python version is compatible")
        return True

def install_requirements():
    """安装requirements.txt中的依赖"""
    print_header("Installing Python Dependencies")
    
    try:
        print("Installing packages from requirements.txt...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        print("✓ Successfully installed base requirements")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing requirements: {e}")
        return False

def install_shimmer_library():
    """安装Shimmer Python库"""
    print_header("Installing Shimmer Library")
    
    print("Which Shimmer library would you like to install?")
    print("1. matmont/shimmer3 (Recommended for most users)")
    print("2. seemoo-lab/pyshimmer (More features, but may be more complex)")
    print("3. Skip (I'll install it manually)")
    
    choice = input("\nEnter your choice (1/2/3): ").strip()
    
    try:
        if choice == "1":
            print("\nInstalling matmont/shimmer3...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "git+https://github.com/matmont/shimmer3.git"
            ])
            print("✓ Successfully installed matmont/shimmer3")
            return True
        
        elif choice == "2":
            print("\nInstalling seemoo-lab/pyshimmer...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "git+https://github.com/seemoo-lab/pyshimmer.git"
            ])
            print("✓ Successfully installed seemoo-lab/pyshimmer")
            return True
        
        elif choice == "3":
            print("Skipping Shimmer library installation")
            print("Remember to install it manually before running the application")
            return True
        
        else:
            print("Invalid choice. Skipping Shimmer library installation")
            return True
    
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing Shimmer library: {e}")
        print("\nYou may need to install Git first:")
        if platform.system() == "Windows":
            print("  Download from: https://git-scm.com/download/win")
        elif platform.system() == "Linux":
            print("  sudo apt-get install git")
        elif platform.system() == "Darwin":
            print("  xcode-select --install")
        return False

def create_directories():
    """创建必要的目录"""
    print_header("Creating Directories")
    
    directories = ['data', 'logs']
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✓ Created directory: {directory}/")
        except Exception as e:
            print(f"❌ Error creating {directory}/: {e}")
            return False
    
    return True

def check_bluetooth():
    """检查蓝牙支持"""
    print_header("Checking Bluetooth Support")
    
    system = platform.system()
    
    if system == "Windows":
        print("On Windows, please ensure:")
        print("  1. Bluetooth is enabled in Settings")
        print("  2. Your Shimmer device is paired")
        print("  3. You know the COM port number")
        print("\nRun 'python scan_devices.py' to find your device")
    
    elif system == "Linux":
        print("On Linux, please ensure:")
        print("  1. bluez is installed: sudo apt-get install bluez")
        print("  2. Your user is in dialout group: sudo usermod -a -G dialout $USER")
        print("\nRun 'python scan_devices.py' for more details")
    
    elif system == "Darwin":
        print("On macOS, please ensure:")
        print("  1. Bluetooth is enabled in System Preferences")
        print("  2. Your Shimmer device is paired")
        print("\nRun 'python scan_devices.py' to find your device")
    
    print("\n✓ Bluetooth check complete (manual verification required)")
    return True

def test_imports():
    """测试关键库是否可以导入"""
    print_header("Testing Package Imports")
    
    test_packages = [
        ('pylsl', 'pylsl'),
        ('numpy', 'numpy'),
        ('serial', 'pyserial'),
    ]
    
    all_success = True
    
    for package_name, install_name in test_packages:
        try:
            __import__(package_name)
            print(f"✓ {install_name} imported successfully")
        except ImportError:
            print(f"❌ Failed to import {install_name}")
            all_success = False
    
    # Test Shimmer library (may not be installed yet)
    try:
        from shimmer import shimmer
        print("✓ Shimmer library imported successfully")
    except ImportError:
        print("⚠ Shimmer library not found (this is optional if you haven't installed it yet)")
    
    return all_success

def create_example_config():
    """创建示例配置文件"""
    print_header("Configuration")
    
    print("The default configuration is already in config.py")
    print("\nPlease edit config.py to set:")
    print("  - Your Shimmer device COM port")
    print("  - Desired sampling rate")
    print("  - Enabled sensors")
    print("\nYou can run 'python scan_devices.py' to help find your device")
    
    return True

def print_next_steps():
    """打印后续步骤"""
    print_header("Installation Complete!")
    
    print("Next steps:")
    print("\n1. Find your Shimmer device:")
    print("   python scan_devices.py")
    
    print("\n2. Edit config.py with your device settings:")
    print("   - Set the correct COM port/device path")
    print("   - Adjust sampling rate if needed")
    print("   - Choose which sensors to enable")
    
    print("\n3. Run the application:")
    print("   python main.py")
    
    print("\n4. In another terminal, test the LSL stream:")
    print("   python test_lsl_receiver.py")
    
    print("\n5. For multi-modal sync, use LabRecorder:")
    print("   Download from: https://github.com/labstreaminglayer/App-LabRecorder/releases")
    
    print("\nFor help, see README.md")
    print("="*60)

def main():
    """主安装流程"""
    print_header("Shimmer GSR+ LSL Integration - Setup Script")
    print(f"Operating System: {platform.system()}")
    print(f"Python: {sys.version}")
    
    # 检查Python版本
    if not check_python_version():
        sys.exit(1)
    
    # 安装依赖
    if not install_requirements():
        print("\n⚠ Warning: Some requirements failed to install")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    # 安装Shimmer库
    install_shimmer_library()
    
    # 创建目录
    create_directories()
    
    # 检查蓝牙
    check_bluetooth()
    
    # 测试导入
    test_imports()
    
    # 配置说明
    create_example_config()
    
    # 显示后续步骤
    print_next_steps()

if __name__ == "__main__":
    main()

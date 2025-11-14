"""
检查pyshimmer库中可用的EChannelType
"""

try:
    from pyshimmer import EChannelType
    
    print("=== 可用的EChannelType枚举值 ===\n")
    
    # 列出所有EChannelType成员
    for name in dir(EChannelType):
        if not name.startswith('_'):
            try:
                value = getattr(EChannelType, name)
                print(f"{name}: {value}")
            except:
                pass
    
    print("\n=== GSR相关通道 ===")
    for name in dir(EChannelType):
        if 'GSR' in name.upper():
            value = getattr(EChannelType, name)
            print(f"{name}: {value}")
    
    print("\n=== ADC相关通道 ===")
    for name in dir(EChannelType):
        if 'ADC' in name.upper() or 'A13' in name.upper():
            value = getattr(EChannelType, name)
            print(f"{name}: {value}")
    
    print("\n=== 电池相关通道 ===")
    for name in dir(EChannelType):
        if 'BATT' in name.upper() or 'VOLT' in name.upper():
            value = getattr(EChannelType, name)
            print(f"{name}: {value}")

except ImportError as e:
    print(f"无法导入pyshimmer: {e}")
    print("\n请安装pyshimmer:")
    print("  pip install pyshimmer")
    print("  或")
    print("  pip install git+https://github.com/patrickmayy/pyshimmer.git")

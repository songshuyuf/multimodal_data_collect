"""
Shimmer GSR+ LSL Integration - Configuration File
配置文件：定义所有设备和数据采集的参数
"""

# ========== Shimmer GSR+ 设备配置 ==========
SHIMMER_CONFIG = {
    # 蓝牙连接配置
    'com_port': 'COM6',  # Windows: 'COM6', Linux: '/dev/rfcomm0'
    'mac_address': None,   # 如果已知MAC地址,填写在这里,例如: '00:06:66:XX:XX:XX'
    'device_id': 'A5E0',  # 添加这行,改成你的设备ID
    # 采样率配置
    'sampling_rate': 128.0,  # Hz, 可选: 51.2, 128.0, 256.0, 512.0

    # 传感器配置
    'enabled_sensors': [
        'gsr',           # 皮肤电反应
        # 'ppg',           # 光电容积脉搏波 (需要确认通道名称后启用)
        'battery',       # 电池电压
        # 'accelerometer', # 加速度计 (可选)
    ],
    
    # 数据配置
    'use_calibrated_data': True,  # 使用校准后的数据
}

# ========== LSL 流配置 ==========
LSL_CONFIG = {
    # LSL流的基本信息
    'stream_name': 'ShimmerGSR',
    'stream_type': 'GSR',  # 流类型标识
    'source_id': 'shimmer_gsr_001',  # 唯一设备ID
    
    # 通道配置 (会根据enabled_sensors自动生成)
    'channel_format': 'float32',
    
    # 元数据
    'manufacturer': 'Shimmer',
    'model': 'GSR+',
}

# ========== 数据保存配置 ==========
DATA_SAVING_CONFIG = {
    'save_raw_data': True,
    'output_directory': './data',
    'file_format': 'csv',  # 'csv', 'hdf5', 'both'
    'include_timestamp': True,
    'buffer_size': 1000,  # 缓冲区大小,达到后写入文件
}

# ========== 日志配置 ==========
LOGGING_CONFIG = {
    'level': 'INFO',  # 'DEBUG', 'INFO', 'WARNING', 'ERROR'
    'log_to_file': True,
    'log_directory': './logs',
    'console_output': True,
}

# ========== 传感器通道映射 ==========
SENSOR_CHANNELS = {
    'gsr': {
        'names': ['GSR_Skin_Conductance', 'GSR_Skin_Resistance'],
        'units': ['uS', 'kOhm'],
        'types': ['GSR', 'GSR']
    },
    'ppg': {
        'names': ['PPG_A13'],
        'units': ['mV'],  # 改成mV
        'types': ['PPG']
    },
    'accelerometer_ln': {  # Low-Noise加速度计
        'names': ['Accel_LN_X', 'Accel_LN_Y', 'Accel_LN_Z'],
        'units': ['m/s^2', 'm/s^2', 'm/s^2'],
        'types': ['Accel', 'Accel', 'Accel']
    },
    'accelerometer_wr': {  # 新增Wide-Range加速度计
        'names': ['Accel_WR_X', 'Accel_WR_Y', 'Accel_WR_Z'],
        'units': ['m/s^2', 'm/s^2', 'm/s^2'],
        'types': ['Accel', 'Accel', 'Accel']
    },
    'gyroscope': {
        'names': ['Gyro_X', 'Gyro_Y', 'Gyro_Z'],
        'units': ['deg/s', 'deg/s', 'deg/s'],
        'types': ['Gyro', 'Gyro', 'Gyro']
    },
    'magnetometer': {
        'names': ['Mag_X', 'Mag_Y', 'Mag_Z'],
        'units': ['local', 'local', 'local'],
        'types': ['Mag', 'Mag', 'Mag']
    },
    'temperature': {
        'names': ['Temperature_BMP280'],
        'units': ['Celcius'],
        'types': ['Temp']
    },
    'pressure': {
        'names': ['Pressure_BMP280'],
        'units': ['Pa'],
        'types': ['Pressure']
    },
    'external_adc': {  # 新增外部ADC
        'names': ['Ext_Exp_A7'],
        'units': ['mV'],
        'types': ['ExternalADC']
    },
    'battery': {
        'names': ['VSenseBatt'],
        'units': ['mV'],
        'types': ['Battery']
    },
    'heart_rate': {
        'names': ['PPGtoHR'],  # 只有心率,删除IBI
        'units': ['BPM'],
        'types': ['HR']
    },
}

SHIMMER_CONFIG = {
    'com_port': 'COM6',
    'device_id': 'A5E0',
    'sampling_rate': 128.0,
    'enabled_sensors': [
        'gsr',
        'ppg',
        'accelerometer_ln',
        'accelerometer_wr',  # 新增
        'gyroscope',
        'magnetometer',
        'temperature',
        'pressure',
        'external_adc',      # 新增
        'battery',           # 新增
        'heart_rate',
    ],
}



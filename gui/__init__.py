"""
GUI模块
"""
from .main_window import MainWindow
from .patient_tab import PatientTab
from .collection_tab import CollectionTab
from .device_controller import DeviceController
from .realtime_shimmer_tab import RealtimeShimmerTab
from .realtime_video_audio_tab import RealtimeVideoAudioTab
from .realtime_eeg_tab import RealtimeEEGTab

__all__ = [
    'MainWindow',
    'PatientTab',
    'CollectionTab',
    'DeviceController',
    'RealtimeShimmerTab',
    'RealtimeVideoAudioTab',
    'RealtimeEEGTab'
]
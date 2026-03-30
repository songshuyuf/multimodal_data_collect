"""
app.monitors — 实时监控 Tab 模块
================================
GSR / EMG / EEG / Video / Audio 五个实时信号监测面板。
"""

from .gsr_tab import RealtimeShimmerTab
from .emg_tab import RealtimeEMGTab
from .eeg_tab import RealtimeEEGTab
from .video_tab import RealtimeVideoTab
from .audio_tab import RealtimeAudioTab


def _is_dark() -> bool:
    """Check if current Fluent theme is dark, with graceful fallback."""
    try:
        from qfluentwidgets import isDarkTheme
        return isDarkTheme()
    except Exception:
        return False


def tint(hex_color: str, alpha: int = 30) -> str:
    """Convert '#RRGGBB' + alpha(0-255) to proper 'rgba(r,g,b,a)' CSS string.

    Qt stylesheets misinterpret 8-digit hex (#RRGGBBAA) as #AARRGGBB,
    so always use rgba() notation instead.
    """
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f'rgba({r},{g},{b},{alpha})'


def theme_pg_plot(plot_widget):
    """Apply dark/light background + axis colors to a pyqtgraph PlotWidget or plot item."""
    dark = _is_dark()
    bg = '#1e1e1e' if dark else '#ffffff'
    fg = '#d4d4d4' if dark else '#333333'
    plot_widget.setBackground(bg)
    for axis_name in ('left', 'bottom'):
        try:
            ax = plot_widget.getAxis(axis_name)
            ax.setPen(fg)
            ax.setTextPen(fg)
        except Exception:
            pass


def theme_pg_layout(layout_widget):
    """Apply dark/light background to a pyqtgraph GraphicsLayoutWidget."""
    dark = _is_dark()
    layout_widget.setBackground('#1e1e1e' if dark else '#ffffff')


def theme_mpl_figure(figure):
    """Apply dark/light colors to a matplotlib Figure and its axes."""
    dark = _is_dark()
    bg = '#1e1e1e' if dark else '#ffffff'
    fg = '#d4d4d4' if dark else '#333333'
    figure.set_facecolor(bg)
    for ax in figure.get_axes():
        ax.set_facecolor(bg)
        ax.tick_params(colors=fg, labelcolor=fg)
        ax.xaxis.label.set_color(fg)
        ax.yaxis.label.set_color(fg)
        ax.title.set_color(fg)
        for spine in ax.spines.values():
            spine.set_edgecolor(fg)

__all__ = [
    "RealtimeShimmerTab",
    "RealtimeEMGTab",
    "RealtimeEEGTab",
    "RealtimeVideoTab",
    "RealtimeAudioTab",
]

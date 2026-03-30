# VR 同步资源

## 方案说明

- **视频**：放在 PICO 本地，与 PC 存同一份
- **同步**：PC 通过 HTTP 轮询下发 play/pause/stop，PICO 页面根据命令控制本地视频

## 使用步骤

### 1. PC 端

实验流程进入 VR 阶段时，启动 VR 同步服务并下发命令：

```python
from core.vr_sync import VRSyncServer

server = VRSyncServer(port=8765)
server.start()

# 进入 VR 阶段
server.set_state("play")

# 3 分钟后结束
server.set_state("stop")
server.stop()
```

### 2. PICO 端

1. 将 `pico_vr_page.html` 和视频文件（如 `video.mp4`）拷到 PICO 存储同一目录
2. 修改 HTML 中的 `PC_IP` 为你的 PC 局域网 IP，或通过 URL 参数传入：
   - `file:///sdcard/.../pico_vr_page.html?pc=192.168.1.100&port=8765`
3. 在 PICO 浏览器中打开该 HTML 文件
4. 页面会每 500ms 轮询 PC 的 `/state`，收到 `play` 即播放本地视频

### 3. 视频路径

- **本地模式**：`video.mp4` 与 HTML 同目录，使用相对路径
- **URL 参数**：`?video=video.mp4` 或 `?video=/sdcard/xxx/video.mp4`

## 单元测试

```bash
python tests/test_vr_unit.py
python tests/test_vr_unit.py --simulate
```

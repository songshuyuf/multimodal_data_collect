"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import * as echarts from "echarts/core";
import { LineChart, BarChart } from "echarts/charts";
import { GridComponent, DataZoomComponent, TooltipComponent, LegendComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { motion } from "framer-motion";
import { ArrowLeft, Download, ChevronDown, ChevronUp, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { TimelineBar } from "@/components/viewer/TimelineBar";
import { sessionApi, type SessionTimeline, type ModalityStats, type WaveformData } from "@/lib/api";
import { formatDuration, formatFileSize, MODALITY_META, type Modality } from "@/lib/utils";

echarts.use([LineChart, BarChart, GridComponent, DataZoomComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

const DEMO_TIMELINE: SessionTimeline = {
  session_id: 1,
  total_duration: 2700,
  modalities: ["eeg", "gsr", "emg", "audio", "video"],
  segments: [
    { task_name: "基线休息", task_type: "rest", start_sec: 0, end_sec: 180, color: "#64748b" },
    { task_name: "音乐鉴赏", task_type: "music", start_sec: 180, end_sec: 660, color: "#8b5cf6" },
    { task_name: "休息", task_type: "rest", start_sec: 660, end_sec: 780, color: "#64748b" },
    { task_name: "绘画鉴赏", task_type: "painting", start_sec: 780, end_sec: 1260, color: "#f59e0b" },
    { task_name: "休息", task_type: "rest", start_sec: 1260, end_sec: 1380, color: "#64748b" },
    { task_name: "点探测", task_type: "probe", start_sec: 1380, end_sec: 1800, color: "#22c55e" },
    { task_name: "VR 沉浸", task_type: "vr", start_sec: 1920, end_sec: 2520, color: "#ef4444" },
  ],
};

const CHANNEL_MAP: Record<string, string[]> = {
  eeg: ["Fp1", "Fp2", "F3", "F4", "F7", "F8", "C3", "C4", "T3", "T4", "P3", "P4", "O1", "O2", "Fz", "Cz", "Pz"],
  gsr: ["SCL", "HR", "HRV_RMSSD", "HRV_SDNN"],
  emg: ["EMG_CH1", "EMG_CH2", "EMG_Envelope"],
  audio: ["Left", "Right"],
  video: [],
};

const MODALITY_DESCRIPTIONS: Record<string, { title: string; statsLabels: Record<string, string> }> = {
  eeg: { title: "EEG 脑电详情", statsLabels: { sample_rate: "采样率", channels: "通道数", duration: "时长", size: "文件大小" } },
  gsr: { title: "GSR 皮电 / 心率详情", statsLabels: { sample_rate: "采样率", channels: "信号类型", duration: "时长", size: "文件大小" } },
  emg: { title: "EMG 肌电详情", statsLabels: { sample_rate: "采样率", channels: "通道数", duration: "时长", size: "文件大小" } },
  audio: { title: "音频详情", statsLabels: { sample_rate: "采样率", channels: "声道", duration: "时长", size: "文件大小" } },
  video: { title: "视频详情", statsLabels: { sample_rate: "帧率", channels: "分辨率", duration: "时长", size: "文件大小" } },
};

export default function ModalityDetailPage() {
  const params = useParams();
  const sessionId = Number(params.id);
  const modality = params.modality as Modality;
  const meta = MODALITY_META[modality];
  const modalityInfo = MODALITY_DESCRIPTIONS[modality] ?? { title: modality, statsLabels: {} };
  const allChannels = CHANNEL_MAP[modality] ?? ["CH1"];

  const [timeline, setTimeline] = useState<SessionTimeline>(DEMO_TIMELINE);
  const [currentTime, setCurrentTime] = useState(0);
  const [selectedChannels, setSelectedChannels] = useState<string[]>(allChannels.slice(0, 8));
  const [channelPickerOpen, setChannelPickerOpen] = useState(false);
  const [mStats, setMStats] = useState<ModalityStats | null>(null);

  const waveformRef = useRef<HTMLDivElement>(null);
  const spectrumRef = useRef<HTMLDivElement>(null);
  const chartWf = useRef<echarts.ECharts | null>(null);
  const chartSp = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    sessionApi.timeline(sessionId).then(setTimeline).catch(() => {});
    sessionApi.modalityStats(sessionId, modality).then(setMStats).catch(() => {
      setMStats({ modality, sample_rate: modality === "eeg" ? 1000 : 128, channels: allChannels, duration_seconds: 2700, file_size_bytes: 524288000 });
    });
  }, [sessionId, modality]);

  useEffect(() => {
    if (!waveformRef.current) return;
    if (!chartWf.current) chartWf.current = echarts.init(waveformRef.current);
    const chart = chartWf.current;

    const sr = mStats?.sample_rate ?? 256;
    const numSamples = Math.min(sr * 60, 8000);
    const series = selectedChannels.map((ch) => ({
      name: ch,
      type: "line" as const,
      data: Array.from({ length: numSamples }, (_, i) => [i / sr, (Math.random() - 0.5) * 2]),
      showSymbol: false,
      lineStyle: { width: 1 },
      sampling: "lttb" as const,
    }));

    chart.setOption({
      animation: false,
      grid: { left: 60, right: 16, top: 30, bottom: 50 },
      legend: { top: 0, textStyle: { fontSize: 10 } },
      tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
      xAxis: { type: "value", name: "时间 (s)", axisLabel: { formatter: "{value}s" } },
      yAxis: { type: "value", scale: true, splitLine: { lineStyle: { type: "dashed", opacity: 0.3 } } },
      dataZoom: [{ type: "inside" }, { type: "slider", height: 20, bottom: 4 }],
      series,
    }, true);

    const h = () => chart.resize();
    window.addEventListener("resize", h);
    return () => window.removeEventListener("resize", h);
  }, [selectedChannels, mStats]);

  useEffect(() => {
    if (!spectrumRef.current || modality === "video") return;
    if (!chartSp.current) chartSp.current = echarts.init(spectrumRef.current);
    const chart = chartSp.current;

    const freqs = Array.from({ length: 100 }, (_, i) => i * 0.5);
    const powers = freqs.map((f) => Math.exp(-f / 10) * (1 + Math.random() * 0.3));

    chart.setOption({
      animation: false,
      grid: { left: 60, right: 16, top: 20, bottom: 40 },
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: freqs.map((f) => `${f}`), name: "频率 (Hz)" },
      yAxis: { type: "value", name: "功率", splitLine: { lineStyle: { type: "dashed", opacity: 0.3 } } },
      series: [{
        type: "bar",
        data: powers,
        itemStyle: { color: meta?.color ?? "#6366f1" },
        barWidth: "60%",
      }],
    }, true);

    const h = () => chart.resize();
    window.addEventListener("resize", h);
    return () => window.removeEventListener("resize", h);
  }, [modality, meta]);

  useEffect(() => {
    return () => {
      chartWf.current?.dispose();
      chartSp.current?.dispose();
    };
  }, []);

  const toggleChannel = (ch: string) => {
    setSelectedChannels((prev) => prev.includes(ch) ? prev.filter((c) => c !== ch) : [...prev, ch]);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href={`/dashboard/sessions/${sessionId}`}>
            <Button variant="ghost" size="icon"><ArrowLeft className="h-4 w-4" /></Button>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: meta?.color }} />
              <h1 className="text-xl font-bold">{modalityInfo.title}</h1>
            </div>
            <p className="text-sm text-muted-foreground mt-1">会话 #{sessionId}</p>
          </div>
        </div>
        <a href={sessionApi.modalityDownloadUrl(sessionId, modality)}>
          <Button className="gap-2">
            <Download className="h-4 w-4" />
            下载 {meta?.label ?? modality} 原始数据
          </Button>
        </a>
      </div>

      {/* Stats summary */}
      {mStats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: "采样率", value: `${mStats.sample_rate} Hz` },
            { label: "通道数", value: `${mStats.channels.length}` },
            { label: "时长", value: formatDuration(mStats.duration_seconds) },
            { label: "文件大小", value: formatFileSize(mStats.file_size_bytes) },
          ].map((s) => (
            <Card key={s.label}>
              <CardContent className="p-4 text-center">
                <p className="text-sm text-muted-foreground">{s.label}</p>
                <p className="text-lg font-bold mt-1">{s.value}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Timeline bar */}
      <Card>
        <CardContent className="p-4">
          <TimelineBar segments={timeline.segments} totalDuration={timeline.total_duration} currentTime={currentTime} onSeek={setCurrentTime} />
        </CardContent>
      </Card>

      {/* Channel selector */}
      {allChannels.length > 1 && (
        <Card>
          <CardHeader className="p-4 pb-2 cursor-pointer" onClick={() => setChannelPickerOpen(!channelPickerOpen)}>
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">
                通道选择 — 显示 {selectedChannels.length}/{allChannels.length} 通道
              </CardTitle>
              {channelPickerOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </div>
          </CardHeader>
          {channelPickerOpen && (
            <CardContent className="p-4 pt-0">
              <div className="flex flex-wrap gap-2 mb-2">
                <Button variant="outline" size="sm" className="text-xs" onClick={() => setSelectedChannels([...allChannels])}>全选</Button>
                <Button variant="outline" size="sm" className="text-xs" onClick={() => setSelectedChannels([])}>全不选</Button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {allChannels.map((ch) => {
                  const active = selectedChannels.includes(ch);
                  return (
                    <button
                      key={ch}
                      onClick={() => toggleChannel(ch)}
                      className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${active ? "bg-primary text-primary-foreground border-primary" : "bg-muted/50 text-muted-foreground border-transparent hover:border-border"}`}
                    >
                      {active && <Check className="inline h-3 w-3 mr-1" />}
                      {ch}
                    </button>
                  );
                })}
              </div>
            </CardContent>
          )}
        </Card>
      )}

      {/* Waveform chart */}
      {modality !== "video" && (
        <Card>
          <CardHeader className="p-4 pb-2">
            <CardTitle className="text-sm">波形数据</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div ref={waveformRef} className="w-full h-72" />
          </CardContent>
        </Card>
      )}

      {/* Video player */}
      {modality === "video" && (
        <Card>
          <CardContent className="p-4">
            <div className="relative bg-black aspect-video rounded-lg flex items-center justify-center text-muted-foreground">
              暂无视频数据 — 连接服务器后自动加载
            </div>
          </CardContent>
        </Card>
      )}

      {/* Spectrum / analysis */}
      {modality !== "video" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <CardHeader className="p-4 pb-2">
              <CardTitle className="text-sm">
                {modality === "eeg" ? "功率谱密度" : modality === "audio" ? "频谱图" : "频率分布"}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div ref={spectrumRef} className="w-full h-56" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="p-4 pb-2">
              <CardTitle className="text-sm">统计摘要</CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-0">
              <div className="space-y-3 text-sm">
                {modality === "eeg" && (
                  <>
                    <div className="flex justify-between"><span className="text-muted-foreground">Delta (0.5-4Hz)</span><span className="font-medium">32.5%</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">Theta (4-8Hz)</span><span className="font-medium">21.3%</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">Alpha (8-13Hz)</span><span className="font-medium">28.7%</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">Beta (13-30Hz)</span><span className="font-medium">14.2%</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">Gamma (30+Hz)</span><span className="font-medium">3.3%</span></div>
                  </>
                )}
                {modality === "gsr" && (
                  <>
                    <div className="flex justify-between"><span className="text-muted-foreground">平均心率</span><span className="font-medium">72 bpm</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">RMSSD</span><span className="font-medium">42.3 ms</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">SDNN</span><span className="font-medium">58.7 ms</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">平均 SCL</span><span className="font-medium">5.2 µS</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">SCR 数量</span><span className="font-medium">23</span></div>
                  </>
                )}
                {modality === "emg" && (
                  <>
                    <div className="flex justify-between"><span className="text-muted-foreground">RMS 均值</span><span className="font-medium">12.4 µV</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">峰值</span><span className="font-medium">89.2 µV</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">中位频率</span><span className="font-medium">78.5 Hz</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">激活区间</span><span className="font-medium">15 段</span></div>
                  </>
                )}
                {modality === "audio" && (
                  <>
                    <div className="flex justify-between"><span className="text-muted-foreground">采样率</span><span className="font-medium">44.1 kHz</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">比特深度</span><span className="font-medium">16 bit</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">平均响度</span><span className="font-medium">-23.4 LUFS</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">峰值</span><span className="font-medium">-3.2 dBFS</span></div>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

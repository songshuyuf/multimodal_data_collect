"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowLeft, Download, Clock, User, Brain, Heart, Zap, AudioLines, Video, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { TimelineBar } from "@/components/viewer/TimelineBar";
import { WaveformPanel } from "@/components/viewer/WaveformPanel";
import { VideoPlayer } from "@/components/viewer/VideoPlayer";
import { StimulusPreview } from "@/components/viewer/StimulusPreview";
import { sessionApi, type SessionTimeline, type WaveformData } from "@/lib/api";
import { formatDuration, MODALITY_META, type Modality } from "@/lib/utils";

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
    { task_name: "休息", task_type: "rest", start_sec: 1800, end_sec: 1920, color: "#64748b" },
    { task_name: "VR 沉浸", task_type: "vr", start_sec: 1920, end_sec: 2520, color: "#ef4444" },
    { task_name: "结束休息", task_type: "rest", start_sec: 2520, end_sec: 2700, color: "#64748b" },
  ],
};

function generateDemoWaveform(modality: string, channels: string[], duration: number, sr: number): WaveformData {
  const numSamples = Math.min(sr * duration, 5000);
  const data = channels.map(() => Array.from({ length: numSamples }, () => (Math.random() - 0.5) * 2));
  return { modality, channels, sample_rate: sr, start_sec: 0, end_sec: duration, data };
}

const MODALITY_ICONS = { eeg: Brain, gsr: Heart, emg: Zap, audio: AudioLines, video: Video };

export default function SessionDetailPage() {
  const params = useParams();
  const sessionId = Number(params.id);

  const [timeline, setTimeline] = useState<SessionTimeline>(DEMO_TIMELINE);
  const [currentTime, setCurrentTime] = useState(0);
  const [collapsedModalities, setCollapsedModalities] = useState<Set<string>>(new Set());
  const [waveforms, setWaveforms] = useState<Record<string, WaveformData>>({});

  useEffect(() => {
    sessionApi.timeline(sessionId).then(setTimeline).catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    const modalities = timeline.modalities.filter((m) => m !== "video");
    modalities.forEach((m) => {
      const channelMap: Record<string, string[]> = {
        eeg: ["Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4"],
        gsr: ["SCL", "HR"],
        emg: ["EMG1", "EMG2"],
        audio: ["L", "R"],
      };
      const channels = channelMap[m] ?? ["CH1"];
      const sr = m === "eeg" ? 256 : m === "audio" ? 44100 : 128;
      const demo = generateDemoWaveform(m, channels, timeline.total_duration, sr);
      setWaveforms((prev) => ({ ...prev, [m]: demo }));

      sessionApi.waveform(sessionId, m, 0, Math.min(60, timeline.total_duration), channels)
        .then((d) => setWaveforms((prev) => ({ ...prev, [m]: d })))
        .catch(() => {});
    });
  }, [sessionId, timeline]);

  const handleSeek = useCallback((time: number) => setCurrentTime(time), []);

  const toggleCollapse = (m: string) => {
    setCollapsedModalities((prev) => {
      const next = new Set(prev);
      next.has(m) ? next.delete(m) : next.add(m);
      return next;
    });
  };

  const currentSegment = timeline.segments.find((s) => currentTime >= s.start_sec && currentTime < s.end_sec);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/dashboard/sessions">
            <Button variant="ghost" size="icon"><ArrowLeft className="h-4 w-4" /></Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold">会话详情 #{sessionId}</h1>
            <div className="flex items-center gap-3 text-sm text-muted-foreground mt-1">
              <span className="flex items-center gap-1"><User className="h-3.5 w-3.5" /> 患者名称</span>
              <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {formatDuration(timeline.total_duration)}</span>
              {currentSegment && (
                <Badge variant="outline" style={{ borderColor: currentSegment.color, color: currentSegment.color }}>
                  {currentSegment.task_name}
                </Badge>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link href={`/dashboard/sessions/${sessionId}/paradigms`}>
            <Button variant="outline" size="sm" className="gap-1">
              <FileText className="h-4 w-4" />
              实验范式
            </Button>
          </Link>
          <a href={sessionApi.downloadUrl(sessionId)}>
            <Button variant="outline" size="sm" className="gap-1">
              <Download className="h-4 w-4" />
              下载全部数据
            </Button>
          </a>
        </div>
      </div>

      {/* Modality quick-nav */}
      <div className="flex flex-wrap gap-2">
        {timeline.modalities.map((m) => {
          const meta = MODALITY_META[m as Modality];
          const Icon = MODALITY_ICONS[m as keyof typeof MODALITY_ICONS] ?? Brain;
          return (
            <Link key={m} href={`/dashboard/sessions/${sessionId}/${m}`}>
              <Badge variant="outline" className="gap-1 py-1.5 px-3 cursor-pointer hover:bg-muted transition-colors" style={{ borderColor: meta?.color }}>
                <Icon className="h-3.5 w-3.5" style={{ color: meta?.color }} />
                {meta?.label ?? m}
              </Badge>
            </Link>
          );
        })}
      </div>

      {/* Timeline */}
      <Card>
        <CardContent className="p-4">
          <TimelineBar
            segments={timeline.segments}
            totalDuration={timeline.total_duration}
            currentTime={currentTime}
            onSeek={handleSeek}
          />
        </CardContent>
      </Card>

      {/* Waveform panels */}
      <motion.div className="space-y-3" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
        {timeline.modalities
          .filter((m) => m !== "video")
          .map((m) => {
            const wf = waveforms[m];
            if (!wf) return null;
            return (
              <WaveformPanel
                key={m}
                modality={m as Modality}
                channels={wf.channels}
                data={wf.data}
                sampleRate={wf.sample_rate}
                startSec={wf.start_sec}
                endSec={wf.end_sec}
                currentTime={currentTime}
                sessionId={sessionId}
                onTimeChange={handleSeek}
                collapsed={collapsedModalities.has(m)}
                onToggleCollapse={() => toggleCollapse(m)}
              />
            );
          })}
      </motion.div>

      {/* Bottom row: video + stimulus */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <VideoPlayer src="" currentTime={currentTime} onTimeUpdate={handleSeek} />
        <StimulusPreview sessionId={sessionId} currentTime={currentTime} />
      </div>
    </div>
  );
}

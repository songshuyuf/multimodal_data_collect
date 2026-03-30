"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowLeft, Download, Clock, Music, Image as ImageIcon, Video, Gamepad2, Coffee, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { sessionApi, type ParadigmDetail, type StimulusItem } from "@/lib/api";
import { formatDuration } from "@/lib/utils";

const TYPE_ICONS: Record<string, typeof Music> = {
  music: Music,
  painting: ImageIcon,
  vr: Gamepad2,
  rest: Coffee,
  probe: Gamepad2,
  video: Video,
};

const TYPE_COLORS: Record<string, string> = {
  rest: "#64748b",
  music: "#8b5cf6",
  painting: "#f59e0b",
  probe: "#22c55e",
  vr: "#ef4444",
};

const DEMO_PARADIGMS: ParadigmDetail[] = [
  { task_name: "基线休息", task_type: "rest", start_sec: 0, end_sec: 180, stimuli: [] },
  {
    task_name: "音乐鉴赏", task_type: "music", start_sec: 180, end_sec: 660,
    stimuli: [
      { name: "巴赫 - G 弦上的咏叹调", type: "audio", url: "#", thumbnail_url: "" },
      { name: "德彪西 - 月光", type: "audio", url: "#", thumbnail_url: "" },
      { name: "肖邦 - 夜曲 Op.9 No.2", type: "audio", url: "#", thumbnail_url: "" },
    ],
  },
  { task_name: "休息", task_type: "rest", start_sec: 660, end_sec: 780, stimuli: [] },
  {
    task_name: "绘画鉴赏", task_type: "painting", start_sec: 780, end_sec: 1260,
    stimuli: [
      { name: "莫奈 - 睡莲", type: "image", url: "#", thumbnail_url: "" },
      { name: "梵高 - 星夜", type: "image", url: "#", thumbnail_url: "" },
      { name: "达利 - 记忆的永恒", type: "image", url: "#", thumbnail_url: "" },
    ],
  },
  { task_name: "休息", task_type: "rest", start_sec: 1260, end_sec: 1380, stimuli: [] },
  {
    task_name: "点探测任务", task_type: "probe", start_sec: 1380, end_sec: 1800,
    stimuli: [
      { name: "探测刺激序列 A", type: "image", url: "#" },
      { name: "探测刺激序列 B", type: "image", url: "#" },
    ],
  },
  { task_name: "休息", task_type: "rest", start_sec: 1800, end_sec: 1920, stimuli: [] },
  {
    task_name: "VR 沉浸体验", task_type: "vr", start_sec: 1920, end_sec: 2520,
    stimuli: [
      { name: "虚拟画廊场景", type: "video", url: "#" },
    ],
  },
  { task_name: "结束休息", task_type: "rest", start_sec: 2520, end_sec: 2700, stimuli: [] },
];

export default function ParadigmsPage() {
  const params = useParams();
  const sessionId = Number(params.id);
  const [paradigms, setParadigms] = useState<ParadigmDetail[]>(DEMO_PARADIGMS);
  const [expandedIdx, setExpandedIdx] = useState<Set<number>>(new Set());

  useEffect(() => {
    sessionApi.paradigms(sessionId).then(setParadigms).catch(() => {});
  }, [sessionId]);

  const toggleExpand = (i: number) => {
    setExpandedIdx((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  };

  const totalDuration = paradigms.length > 0 ? paradigms[paradigms.length - 1].end_sec : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href={`/dashboard/sessions/${sessionId}`}>
            <Button variant="ghost" size="icon"><ArrowLeft className="h-4 w-4" /></Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold">实验范式详情</h1>
            <p className="text-sm text-muted-foreground mt-1">
              会话 #{sessionId} · 共 {paradigms.length} 个范式区间 · 总时长 {formatDuration(totalDuration)}
            </p>
          </div>
        </div>
        <Button variant="outline" className="gap-2">
          <Download className="h-4 w-4" />
          下载范式日志 (CSV)
        </Button>
      </div>

      {/* Timeline overview */}
      <Card>
        <CardContent className="p-4">
          <div className="relative h-8 rounded-md overflow-hidden flex">
            {paradigms.map((p, i) => {
              const width = ((p.end_sec - p.start_sec) / totalDuration) * 100;
              return (
                <div
                  key={i}
                  className="h-full flex items-center justify-center text-white text-xs font-medium cursor-pointer hover:opacity-80 transition-opacity"
                  style={{ width: `${width}%`, backgroundColor: TYPE_COLORS[p.task_type] ?? "#6366f1" }}
                  onClick={() => toggleExpand(i)}
                  title={`${p.task_name} (${formatDuration(p.start_sec)} - ${formatDuration(p.end_sec)})`}
                >
                  {width > 5 ? p.task_name : ""}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Paradigm list */}
      <div className="space-y-3">
        {paradigms.map((p, i) => {
          const Icon = TYPE_ICONS[p.task_type] ?? Coffee;
          const expanded = expandedIdx.has(i);
          const duration = p.end_sec - p.start_sec;
          return (
            <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <Card className={expanded ? "border-primary/30" : ""}>
                <CardHeader className="p-4 cursor-pointer" onClick={() => toggleExpand(i)}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div
                        className="flex h-9 w-9 items-center justify-center rounded-lg text-white"
                        style={{ backgroundColor: TYPE_COLORS[p.task_type] ?? "#6366f1" }}
                      >
                        <Icon className="h-4 w-4" />
                      </div>
                      <div>
                        <div className="font-medium">{p.task_name}</div>
                        <div className="text-xs text-muted-foreground flex items-center gap-2">
                          <Clock className="h-3 w-3" />
                          {formatDuration(p.start_sec)} → {formatDuration(p.end_sec)}
                          <span>({formatDuration(duration)})</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {p.stimuli.length > 0 && (
                        <Badge variant="secondary" className="text-xs">{p.stimuli.length} 个刺激</Badge>
                      )}
                      {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    </div>
                  </div>
                </CardHeader>
                {expanded && p.stimuli.length > 0 && (
                  <CardContent className="p-4 pt-0">
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {p.stimuli.map((s, j) => {
                        const SIcon = TYPE_ICONS[s.type] ?? ImageIcon;
                        return (
                          <div key={j} className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
                            {s.thumbnail_url ? (
                              <img src={s.thumbnail_url} alt={s.name} className="w-12 h-12 object-cover rounded" />
                            ) : (
                              <div className="w-12 h-12 rounded bg-muted flex items-center justify-center">
                                <SIcon className="h-5 w-5 text-muted-foreground" />
                              </div>
                            )}
                            <div className="flex-1 min-w-0">
                              <div className="text-sm font-medium truncate">{s.name}</div>
                              <div className="text-xs text-muted-foreground capitalize">{s.type}</div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                )}
                {expanded && p.stimuli.length === 0 && (
                  <CardContent className="p-4 pt-0">
                    <p className="text-sm text-muted-foreground">此阶段无刺激素材（休息阶段）</p>
                  </CardContent>
                )}
              </Card>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

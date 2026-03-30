"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Users, CalendarDays, HardDrive, Clock, ArrowRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
import { statsApi, type DashboardStats } from "@/lib/api";
import { formatDuration, formatFileSize, MODALITY_META } from "@/lib/utils";

const DEMO_STATS: DashboardStats = {
  patient_count: 24,
  session_count: 156,
  total_duration_seconds: 432000,
  total_data_size_bytes: 85899345920,
  recent_sessions: [
    { id: 1, patient_name: "张三", session_name: "session_20260326_01", created_at: "2026-03-26T10:30:00", duration_seconds: 2700, modalities: ["eeg", "gsr", "emg", "audio", "video"] },
    { id: 2, patient_name: "李四", session_name: "session_20260325_02", created_at: "2026-03-25T14:00:00", duration_seconds: 1800, modalities: ["eeg", "gsr", "audio"] },
    { id: 3, patient_name: "王五", session_name: "session_20260324_01", created_at: "2026-03-24T09:00:00", duration_seconds: 3600, modalities: ["eeg", "gsr", "emg", "audio", "video"] },
  ],
};

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>(DEMO_STATS);

  useEffect(() => {
    statsApi.dashboard().then(setStats).catch(() => {});
  }, []);

  const statCards = [
    { label: "患者总数", value: stats.patient_count, icon: Users, color: "text-blue-500" },
    { label: "会话总数", value: stats.session_count, icon: CalendarDays, color: "text-green-500" },
    { label: "总时长", value: formatDuration(stats.total_duration_seconds), icon: Clock, color: "text-yellow-500" },
    { label: "数据量", value: formatFileSize(stats.total_data_size_bytes), icon: HardDrive, color: "text-purple-500" },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">数据总览</h1>
        <p className="text-muted-foreground">多模态采集系统数据概况</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((s, i) => (
          <motion.div key={s.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}>
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">{s.label}</p>
                    <p className="text-2xl font-bold mt-1">{s.value}</p>
                  </div>
                  <s.icon className={`h-8 w-8 ${s.color} opacity-80`} />
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg">最近会话</CardTitle>
          <Link href="/dashboard/sessions">
            <Button variant="ghost" size="sm" className="gap-1">
              查看全部 <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {stats.recent_sessions.map((s) => (
              <Link key={s.id} href={`/dashboard/sessions/${s.id}`}>
                <div className="flex items-center justify-between p-3 rounded-lg hover:bg-muted/50 transition-colors cursor-pointer">
                  <div>
                    <div className="font-medium">{s.patient_name} — {s.session_name}</div>
                    <div className="text-sm text-muted-foreground">{new Date(s.created_at).toLocaleString("zh-CN")} · {formatDuration(s.duration_seconds)}</div>
                  </div>
                  <div className="flex gap-1">
                    {s.modalities.map((m) => (
                      <Badge key={m} variant="outline" className="text-xs" style={{ borderColor: MODALITY_META[m as keyof typeof MODALITY_META]?.color }}>
                        {MODALITY_META[m as keyof typeof MODALITY_META]?.label ?? m}
                      </Badge>
                    ))}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

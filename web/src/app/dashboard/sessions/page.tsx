"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Search, Filter, Download, ChevronLeft, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
import { sessionApi, type SessionSummary, type PaginatedSessions } from "@/lib/api";
import { formatDuration, MODALITY_META, type Modality } from "@/lib/utils";

const DEMO: PaginatedSessions = {
  items: Array.from({ length: 10 }, (_, i) => ({
    id: i + 1,
    patient_name: ["张三", "李四", "王五", "赵六", "陈七"][i % 5],
    session_name: `session_202603${String(20 + i).padStart(2, "0")}_01`,
    created_at: `2026-03-${String(20 + i).padStart(2, "0")}T10:00:00`,
    duration_seconds: 1800 + i * 300,
    modalities: i % 2 === 0 ? ["eeg", "gsr", "emg", "audio", "video"] : ["eeg", "gsr", "audio"],
  })),
  total: 56,
  page: 1,
  page_size: 10,
};

export default function SessionsPage() {
  const [data, setData] = useState<PaginatedSessions>(DEMO);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  useEffect(() => {
    sessionApi.list({ page, page_size: 10 }).then(setData).catch(() => {});
  }, [page]);

  const totalPages = Math.ceil(data.total / data.page_size);

  const filtered = search
    ? data.items.filter((s) => s.patient_name.includes(search) || s.session_name.includes(search))
    : data.items;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">会话列表</h1>
          <p className="text-muted-foreground">共 {data.total} 个采集会话</p>
        </div>
        <Button variant="outline" className="gap-2">
          <Download className="h-4 w-4" />
          批量导出
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="搜索患者或会话名称..." className="pl-9" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <Button variant="outline" size="icon"><Filter className="h-4 w-4" /></Button>
      </div>

      <div className="space-y-2">
        {filtered.map((s, i) => (
          <motion.div key={s.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }}>
            <Link href={`/dashboard/sessions/${s.id}`}>
              <Card className="hover:shadow-md hover:border-primary/20 transition-all cursor-pointer">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary font-bold text-sm">
                        #{s.id}
                      </div>
                      <div>
                        <div className="font-medium">{s.patient_name}</div>
                        <div className="text-sm text-muted-foreground">{s.session_name}</div>
                      </div>
                    </div>

                    <div className="flex items-center gap-6">
                      <div className="hidden sm:flex gap-1">
                        {s.modalities.map((m) => {
                          const meta = MODALITY_META[m as Modality];
                          return meta ? (
                            <Badge key={m} variant="outline" className="text-xs" style={{ borderColor: meta.color, color: meta.color }}>
                              {meta.label}
                            </Badge>
                          ) : null;
                        })}
                      </div>
                      <div className="text-right text-sm">
                        <div>{formatDuration(s.duration_seconds)}</div>
                        <div className="text-muted-foreground">{new Date(s.created_at).toLocaleDateString("zh-CN")}</div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          </motion.div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <Button variant="outline" size="icon" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground">第 {page} / {totalPages} 页</span>
          <Button variant="outline" size="icon" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}

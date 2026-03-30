"use client";

import { motion } from "framer-motion";
import { Download, Monitor, Shield, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const RELEASES = [
  {
    version: "0.7.0",
    date: "2026-03-26",
    latest: true,
    size: "约 280 MB",
    notes: [
      "五模态数据同步采集（EEG、GSR、EMG、音频、视频）",
      "实验范式引擎（音乐鉴赏、绘画鉴赏、点探测、VR）",
      "实时波形监控面板",
      "数据自动上传至服务器",
    ],
  },
  {
    version: "0.6.0",
    date: "2026-03-10",
    latest: false,
    size: "约 250 MB",
    notes: ["初始版本：基础数据采集", "EEG 与 GSR 采集", "本地数据存储"],
  },
];

export default function DownloadPage() {
  return (
    <div className="py-16">
      <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
        <motion.div
          className="text-center mb-12"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-4xl font-bold mb-4">软件下载</h1>
          <p className="text-lg text-muted-foreground">下载 AI 艺术诊疗多模态采集系统客户端</p>
        </motion.div>

        <div className="grid gap-4 mb-12">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { icon: Monitor, title: "Windows 平台", desc: "支持 Windows 10/11" },
              { icon: Shield, title: "安全可靠", desc: "内置数据加密与传输校验" },
              { icon: RefreshCw, title: "自动更新", desc: "检测新版本自动提示升级" },
            ].map((f) => (
              <Card key={f.title} className="border-transparent bg-muted/50">
                <CardContent className="p-4 flex items-center gap-3">
                  <f.icon className="h-8 w-8 text-primary shrink-0" />
                  <div>
                    <div className="font-medium text-sm">{f.title}</div>
                    <div className="text-xs text-muted-foreground">{f.desc}</div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          {RELEASES.map((r) => (
            <motion.div
              key={r.version}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <Card className={r.latest ? "border-primary/30 shadow-md" : ""}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <CardTitle>v{r.version}</CardTitle>
                      {r.latest && <Badge>最新版本</Badge>}
                    </div>
                    <span className="text-sm text-muted-foreground">{r.date}</span>
                  </div>
                  <CardDescription>安装包大小: {r.size}</CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground mb-4">
                    {r.notes.map((n) => (
                      <li key={n}>{n}</li>
                    ))}
                  </ul>
                  <Button className="gap-2" variant={r.latest ? "default" : "outline"}>
                    <Download className="h-4 w-4" />
                    下载 v{r.version}
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}

"use client";

import { motion } from "framer-motion";
import { Brain, Heart, Zap, AudioLines, Video, ArrowRight, Database, Shield, Cpu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import Link from "next/link";

const MODALITIES = [
  { icon: Brain, label: "EEG 脑电", desc: "64 通道脑电信号实时采集与分析，捕捉艺术鉴赏时的神经响应", color: "text-blue-500" },
  { icon: Heart, label: "GSR 皮电", desc: "皮肤电导与心率变异性监测，量化情绪唤醒程度", color: "text-green-500" },
  { icon: Zap, label: "EMG 肌电", desc: "面部与肢体肌电采集，追踪微表情和身体反应", color: "text-yellow-500" },
  { icon: AudioLines, label: "音频采集", desc: "高保真音频记录，捕捉语音反馈与环境声音", color: "text-purple-500" },
  { icon: Video, label: "视频记录", desc: "多角度视频录制，记录行为表现与面部表情", color: "text-red-500" },
];

const FEATURES = [
  { icon: Database, title: "多模态同步", desc: "五种模态数据时间轴精准对齐，毫秒级同步" },
  { icon: Cpu, title: "实时分析", desc: "在线波形显示、频谱分析、心率计算" },
  { icon: Shield, title: "实验范式", desc: "音乐鉴赏、绘画鉴赏、点探测、VR 沉浸等多种范式" },
];

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.1, duration: 0.5 } }),
};

export default function HomePage() {
  return (
    <div className="overflow-hidden">
      {/* Hero */}
      <section className="relative flex min-h-[85vh] items-center justify-center">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/5 via-transparent to-transparent" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/10 via-transparent to-transparent" />
        <div className="relative mx-auto max-w-5xl px-4 text-center">
          <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.6 }}>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border bg-background/80 px-4 py-2 text-sm backdrop-blur">
              <Brain className="h-4 w-4 text-primary" />
              Westlake University TGAI Lab
            </div>
          </motion.div>

          <motion.h1
            className="text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl lg:text-7xl"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.6 }}
          >
            AI 艺术诊疗
            <br />
            <span className="bg-gradient-to-r from-primary via-blue-400 to-purple-500 bg-clip-text text-transparent">
              多模态采集系统
            </span>
          </motion.h1>

          <motion.p
            className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.6 }}
          >
            融合 EEG、GSR、EMG、音频和视频五种模态，构建艺术治疗研究的完整数据采集与分析平台
          </motion.p>

          <motion.div
            className="mt-8 flex flex-wrap items-center justify-center gap-4"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6, duration: 0.6 }}
          >
            <Link href="/dashboard">
              <Button size="lg" className="gap-2">
                进入数据平台 <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="/download">
              <Button size="lg" variant="outline">
                下载客户端
              </Button>
            </Link>
          </motion.div>
        </div>
      </section>

      {/* Modalities */}
      <section className="py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div className="text-center mb-16" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={0}>
            <h2 className="text-3xl font-bold">五大采集模态</h2>
            <p className="mt-3 text-muted-foreground">全方位捕捉艺术体验中的生理与行为数据</p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">
            {MODALITIES.map((m, i) => (
              <motion.div key={m.label} initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={i + 1}>
                <Card className="group relative overflow-hidden border-transparent bg-muted/50 hover:border-primary/30 hover:shadow-lg transition-all duration-300 h-full">
                  <CardContent className="p-6 text-center">
                    <div className={`mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-background shadow-sm ${m.color}`}>
                      <m.icon className="h-7 w-7" />
                    </div>
                    <h3 className="font-semibold mb-2">{m.label}</h3>
                    <p className="text-sm text-muted-foreground">{m.desc}</p>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-24 bg-muted/30">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div className="text-center mb-16" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={0}>
            <h2 className="text-3xl font-bold">核心功能</h2>
          </motion.div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {FEATURES.map((f, i) => (
              <motion.div key={f.title} initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={i + 1}>
                <Card className="h-full border-transparent bg-background/80 hover:shadow-lg transition-all">
                  <CardContent className="p-8">
                    <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <f.icon className="h-6 w-6" />
                    </div>
                    <h3 className="text-xl font-semibold mb-2">{f.title}</h3>
                    <p className="text-muted-foreground">{f.desc}</p>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24">
        <div className="mx-auto max-w-3xl px-4 text-center">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={0}>
            <h2 className="text-3xl font-bold mb-4">开始探索数据</h2>
            <p className="text-muted-foreground mb-8">
              登录数据平台，查看多模态实验数据、同步时间轴分析、单模态深度分析，一切尽在浏览器中
            </p>
            <div className="flex flex-wrap justify-center gap-4">
              <Link href="/dashboard">
                <Button size="lg" className="gap-2">进入数据平台 <ArrowRight className="h-4 w-4" /></Button>
              </Link>
              <Link href="/join">
                <Button size="lg" variant="outline">加入我们</Button>
              </Link>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
}

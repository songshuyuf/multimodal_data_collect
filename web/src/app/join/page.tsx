"use client";

import { motion } from "framer-motion";
import { Mail, MapPin, GraduationCap, Code, FlaskConical } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const POSITIONS = [
  {
    title: "博士研究生",
    icon: GraduationCap,
    tags: ["脑机接口", "情感计算", "信号处理"],
    desc: "研究多模态脑信号与艺术治疗的交互机制，开发新型情感识别算法",
  },
  {
    title: "研究助理 / 工程师",
    icon: Code,
    tags: ["Python", "全栈开发", "数据分析"],
    desc: "负责采集系统开发、数据平台建设、实验范式设计与数据分析",
  },
  {
    title: "硕士研究生",
    icon: FlaskConical,
    tags: ["VR/AR", "用户体验", "实验设计"],
    desc: "设计并实施 VR 艺术体验实验，分析沉浸式环境下的多模态生理数据",
  },
];

export default function JoinPage() {
  return (
    <div className="py-16">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <motion.div className="text-center mb-16" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-4xl font-bold mb-4">加入我们</h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            我们正在寻找对 AI、神经科学和艺术交叉领域充满热情的伙伴
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-16">
          {POSITIONS.map((p, i) => (
            <motion.div
              key={p.title}
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.15, duration: 0.5 }}
            >
              <Card className="h-full hover:shadow-lg transition-all">
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <p.icon className="h-5 w-5" />
                    </div>
                    <CardTitle className="text-lg">{p.title}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground mb-4">{p.desc}</p>
                  <div className="flex flex-wrap gap-1">
                    {p.tags.map((t) => (
                      <Badge key={t} variant="secondary" className="text-xs">{t}</Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* Contact */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <Card>
            <CardHeader>
              <CardTitle>联系我们</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div className="space-y-4">
                  <div className="flex items-center gap-3 text-sm">
                    <MapPin className="h-5 w-5 text-primary shrink-0" />
                    <span>浙江省杭州市西湖区 · 西湖大学云谷校区</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <Mail className="h-5 w-5 text-primary shrink-0" />
                    <span>tgai-lab@westlake.edu.cn</span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-4">
                    请将简历发送至上述邮箱，邮件标题格式：【应聘岗位】姓名-学校
                  </p>
                </div>
                <div className="space-y-3">
                  <Input placeholder="您的姓名" />
                  <Input placeholder="邮箱地址" type="email" />
                  <Input placeholder="简要介绍您的背景和兴趣" />
                  <Button className="w-full">提交申请</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}

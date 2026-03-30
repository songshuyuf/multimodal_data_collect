"use client";

import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

interface Member {
  name: string;
  role: string;
  focus: string;
  initials: string;
  tags: string[];
}

const MEMBERS: Member[] = [
  { name: "待补充", role: "课题组负责人", focus: "脑机接口与艺术治疗", initials: "PI", tags: ["PI", "neuroscience"] },
  { name: "待补充", role: "博士研究生", focus: "多模态信号处理", initials: "PhD", tags: ["signal processing", "EEG"] },
  { name: "待补充", role: "硕士研究生", focus: "情感计算与 VR", initials: "MS", tags: ["affective computing", "VR"] },
  { name: "待补充", role: "研究助理", focus: "系统开发与数据分析", initials: "RA", tags: ["full-stack", "data"] },
];

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.1, duration: 0.5 } }),
};

export default function TeamPage() {
  return (
    <div className="py-16">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <motion.div className="text-center mb-16" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={0}>
          <h1 className="text-4xl font-bold mb-4">研究团队</h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            西湖大学 TGAI Lab — 致力于探索 AI 与艺术治疗的交叉领域
          </p>
        </motion.div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {MEMBERS.map((m, i) => (
            <motion.div key={i} initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={i + 1}>
              <Card className="group hover:shadow-lg transition-all duration-300 h-full">
                <CardContent className="p-6 text-center">
                  <Avatar className="h-20 w-20 mx-auto mb-4 text-lg">
                    <AvatarFallback className="bg-primary/10 text-primary text-lg font-bold">
                      {m.initials}
                    </AvatarFallback>
                  </Avatar>
                  <h3 className="text-lg font-semibold">{m.name}</h3>
                  <p className="text-sm text-primary font-medium mb-2">{m.role}</p>
                  <p className="text-sm text-muted-foreground mb-3">{m.focus}</p>
                  <div className="flex flex-wrap justify-center gap-1">
                    {m.tags.map((t) => (
                      <Badge key={t} variant="secondary" className="text-xs">{t}</Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}

import { Brain } from "lucide-react";
import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t bg-muted/30">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div>
            <div className="flex items-center gap-2 font-bold text-lg mb-3">
              <Brain className="h-5 w-5 text-primary" />
              AI 艺术诊疗多模态采集系统
            </div>
            <p className="text-sm text-muted-foreground">
              西湖大学 TGAI Lab — 融合 EEG、GSR、EMG、音视频的多模态艺术治疗研究平台
            </p>
          </div>

          <div>
            <h3 className="font-semibold mb-3">快速链接</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link href="/team" className="hover:text-primary transition-colors">团队介绍</Link></li>
              <li><Link href="/download" className="hover:text-primary transition-colors">软件下载</Link></li>
              <li><Link href="/dashboard" className="hover:text-primary transition-colors">数据平台</Link></li>
              <li><Link href="/join" className="hover:text-primary transition-colors">加入我们</Link></li>
            </ul>
          </div>

          <div>
            <h3 className="font-semibold mb-3">联系方式</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li>西湖大学云谷校区</li>
              <li>浙江省杭州市西湖区</li>
              <li>
                <a href="https://www.westlake.edu.cn" target="_blank" rel="noopener noreferrer" className="hover:text-primary transition-colors">
                  www.westlake.edu.cn
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t text-center text-sm text-muted-foreground">
          &copy; {new Date().getFullYear()} Westlake University TGAI Lab. All rights reserved.
        </div>
      </div>
    </footer>
  );
}

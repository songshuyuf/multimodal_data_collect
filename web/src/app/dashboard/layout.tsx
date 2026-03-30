"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, List, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

const SIDEBAR_LINKS = [
  { href: "/dashboard", label: "数据总览", icon: BarChart3, exact: true },
  { href: "/dashboard/sessions", label: "会话列表", icon: List, exact: false },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout, hydrate } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <div className="flex flex-1">
      {/* Sidebar */}
      <aside className="hidden md:flex w-56 flex-col border-r bg-muted/30 p-4">
        <div className="mb-6">
          <p className="text-sm text-muted-foreground">当前用户</p>
          <p className="font-medium truncate">{user?.username ?? "未登录"}</p>
        </div>

        <nav className="flex-1 space-y-1">
          {SIDEBAR_LINKS.map((link) => {
            const active = link.exact ? pathname === link.href : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-muted"
                )}
              >
                <link.icon className="h-4 w-4" />
                {link.label}
              </Link>
            );
          })}
        </nav>

        <Button variant="ghost" size="sm" className="justify-start gap-2 text-muted-foreground" onClick={handleLogout}>
          <LogOut className="h-4 w-4" />
          退出登录
        </Button>
      </aside>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <div className="mx-auto max-w-7xl p-6">
          {children}
        </div>
      </div>
    </div>
  );
}

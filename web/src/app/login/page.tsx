"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff, Brain } from "lucide-react";
import { Input } from "@/components/ui/input";
import { AnimatedCharacters } from "@/components/ui/animated-characters";
import { InteractiveHoverButton } from "@/components/ui/interactive-hover-button";
import { useAuthStore } from "@/lib/auth";
import { authApi } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [showPassword, setShowPassword] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleLogin = async () => {
    if (!username || !password) {
      setError("请输入用户名和密码");
      return;
    }
    setIsLoading(true);
    setError("");
    try {
      const res = await authApi.login({ username, password });
      setAuth(res.user, res.access_token);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "用户名或密码错误，请重试");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen w-full fixed inset-0 z-50 bg-background">
      {/* Left Content Section with Animated Characters */}
      <div className="hidden lg:flex lg:w-1/2 relative flex-col items-center justify-between overflow-hidden bg-[hsl(220,15%,76%)] dark:bg-[hsl(220,15%,22%)] p-8">
        {/* Top Logo */}
        <div className="flex items-center gap-2.5 self-start z-10">
          <Brain className="h-7 w-7 text-primary" />
          <span className="text-lg font-bold tracking-tight">AI 艺术诊疗</span>
        </div>

        {/* Center: Animated Characters */}
        <div className="z-10">
          <AnimatedCharacters
            isTyping={isTyping}
            showPassword={showPassword}
            passwordLength={password.length}
          />
        </div>

        {/* Bottom Links */}
        <div className="z-10 flex items-center gap-6 text-xs text-muted-foreground">
          <a
            href="https://www.westlake.edu.cn"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors"
          >
            Westlake University
          </a>
          <span className="hover:text-foreground transition-colors cursor-default">
            TGAI Lab
          </span>
        </div>

        {/* Subtle background gradient */}
        <div className="absolute inset-0 bg-gradient-to-b from-black/5 to-transparent pointer-events-none" />
      </div>

      {/* Right Login Section */}
      <div className="flex w-full lg:w-1/2 items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-[420px] space-y-8">
          {/* Mobile Logo */}
          <div className="flex items-center gap-2 lg:hidden">
            <Brain className="h-6 w-6 text-primary" />
            <span className="font-bold text-lg">AI 艺术诊疗</span>
          </div>

          {/* Header */}
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Welcome back!</h1>
            <p className="mt-2 text-muted-foreground">Please enter your details</p>
          </div>

          {/* Login Form */}
          <div className="space-y-5">
            <div className="space-y-2">
              <label className="text-sm font-medium">用户名</label>
              <Input
                placeholder="请输入用户名"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onFocus={() => setIsTyping(true)}
                onBlur={() => setIsTyping(false)}
                className="h-12 bg-background border-border/60 focus:border-primary"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">密码</label>
              <div className="relative">
                <Input
                  placeholder="请输入密码"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onFocus={() => setIsTyping(true)}
                  onBlur={() => setIsTyping(false)}
                  onKeyDown={(e) => e.key === "Enter" && handleLogin()}
                  className="h-12 pr-12 bg-background border-border/60 focus:border-primary"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="h-5 w-5" />
                  ) : (
                    <Eye className="h-5 w-5" />
                  )}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" className="rounded border-border accent-primary" />
                <span className="text-sm text-muted-foreground">Remember for 30 days</span>
              </label>
              <button className="text-sm text-primary hover:underline">
                Forgot password?
              </button>
            </div>

            {error && (
              <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2.5">
                {error}
              </p>
            )}

            <InteractiveHoverButton
              text="Log in"
              className="w-full h-12 text-base font-medium"
              onClick={handleLogin}
              disabled={isLoading}
            />
          </div>

          {/* Sign Up Link */}
          <p className="text-center text-sm text-muted-foreground">
            Don&apos;t have an account?{" "}
            <Link href="/login?tab=register" className="text-primary font-medium hover:underline">
              Sign Up
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

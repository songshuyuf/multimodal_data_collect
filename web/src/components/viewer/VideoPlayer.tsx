"use client";

import { useRef, useEffect } from "react";
import { Play, Pause, SkipBack, SkipForward } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState } from "react";

interface VideoPlayerProps {
  src: string;
  currentTime: number;
  onTimeUpdate?: (time: number) => void;
}

export function VideoPlayer({ src, currentTime, onTimeUpdate }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (videoRef.current && Math.abs(videoRef.current.currentTime - currentTime) > 1) {
      videoRef.current.currentTime = currentTime;
    }
  }, [currentTime]);

  const toggle = () => {
    if (!videoRef.current) return;
    if (playing) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
    setPlaying(!playing);
  };

  const skip = (delta: number) => {
    if (!videoRef.current) return;
    videoRef.current.currentTime += delta;
  };

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="px-3 py-2 bg-muted/30 text-sm font-medium">视频回放</div>
      <div className="relative bg-black aspect-video">
        {src ? (
          <video
            ref={videoRef}
            src={src}
            className="w-full h-full object-contain"
            onTimeUpdate={() => onTimeUpdate?.(videoRef.current?.currentTime ?? 0)}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-muted-foreground text-sm">
            暂无视频数据
          </div>
        )}
      </div>
      <div className="flex items-center justify-center gap-2 p-2 bg-muted/20">
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => skip(-5)}>
          <SkipBack className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={toggle}>
          {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => skip(5)}>
          <SkipForward className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

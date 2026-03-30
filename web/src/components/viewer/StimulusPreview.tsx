"use client";

import { useState, useEffect } from "react";
import { sessionApi, type StimulusItem } from "@/lib/api";
import { Music, Image as ImageIcon, Video, FileText } from "lucide-react";

const TYPE_ICONS: Record<string, typeof Music> = {
  audio: Music,
  image: ImageIcon,
  video: Video,
};

interface StimulusPreviewProps {
  sessionId: number;
  currentTime: number;
}

export function StimulusPreview({ sessionId, currentTime }: StimulusPreviewProps) {
  const [stimuli, setStimuli] = useState<StimulusItem[]>([]);

  useEffect(() => {
    const timer = setTimeout(() => {
      sessionApi.stimulus(sessionId, Math.floor(currentTime)).then(setStimuli).catch(() => {});
    }, 300);
    return () => clearTimeout(timer);
  }, [sessionId, currentTime]);

  return (
    <div className="border rounded-lg overflow-hidden h-full">
      <div className="px-3 py-2 bg-muted/30 text-sm font-medium">当前刺激素材</div>
      <div className="p-3">
        {stimuli.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-muted-foreground text-sm">
            <FileText className="h-8 w-8 mb-2 opacity-50" />
            <span>当前时间无刺激素材</span>
          </div>
        ) : (
          <div className="space-y-3">
            {stimuli.map((s, i) => {
              const Icon = TYPE_ICONS[s.type] ?? FileText;
              return (
                <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-muted/30">
                  {s.thumbnail_url ? (
                    <img src={s.thumbnail_url} alt={s.name} className="w-16 h-16 object-cover rounded" />
                  ) : (
                    <div className="w-16 h-16 rounded bg-muted flex items-center justify-center">
                      <Icon className="h-6 w-6 text-muted-foreground" />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">{s.name}</div>
                    <div className="text-xs text-muted-foreground capitalize">{s.type}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

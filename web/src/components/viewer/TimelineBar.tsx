"use client";

import { useRef, useCallback, useState, useEffect } from "react";
import { type TimelineSegment } from "@/lib/api";
import { formatDuration } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const PARADIGM_COLORS: Record<string, string> = {
  rest: "#64748b",
  music: "#8b5cf6",
  painting: "#f59e0b",
  probe: "#22c55e",
  vr: "#ef4444",
  default: "#6366f1",
};

interface TimelineBarProps {
  segments: TimelineSegment[];
  totalDuration: number;
  currentTime: number;
  onSeek: (time: number) => void;
}

export function TimelineBar({ segments, totalDuration, currentTime, onSeek }: TimelineBarProps) {
  const barRef = useRef<HTMLDivElement>(null);
  const [hoverTime, setHoverTime] = useState<number | null>(null);
  const [hoverSegment, setHoverSegment] = useState<TimelineSegment | null>(null);

  const getTimeFromX = useCallback(
    (clientX: number) => {
      if (!barRef.current) return 0;
      const rect = barRef.current.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      return ratio * totalDuration;
    },
    [totalDuration]
  );

  const handleClick = (e: React.MouseEvent) => {
    onSeek(getTimeFromX(e.clientX));
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const t = getTimeFromX(e.clientX);
    setHoverTime(t);
    const seg = segments.find((s) => t >= s.start_sec && t < s.end_sec) ?? null;
    setHoverSegment(seg);
  };

  const cursorPct = totalDuration > 0 ? (currentTime / totalDuration) * 100 : 0;

  return (
    <div className="space-y-1">
      {/* Segment labels */}
      <div className="relative h-6 text-xs" ref={barRef}>
        {segments.map((seg) => {
          const left = (seg.start_sec / totalDuration) * 100;
          const width = ((seg.end_sec - seg.start_sec) / totalDuration) * 100;
          return (
            <div
              key={`${seg.task_name}-${seg.start_sec}`}
              className="absolute top-0 h-full flex items-center justify-center overflow-hidden text-white font-medium"
              style={{
                left: `${left}%`,
                width: `${width}%`,
                backgroundColor: seg.color || PARADIGM_COLORS[seg.task_type] || PARADIGM_COLORS.default,
                borderRadius: "4px",
              }}
            >
              {width > 5 && <span className="truncate px-1">{seg.task_name}</span>}
            </div>
          );
        })}
      </div>

      {/* Clickable track */}
      <div
        className="relative h-3 bg-muted rounded-full cursor-pointer group"
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => { setHoverTime(null); setHoverSegment(null); }}
      >
        {/* Filled progress */}
        <div className="absolute inset-y-0 left-0 rounded-full bg-primary/30" style={{ width: `${cursorPct}%` }} />

        {/* Cursor */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-primary shadow-md ring-2 ring-background transition-all"
          style={{ left: `calc(${cursorPct}% - 6px)` }}
        />

        {/* Hover tooltip */}
        {hoverTime !== null && (
          <div
            className="absolute -top-10 -translate-x-1/2 bg-popover border rounded-md px-2 py-1 text-xs shadow pointer-events-none whitespace-nowrap"
            style={{ left: `${(hoverTime / totalDuration) * 100}%` }}
          >
            {formatDuration(hoverTime)}
            {hoverSegment && <span className="ml-1 text-muted-foreground">· {hoverSegment.task_name}</span>}
          </div>
        )}
      </div>

      {/* Time labels */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{formatDuration(currentTime)}</span>
        <span className="text-primary font-medium">
          {hoverSegment ? `当前范式: ${hoverSegment.task_name}` : ""}
        </span>
        <span>{formatDuration(totalDuration)}</span>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useRef, useMemo } from "react";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import { GridComponent, DataZoomComponent, TooltipComponent, LegendComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { MODALITY_META, type Modality } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Maximize2, Minimize2 } from "lucide-react";
import { useState } from "react";
import Link from "next/link";

echarts.use([LineChart, GridComponent, DataZoomComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

interface WaveformPanelProps {
  modality: Modality;
  channels: string[];
  data: number[][];
  sampleRate: number;
  startSec: number;
  endSec: number;
  currentTime: number;
  sessionId: number;
  onTimeChange?: (time: number) => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

export function WaveformPanel({
  modality,
  channels,
  data,
  sampleRate,
  startSec,
  endSec,
  currentTime,
  sessionId,
  onTimeChange,
  collapsed = false,
  onToggleCollapse,
}: WaveformPanelProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const meta = MODALITY_META[modality];

  const timeAxis = useMemo(() => {
    if (!data[0]) return [];
    return Array.from({ length: data[0].length }, (_, i) => startSec + i / sampleRate);
  }, [data, sampleRate, startSec]);

  useEffect(() => {
    if (!chartRef.current || collapsed) return;

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, undefined, { renderer: "canvas" });
    }

    const chart = chartInstance.current;

    const series = channels.slice(0, 8).map((ch, idx) => ({
      name: ch,
      type: "line" as const,
      data: data[idx] ? timeAxis.map((t, i) => [t, data[idx][i]]) : [],
      showSymbol: false,
      lineStyle: { width: 1 },
      sampling: "lttb" as const,
    }));

    chart.setOption(
      {
        animation: false,
        grid: { left: 60, right: 16, top: 8, bottom: 40 },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "cross" },
          formatter: (params: any) => {
            if (!Array.isArray(params) || !params.length) return "";
            const t = params[0].data[0];
            onTimeChange?.(t);
            const lines = params.map((p: any) => `${p.seriesName}: ${p.data[1]?.toFixed(2)}`);
            return `${t.toFixed(2)}s<br/>${lines.join("<br/>")}`;
          },
        },
        xAxis: { type: "value", min: startSec, max: endSec, axisLabel: { formatter: (v: number) => `${v.toFixed(0)}s` } },
        yAxis: { type: "value", scale: true, splitLine: { lineStyle: { type: "dashed", opacity: 0.3 } } },
        dataZoom: [
          { type: "inside", xAxisIndex: 0 },
          { type: "slider", xAxisIndex: 0, height: 20, bottom: 4 },
        ],
        series,
      },
      true
    );

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, [channels, data, timeAxis, startSec, endSec, collapsed, sampleRate, onTimeChange]);

  useEffect(() => {
    return () => {
      chartInstance.current?.dispose();
    };
  }, []);

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-muted/30">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: meta.color }} />
          <span className="font-medium text-sm">{meta.label}</span>
          <span className="text-xs text-muted-foreground">{channels.length} 通道</span>
        </div>
        <div className="flex items-center gap-1">
          <Link href={`/dashboard/sessions/${sessionId}/${modality}`}>
            <Button variant="ghost" size="sm" className="text-xs h-7">
              详情
            </Button>
          </Link>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onToggleCollapse}>
            {collapsed ? <Maximize2 className="h-3.5 w-3.5" /> : <Minimize2 className="h-3.5 w-3.5" />}
          </Button>
        </div>
      </div>
      {!collapsed && <div ref={chartRef} className="w-full h-40" />}
    </div>
  );
}

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export const MODALITY_META = {
  eeg: { label: "EEG 脑电", color: "hsl(var(--chart-eeg))", icon: "Brain" },
  gsr: { label: "GSR 皮电", color: "hsl(var(--chart-gsr))", icon: "Heart" },
  emg: { label: "EMG 肌电", color: "hsl(var(--chart-emg))", icon: "Zap" },
  audio: { label: "音频", color: "hsl(var(--chart-audio))", icon: "AudioLines" },
  video: { label: "视频", color: "hsl(var(--chart-video))", icon: "Video" },
} as const;

export type Modality = keyof typeof MODALITY_META;

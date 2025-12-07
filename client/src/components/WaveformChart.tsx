import { useEffect, useRef } from "react";
import { useTheme } from "../contexts/ThemeContext";

interface WaveformChartProps {
  data: number[];
  color: string;
  title: string;
  label: string;
  maxPoints?: number;
}

export function WaveformChart({
  data,
  color,
  title,
  label,
  maxPoints = 60,
}: WaveformChartProps) {
  const { theme } = useTheme();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();
  const lastDataRef = useRef<number[]>([]);

  useEffect(() => {
    // Skip if data hasn't changed
    if (JSON.stringify(data) === JSON.stringify(lastDataRef.current)) {
      return;
    }
    lastDataRef.current = data;

    // Cancel previous frame if it exists
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    // Use requestAnimationFrame for smooth rendering
    animationFrameRef.current = requestAnimationFrame(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      const ctx = canvas.getContext("2d", { alpha: false });
      if (!ctx) return;

      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();

      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;

      ctx.scale(dpr, dpr);

      const w = rect.width;
      const h = rect.height;
      const marginLeft = 50;
      const marginBottom = 30;
      const plotW = w - marginLeft - 15;
      const plotH = h - marginBottom - 15;

      // Clear canvas - theme-aware colors
      const bgColor = theme === "light" ? "#f8fafc" : "#0f172a";
      const plotBgColor = theme === "light" ? "#ffffff" : "#1e293b";
      const gridColor = theme === "light" ? "#cbd5e1" : "#334155";
      const textColor = theme === "light" ? "#475569" : "#94a3b8";

      ctx.fillStyle = bgColor;
      ctx.fillRect(0, 0, w, h);

      ctx.fillStyle = plotBgColor;
      ctx.fillRect(marginLeft, 10, plotW, plotH);

      // Draw grid lines
      ctx.font = "11px system-ui, -apple-system, sans-serif";
      ctx.textAlign = "right";
      const ySteps = [0, 50, 100];

      ySteps.forEach((val) => {
        const y = 10 + plotH - (val / 100) * plotH;

        ctx.strokeStyle = gridColor;
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 3]);
        ctx.beginPath();
        ctx.moveTo(marginLeft, y);
        ctx.lineTo(marginLeft + plotW, y);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = textColor;
        ctx.fillText(val + "%", marginLeft - 8, y + 4);
      });

      ctx.textAlign = "center";
      ctx.fillStyle = textColor;
      ctx.font = "10px system-ui, -apple-system, sans-serif";
      ctx.fillText("Time (seconds)", marginLeft + plotW / 2, h - 8);

      if (data.length < 2) {
        ctx.fillStyle = textColor;
        ctx.font = "bold 12px system-ui, -apple-system, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(
          "Awaiting signal data...",
          marginLeft + plotW / 2,
          10 + plotH / 2
        );
        return;
      }

      const pointWidth = plotW / maxPoints;
      const startX = marginLeft + plotW - data.length * pointWidth;

      // Draw gradient fill
      const gradient = ctx.createLinearGradient(0, 10, 0, 10 + plotH);
      gradient.addColorStop(0, color + "30");
      gradient.addColorStop(1, color + "05");

      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.moveTo(startX, 10 + plotH);
      data.forEach((val, i) => {
        const x = startX + i * pointWidth;
        const y = 10 + plotH - (val / 100) * plotH;
        ctx.lineTo(x, y);
      });
      ctx.lineTo(startX + (data.length - 1) * pointWidth, 10 + plotH);
      ctx.closePath();
      ctx.fill();

      // Draw line
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      data.forEach((val, i) => {
        const x = startX + i * pointWidth;
        const y = 10 + plotH - (val / 100) * plotH;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Draw last point indicator
      const lastVal = data[data.length - 1];
      const lastX = startX + (data.length - 1) * pointWidth;
      const lastY = 10 + plotH - (lastVal / 100) * plotH;

      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(lastX, lastY, 5, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = theme === "light" ? "#1e293b" : "#f1f5f9";
      ctx.font = "bold 13px system-ui, -apple-system, sans-serif";
      ctx.textAlign = "left";
      const textX = Math.min(lastX + 10, w - 50);
      ctx.fillText(lastVal.toFixed(0) + "%", textX, lastY + 5);
    });

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [data, color, maxPoints, theme]);

  return (
    <div className="bg-white dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700/50 rounded-lg p-4 shadow-lg">
      <div className="flex items-center gap-3 mb-3">
        <h3 className="text-slate-900 dark:text-slate-200 font-semibold text-sm">
          {title}
        </h3>
        <span
          className={`text-xs px-2 py-1 rounded font-medium border ${
            label === "RAW"
              ? "bg-blue-500/20 dark:bg-blue-500/20 text-blue-600 dark:text-blue-300 border-blue-500/30 dark:border-blue-500/30"
              : "bg-pink-500/20 dark:bg-pink-500/20 text-pink-600 dark:text-pink-300 border-pink-500/30 dark:border-pink-500/30"
          }`}
        >
          {label}
        </span>
      </div>
      <div className="relative">
        <canvas
          ref={canvasRef}
          className="w-full rounded bg-slate-50 dark:bg-slate-900"
          style={{ height: "180px" }}
        />
      </div>
    </div>
  );
}

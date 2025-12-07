import { Activity, Radio, Cpu } from "lucide-react";

interface StatusBarProps {
  isConnected: boolean;
  isESP32Connected: boolean;
  lastUpdate: string;
}

export function StatusBar({
  isConnected,
  isESP32Connected,
  lastUpdate,
}: StatusBarProps) {
  return (
    <div className="bg-white dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700/50 rounded-lg px-6 py-3 shadow-lg">
      <div className="flex items-center justify-between flex-wrap gap-4 text-sm">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            {isConnected ? (
              <>
                <div className="w-2 h-2 bg-green-500 dark:bg-green-400 rounded-full animate-pulse shadow-lg shadow-green-500/40 dark:shadow-green-400/40" />
                <span className="text-green-600 dark:text-green-300 font-medium">
                  Dashboard Connected
                </span>
              </>
            ) : (
              <>
                <div className="w-2 h-2 bg-red-500 dark:bg-red-400 rounded-full" />
                <span className="text-red-600 dark:text-red-300 font-medium">
                  Dashboard Disconnected
                </span>
              </>
            )}
          </div>

          <div className="h-4 w-px bg-slate-300 dark:bg-slate-700" />

          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-green-500 dark:text-green-400" />
            {isESP32Connected ? (
              <>
                <div className="w-2 h-2 bg-green-500 dark:bg-green-400 rounded-full animate-pulse shadow-lg shadow-green-500/40 dark:shadow-green-400/40" />
                <span className="text-green-600 dark:text-green-300 font-medium">
                  ESP32 Connected
                </span>
              </>
            ) : (
              <>
                <div className="w-2 h-2 bg-red-500 dark:bg-red-400 rounded-full" />
                <span className="text-red-600 dark:text-red-300 font-medium">
                  ESP32 Disconnected
                </span>
              </>
            )}
          </div>

          <div className="h-4 w-px bg-slate-300 dark:bg-slate-700" />

          <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
            <Activity className="w-4 h-4" />
            <span className="font-medium text-slate-800 dark:text-slate-200">
              16 kHz
            </span>
            <span className="text-slate-500 dark:text-slate-500">
              Sample Rate
            </span>
          </div>

          <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
            <span className="font-medium text-slate-800 dark:text-slate-200">
              128
            </span>
            <span className="text-slate-500 dark:text-slate-500">
              FFT Samples
            </span>
          </div>

          <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
            <span className="font-medium text-slate-800 dark:text-slate-200">
              0-8 kHz
            </span>
            <span className="text-slate-500 dark:text-slate-500">Range</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Radio className="w-4 h-4 text-blue-500 dark:text-blue-400" />
          <span className="text-slate-600 dark:text-slate-400">
            Last update:
          </span>
          <span className="text-slate-800 dark:text-slate-200 font-medium">
            {lastUpdate}
          </span>
        </div>
      </div>
    </div>
  );
}

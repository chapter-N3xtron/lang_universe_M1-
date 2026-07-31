"use client";

import { useTheme } from "next-themes";
import { Moon, Sun, Monitor } from "lucide-react";
import { TooltipIconButton } from "@/components/thread/tooltip-icon-button";
import { useEffect, useState } from "react";

const THEMES = ["light", "dark", "system"] as const;
const THEME_ICONS = {
  light: Sun,
  dark: Moon,
  system: Monitor,
} as const;
const THEME_LABELS = {
  light: "Light mode",
  dark: "Dark mode",
  system: "System theme",
} as const;

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return <div className="size-6 p-1" />;
  }

  const currentTheme = theme ?? "system";
  const nextTheme =
    THEMES[
      (THEMES.indexOf(currentTheme as (typeof THEMES)[number]) + 1) %
        THEMES.length
    ];
  const Icon = THEME_ICONS[currentTheme as keyof typeof THEME_ICONS] ?? Monitor;

  return (
    <TooltipIconButton
      tooltip={THEME_LABELS[currentTheme as keyof typeof THEME_LABELS]}
      variant="ghost"
      onClick={() => setTheme(nextTheme)}
    >
      <Icon className="size-4" />
    </TooltipIconButton>
  );
}

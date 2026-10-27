"use client";

import { useEffect, useState } from "react";

type Theme = "dark" | "light";
const storageKey = "aria-interface-theme";

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(storageKey);
      const next: Theme = saved === "light" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      setTheme(next);
    } catch {
      document.documentElement.dataset.theme = "dark";
    }
  }, []);

  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    setTheme(next);
    try {
      window.localStorage.setItem(storageKey, next);
    } catch {
      // Keep the selected theme for this page even when storage is unavailable.
    }
  }

  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      aria-pressed={theme === "light"}
      onClick={toggleTheme}
    >
      <span aria-hidden="true">{theme === "dark" ? "◐" : "◑"}</span>
      <span>{theme === "dark" ? "Dark" : "Light"}</span>
    </button>
  );
}

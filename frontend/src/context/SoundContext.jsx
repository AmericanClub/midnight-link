import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";

const SoundContext = createContext({ enabled: true, toggle: () => {}, blip: () => {} });

// Arcade "blip" sound engine (Web Audio) + global click listener.
export function SoundProvider({ children }) {
  const [enabled, setEnabled] = useState(
    () => (localStorage.getItem("ml-sound") || "on") !== "off"
  );
  const ctxRef = useRef(null);
  const enabledRef = useRef(enabled);

  useEffect(() => {
    enabledRef.current = enabled;
    localStorage.setItem("ml-sound", enabled ? "on" : "off");
  }, [enabled]);

  const getCtx = useCallback(() => {
    if (!ctxRef.current) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (AC) ctxRef.current = new AC();
    }
    return ctxRef.current;
  }, []);

  const blip = useCallback(
    (freq = 620, dur = 0.055, type = "square") => {
      if (!enabledRef.current) return;
      const ctx = getCtx();
      if (!ctx) return;
      try {
        if (ctx.state === "suspended") ctx.resume();
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.type = type;
        o.frequency.setValueAtTime(freq, ctx.currentTime);
        o.frequency.exponentialRampToValueAtTime(freq * 1.35, ctx.currentTime + dur);
        g.gain.setValueAtTime(0.0001, ctx.currentTime);
        g.gain.exponentialRampToValueAtTime(0.05, ctx.currentTime + 0.006);
        g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + dur);
        o.connect(g);
        g.connect(ctx.destination);
        o.start();
        o.stop(ctx.currentTime + dur);
      } catch (e) {
        /* ignore audio errors */
      }
    },
    [getCtx]
  );

  // Global click listener — plays a subtle blip on interactive elements.
  useEffect(() => {
    const handler = (e) => {
      if (!enabledRef.current) return;
      const t = e.target;
      if (!t || !t.closest) return;
      const el = t.closest("button, [role='button'], a[data-testid], a[href]");
      if (!el || el.getAttribute("aria-disabled") === "true" || el.disabled) return;
      blip(600, 0.05);
    };
    document.addEventListener("click", handler, true);
    return () => document.removeEventListener("click", handler, true);
  }, [blip]);

  const toggle = useCallback(() => {
    setEnabled((v) => {
      const nv = !v;
      if (nv) {
        enabledRef.current = true;
        blip(760, 0.06);
      }
      return nv;
    });
  }, [blip]);

  return (
    <SoundContext.Provider value={{ enabled, toggle, blip }}>
      {children}
    </SoundContext.Provider>
  );
}

export const useSound = () => useContext(SoundContext);

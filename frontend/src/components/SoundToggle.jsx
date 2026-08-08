import React from "react";
import { Volume2, VolumeX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSound } from "@/context/SoundContext";

export default function SoundToggle() {
  const { enabled, toggle } = useSound();
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggle}
      data-testid="sound-toggle-btn"
      aria-label="Toggle arcade sound"
      title={enabled ? "Sound on" : "Sound off"}
    >
      {enabled ? <Volume2 className="h-5 w-5" /> : <VolumeX className="h-5 w-5" />}
    </Button>
  );
}

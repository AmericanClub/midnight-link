import * as React from "react"

import { cn } from "@/lib/utils"

const Textarea = React.forwardRef(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        "flex min-h-[70px] w-full rounded-[3px] border-[2.5px] border-[hsl(var(--nb-border))] bg-card px-3 py-2 text-base shadow-[2px_2px_0_0_hsl(var(--nb-shadow))] transition-shadow placeholder:text-muted-foreground focus-visible:outline-none focus-visible:shadow-[3px_3px_0_0_hsl(var(--ring))] focus-visible:border-[hsl(var(--ring))] disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
        className
      )}
      ref={ref}
      {...props} />
  );
})
Textarea.displayName = "Textarea"

export { Textarea }

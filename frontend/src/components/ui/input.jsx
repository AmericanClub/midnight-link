import * as React from "react"

import { cn } from "@/lib/utils"

const Input = React.forwardRef(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-[3px] border-[2.5px] border-[hsl(var(--nb-border))] bg-card px-3 py-1 text-base shadow-[2px_2px_0_0_hsl(var(--nb-shadow))] transition-shadow file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:shadow-[3px_3px_0_0_hsl(var(--ring))] focus-visible:border-[hsl(var(--ring))] disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
        className
      )}
      ref={ref}
      {...props} />
  );
})
Input.displayName = "Input"

export { Input }

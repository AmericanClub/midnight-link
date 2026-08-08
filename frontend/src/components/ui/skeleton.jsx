import { cn } from "@/lib/utils"

function Skeleton({
  className,
  ...props
}) {
  return (
    <div
      className={cn(
        "nb-skeleton rounded-[3px] border-2 border-[hsl(var(--nb-border)/0.35)] bg-muted",
        className
      )}
      {...props} />
  );
}

export { Skeleton }

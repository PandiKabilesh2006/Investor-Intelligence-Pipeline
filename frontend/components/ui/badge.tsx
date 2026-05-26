import { cn } from "@/lib/utils";

type BadgeProps = {
  children: React.ReactNode;
  className?: string;
};

export function Badge({ children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border border-border bg-accent px-2 py-1 text-xs font-medium text-accent-foreground",
        className
      )}
    >
      {children}
    </span>
  );
}

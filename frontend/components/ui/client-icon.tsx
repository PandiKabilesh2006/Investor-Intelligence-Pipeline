"use client";

import React, { useEffect, useState } from "react";
import { LucideIcon } from "lucide-react";

interface ClientIconProps {
  icon: LucideIcon;
  className?: string;
}

export function ClientIcon({ icon: Icon, className }: ClientIconProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    // Render a span with matching className to preserve layout flow during SSR
    return <span className={className} style={{ display: "inline-block", width: "1em", height: "1em" }} />;
  }

  return <Icon className={className} />;
}

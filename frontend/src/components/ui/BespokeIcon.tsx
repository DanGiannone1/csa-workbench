"use client";

import React from "react";
import { LucideIcon } from "lucide-react";

interface BespokeIconProps {
  icon: LucideIcon;
  size?: number;
  className?: string;
  strokeWidth?: number;
}

/**
 * Keeps product icon sizing and stroke weight consistent without visual effects.
 */
export default function BespokeIcon({
  icon: Icon,
  size = 18,
  className = "",
  strokeWidth = 2,
}: BespokeIconProps) {
  return (
    <span className={`inline-flex items-center justify-center ${className}`}>
      <Icon 
        size={size} 
        strokeWidth={strokeWidth} 
      />
    </span>
  );
}

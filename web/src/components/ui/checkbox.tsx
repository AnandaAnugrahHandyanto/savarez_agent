import { cn } from "@/lib/utils";
import React from "react";

type CheckedState = boolean | "indeterminate";

interface CheckboxProps
  extends Omit<
    React.InputHTMLAttributes<HTMLInputElement>,
    "checked" | "defaultChecked" | "onChange" | "type"
  > {
  checked?: CheckedState;
  defaultChecked?: CheckedState;
  onCheckedChange?: (checked: CheckedState) => void;
}

export function Checkbox({
  checked,
  className,
  defaultChecked,
  onCheckedChange,
  ...props
}: CheckboxProps) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const isIndeterminate = checked === "indeterminate";

  React.useEffect(() => {
    if (inputRef.current) {
      inputRef.current.indeterminate = isIndeterminate;
    }
  }, [isIndeterminate]);

  return (
    <input
      ref={inputRef}
      type="checkbox"
      checked={isIndeterminate ? false : checked}
      defaultChecked={defaultChecked === "indeterminate" ? false : defaultChecked}
      className={cn(
        "h-4 w-4 shrink-0 rounded border border-border bg-background accent-foreground",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-foreground/30",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      onChange={(event) => onCheckedChange?.(event.currentTarget.checked)}
      {...props}
    />
  );
}

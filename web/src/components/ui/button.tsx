import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

<<<<<<< HEAD
export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-mondwest text-xs tracking-[0.1em] uppercase transition-colors cursor-pointer"
=======
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap text-xs tracking-[0.1em]  transition-colors cursor-pointer"
>>>>>>> 0777bd2f (style(web): update dashboard font to system-ui stack)
  + " disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-foreground/90 text-background hover:bg-foreground",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-border bg-transparent hover:bg-foreground/10 hover:text-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-foreground/10 hover:text-foreground",
        link: "text-foreground underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3 text-[0.65rem]",
        lg: "h-10 px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export function Button({
  className,
  variant,
  size,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants>) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

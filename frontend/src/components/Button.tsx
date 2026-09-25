import type { ButtonHTMLAttributes } from "react";
export default function Button({
  variant = "secondary",
  className = "",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "quiet";
}) {
  return (
    <button
      type={type}
      className={`button ${variant} ${className}`}
      {...props}
    />
  );
}

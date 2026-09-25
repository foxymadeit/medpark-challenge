import { useId, type InputHTMLAttributes } from "react";
export default function InputField({
  label,
  id,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const generated = useId();
  return (
    <div className="form-field">
      <label htmlFor={id ?? generated}>{label}</label>
      <input id={id ?? generated} {...props} />
    </div>
  );
}

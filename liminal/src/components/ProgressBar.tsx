/** 4px progress track (Figma "Track 4px" / "Progress · iOS 4px"). */
export function ProgressBar({ value, label }: { value: number; label: string }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div className="progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
      <div className="progress__fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

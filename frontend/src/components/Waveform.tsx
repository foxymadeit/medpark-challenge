export default function Waveform({ levels, color }: { levels: number[]; color?: string }) {
  return (
    <div className="waveform" aria-hidden="true">
      {levels.map((height, i) => (
        <span key={i} style={{ height, ...(color ? { background: color } : {}) }} />
      ))}
    </div>
  );
}

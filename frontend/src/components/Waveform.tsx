export default function Waveform({ levels }: { levels: number[] }) {
  return (
    <div className="waveform" aria-hidden="true">
      {levels.map((height, i) => (
        <span key={i} style={{ height }} />
      ))}
    </div>
  );
}

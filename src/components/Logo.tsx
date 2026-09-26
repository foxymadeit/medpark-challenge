import logo from '../assets/logo-liminal.svg';

/** Liminal logo — asset exported from Figma component "Logo / Liminal" (2009:1592). */
export function Logo({ size = 25.55 }: { size?: number }) {
  return <img src={logo} width={size} height={size} alt="" className="logo" />;
}

/** Wordmark from Figma "Brand" (2009:1603): "Li·min·al" with the middle syllable bold and blue. */
export function Wordmark() {
  return (
    <span className="wordmark">
      Li<span className="wordmark__min">min</span>al
    </span>
  );
}

/** Renders a sentence with the product name in it as the wordmark (e.g. "Welcome to Liminal"). */
export function WithWordmark({ text }: { text: string }) {
  const i = text.indexOf('Liminal');
  if (i < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, i)}
      <Wordmark />
      {text.slice(i + 'Liminal'.length)}
    </>
  );
}

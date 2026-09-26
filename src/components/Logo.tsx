import logo from '../assets/logo-liminal.svg';

/** Liminal logo — asset exported from Figma component "Logo / Liminal" (2009:1592). */
export function Logo({ size = 25.55 }: { size?: number }) {
  return <img src={logo} width={size} height={size} alt="" className="logo" />;
}

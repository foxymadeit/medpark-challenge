import { Link } from "react-router-dom";

export default function LiminalLogo() {
  return (
    <Link className="liminal-logo" to="/meetings">
      <img
        src="/assets/liminal-logo.svg"
        alt="Liminal"
        width="47"
        height="28"
      />
    </Link>
  );
}

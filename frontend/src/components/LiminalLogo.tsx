import { Link } from "react-router-dom";

export default function LiminalLogo({
  publicOnly = false,
}: {
  publicOnly?: boolean;
}) {
  return (
    <Link className="liminal-logo" to={publicOnly ? "/login" : "/meetings"}>
      <img
        src="/assets/liminal-logo.svg"
        alt="Liminal"
        width="47"
        height="28"
      />
    </Link>
  );
}

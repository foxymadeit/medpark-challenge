import { Navigate, useParams } from "react-router-dom";

export default function LegacyRoute({ page }: { page: string }) {
  const { meetingId } = useParams();
  return <Navigate replace to={`/meetings/${meetingId}/${page}`} />;
}

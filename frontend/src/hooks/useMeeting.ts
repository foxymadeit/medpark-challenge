import { useCallback } from "react";
import { useParams } from "react-router-dom";
import { getMeeting } from "../api/meetings";
import { useData } from "./useData";
export function useMeeting() {
  const { id, meetingId } = useParams();
  const key = id ?? meetingId ?? "";
  return useData(useCallback(() => getMeeting(key), [key]));
}

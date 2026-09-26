import { getRouting } from "../api/routing";
import { useData } from "./useData";

/** Who each meeting type is sent to, read once from the server. */
export function useRouting() {
  return useData(getRouting, 0).data;
}

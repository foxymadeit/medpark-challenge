import { FiCheck } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { DEMO_MODE } from "../api/config";
import { listName } from "../api/routing";
import { useRouting } from "../hooks/useRouting";
import type { Meeting } from "../types/meeting";
import { formatClock } from "../utils";

/** "Sent to the Medical board, 12 recipients, at 19:08", with a check that
 * draws in once. On the minutes page it links to the delivery page. */
export default function DeliveryBanner({
  meeting,
  link = false,
}: {
  meeting: Meeting;
  link?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const routing = useRouting();
  const count = routing?.[meeting.type];
  const list = listName(meeting.type, t);
  const time = meeting.sentAt ? formatClock(meeting.sentAt, i18n.language) : "";
  const detail = count
    ? t("sentToCount", { list, count, time })
    : t("sentTo", { list, time });
  const body = (
    <>
      <FiCheck size={28} className="success success-check" aria-hidden />
      <div>
        <h2>{t("deliveryConfirmed")}</h2>
        <p>{detail}</p>
        {DEMO_MODE && <p>{t("demoDelivery")}</p>}
      </div>
    </>
  );
  return link ? (
    <Link className="panel delivery-banner" to={`/meetings/${meeting.id}/sent`}>
      {body}
    </Link>
  ) : (
    <section className="panel delivery-banner" role="status">
      {body}
    </section>
  );
}

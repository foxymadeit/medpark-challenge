import { useEffect } from "react";
import { DEMO_MODE } from "../api/config";
import { getMeetings } from "../api/meetings";
import { Outlet, useLocation } from "react-router-dom";
import TopBar from "./TopBar";
import MobileTabBar from "./MobileTabBar";
export default function Layout() {
  useEffect(() => {
    if (!DEMO_MODE) return;
    // Reconcile persisted deadlines even while another page is open.
    const timer = setInterval(() => {
      void getMeetings().catch(() => {});
    }, 1000);
    return () => clearInterval(timer);
  }, []);
  const { pathname } = useLocation();
  // On a phone the bottom bar is the only way between sections, so it is
  // on every page except the two where a person is speaking into the mic.
  const tabs = !/\/(record|enroll)$/.test(pathname);
  return (
    <>
      <TopBar />
      <main className={`page-container ${tabs ? "with-tabs" : ""}`}>
        <div key={pathname} className="page-enter">
          <Outlet />
        </div>
      </main>
      {tabs && <MobileTabBar />}
    </>
  );
}

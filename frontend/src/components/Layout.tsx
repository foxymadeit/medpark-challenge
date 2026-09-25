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
  const tabs = [
    "/meetings",
    "/action-items",
    "/history",
    "/people",
    "/system",
  ].includes(pathname);
  return (
    <>
      <TopBar />
      <main className={`page-container ${tabs ? "with-tabs" : ""}`}>
        <Outlet />
      </main>
      {tabs && <MobileTabBar />}
    </>
  );
}

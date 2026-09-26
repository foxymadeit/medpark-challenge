import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import {
  DEMO_SESSION_KEY,
  restoreDemoAccount,
  saveDemoSession,
} from "../src/auth/demoSession";
import { AuthContext } from "../src/auth/useAuth";
import AdminRoute from "../src/auth/AdminRoute";
import { getPeople } from "../src/api/meetings";
import { saveStaffProfile } from "../src/api/admin";
import { readStore, writeStore } from "../src/mock/store";
import i18n from "../src/i18n/i18n";
describe("account separation and translations", () => {
  it("discards legacy and malformed sessions and never restores participant identity", () => {
    sessionStorage.setItem(
      "secure-mom-demo-auth",
      JSON.stringify({ name: "Elena Ciobanu" }),
    );
    expect(restoreDemoAccount()).toBeNull();
    expect(sessionStorage.getItem("secure-mom-demo-auth")).toBeNull();
    sessionStorage.setItem(DEMO_SESSION_KEY, "broken");
    expect(restoreDemoAccount()).toBeNull();
    saveDemoSession();
    const stale = JSON.parse(sessionStorage.getItem(DEMO_SESSION_KEY)!);
    sessionStorage.setItem(
      DEMO_SESSION_KEY,
      JSON.stringify({ ...stale, name: "Elena Ciobanu", initials: "EC" }),
    );
    expect(restoreDemoAccount()).toMatchObject({
      name: "Administrator",
      initials: "AD",
      role: "admin",
    });
  });
  it("keeps participant edits and legacy seed emails separate from the account", async () => {
    saveDemoSession();
    const before = restoreDemoAccount();
    const store = readStore();
    store.people.find((p) => p.id === "elena")!.email = "admin@medpark.local";
    writeStore(store);
    await saveStaffProfile(
      { name: "Another participant", email: "another@medpark.local" },
      "admin",
    );
    expect((await getPeople()).find((p) => p.id === "elena")?.email).not.toBe(
      before?.email,
    );
    expect(restoreDemoAccount()).toEqual(before);
  });
  it("redirects non-admin accounts away from System", async () => {
    render(
      <AuthContext.Provider
        value={{
          user: {
            id: "staff",
            name: "Staff",
            email: "staff@medpark.local",
            role: "staff",
          },
          loading: false,
          error: "",
          login: vi.fn(),
          logout: vi.fn(),
        }}
      >
        <MemoryRouter initialEntries={["/system"]}>
          <Routes>
            <Route element={<AdminRoute />}>
              <Route path="/system" element={<h1>Restricted</h1>} />
            </Route>
            <Route path="/meetings" element={<h1>Meetings allowed</h1>} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>,
    );
    expect(await screen.findByText("Meetings allowed")).toBeTruthy();
    expect(screen.queryByText("Restricted")).toBeNull();
  });
  it("provides every interface key in EN, RO and RU", () => {
    const en = i18n.getResourceBundle("en", "translation");
    for (const language of ["ro", "ru"]) {
      const bundle = i18n.getResourceBundle(language, "translation");
      expect(Object.keys(bundle).sort()).toEqual(Object.keys(en).sort());
      for (const value of Object.values(bundle))
        expect(typeof value === "string" && value.length > 0).toBe(true);
    }
  });
});

import { useCallback, useState, type FormEvent } from "react";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/useAuth";
import {
  assignStaffRole,
  getAdminData,
  saveAccount,
  saveStaffProfile,
  setAccountActive,
  setDistributionListActive,
  setStaffActive,
} from "../api/admin";
import { useData, notifyUpdate } from "../hooks/useData";
import StatePanel from "../components/StatePanel";
import Button from "../components/Button";

type Section = "overview" | "users" | "people" | "roles" | "lists";

export default function AdminPage({
  section = "overview",
}: {
  section?: Section;
}) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { data, error, refresh } = useData(
    useCallback(() => getAdminData(), []),
  );
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  if (!data) return <StatePanel error={error} retry={refresh} />;

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setActionError("");
    try {
      await action();
      notifyUpdate();
      await refresh();
    } catch (reason) {
      setActionError(
        reason instanceof Error ? reason.message : "requestFailed",
      );
    } finally {
      setBusy(false);
    }
  }

  const nav = (
    <nav className="admin-nav" aria-label={t("adminArea")}>
      {["overview", "users", "people", "roles", "lists"].map((item) => (
        <NavLink
          key={item}
          end={item === "overview"}
          to={item === "overview" ? "/admin" : `/admin/${item}`}
        >
          {t(
            item === "overview"
              ? "overview"
              : item === "lists"
                ? "distributionLists"
                : item,
          )}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">{t("adminArea")}</p>
          <h1>
            {t(
              section === "overview"
                ? "administration"
                : section === "lists"
                  ? "distributionLists"
                  : section,
            )}
          </h1>
        </div>
      </header>
      {nav}
      {section === "overview" && (
        <div className="admin-summary-grid">
          <AdminSummary
            label={t("users")}
            value={data.accounts.length}
            to="/admin/users"
          />
          <AdminSummary
            label={t("people")}
            value={data.staffProfiles.length}
            to="/admin/people"
          />
          <AdminSummary
            label={t("roles")}
            value={data.staffRoles.length}
            to="/admin/roles"
          />
          <AdminSummary
            label={t("distributionLists")}
            value={data.distributionLists.length}
            to="/admin/lists"
          />
        </div>
      )}
      {section === "users" && (
        <UsersPanel data={data} busy={busy} run={run} role={user!.role} t={t} />
      )}
      {section === "people" && (
        <PeoplePanel
          data={data}
          busy={busy}
          run={run}
          role={user!.role}
          t={t}
        />
      )}
      {section === "roles" && (
        <RolesPanel data={data} busy={busy} run={run} role={user!.role} t={t} />
      )}
      {section === "lists" && (
        <section className="panel admin-table-list">
          {data.distributionLists.map((list) => (
            <div className="admin-row" key={list.id}>
              <div>
                <strong>{list.name}</strong>
                <p>{list.email}</p>
              </div>
              <Button
                disabled={busy}
                onClick={() =>
                  void run(() =>
                    setDistributionListActive(
                      list.id,
                      !list.active,
                      user!.role,
                    ),
                  )
                }
              >
                {t(list.active ? "deactivate" : "activate")}
              </Button>
            </div>
          ))}
        </section>
      )}
      {actionError && (
        <p className="error" role="alert">
          {t(actionError, { defaultValue: t("requestFailed") })}
        </p>
      )}
    </>
  );
}

function AdminSummary({
  label,
  value,
  to,
}: {
  label: string;
  value: number;
  to: string;
}) {
  return (
    <NavLink className="panel admin-summary" to={to}>
      <strong>{value}</strong>
      <span>{label}</span>
    </NavLink>
  );
}

type PanelProps = {
  data: Awaited<ReturnType<typeof getAdminData>>;
  busy: boolean;
  run: (action: () => Promise<unknown>) => Promise<void>;
  role: "admin" | "staff";
  t: ReturnType<typeof useTranslation>["t"];
};

function UsersPanel({ data, busy, run, role, t }: PanelProps) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    void run(() =>
      saveAccount(
        {
          username: String(form.get("username")),
          email: String(form.get("email")),
          role: String(form.get("role")) as "admin" | "staff",
          staffProfileId: String(form.get("staffProfileId")) || undefined,
        },
        role,
      ),
    );
    event.currentTarget.reset();
  };
  return (
    <div className="admin-layout">
      <form className="panel admin-form" onSubmit={submit}>
        <h2>{t("createAccount")}</h2>
        <label>
          {t("username")}
          <input name="username" required />
        </label>
        <label>
          {t("email")}
          <input name="email" type="email" />
        </label>
        <label>
          {t("role")}
          <select name="role">
            <option value="staff">{t("staff")}</option>
            <option value="admin">{t("admin")}</option>
          </select>
        </label>
        <label>
          {t("person")}
          <select name="staffProfileId">
            <option value="">—</option>
            {data.staffProfiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name}
              </option>
            ))}
          </select>
        </label>
        <Button variant="primary" disabled={busy} type="submit">
          {t("create")}
        </Button>
      </form>
      <section className="panel admin-table-list">
        {data.accounts.map((account) => (
          <div className="admin-row" key={account.id}>
            <div>
              <strong>{account.username}</strong>
              <p>
                {t(account.role)} · {t(account.active ? "active" : "inactive")}
              </p>
            </div>
            <Button
              disabled={busy || account.id === "demo-admin"}
              onClick={() =>
                void run(() =>
                  setAccountActive(account.id, !account.active, role),
                )
              }
            >
              {t(account.active ? "deactivate" : "activate")}
            </Button>
          </div>
        ))}
      </section>
    </div>
  );
}

function PeoplePanel({ data, busy, run, role, t }: PanelProps) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    void run(() =>
      saveStaffProfile(
        { name: String(form.get("name")), email: String(form.get("email")) },
        role,
      ),
    );
    event.currentTarget.reset();
  };
  return (
    <div className="admin-layout">
      <form className="panel admin-form" onSubmit={submit}>
        <h2>{t("createPerson")}</h2>
        <label>
          {t("name")}
          <input name="name" required />
        </label>
        <label>
          {t("email")}
          <input name="email" type="email" required />
        </label>
        <Button variant="primary" disabled={busy} type="submit">
          {t("create")}
        </Button>
      </form>
      <section className="panel admin-table-list">
        {data.staffProfiles.map((profile) => (
          <div className="admin-row" key={profile.id}>
            <div>
              <strong>{profile.name}</strong>
              <p>
                {profile.email} · {t(profile.active ? "active" : "inactive")}
              </p>
            </div>
            <Button
              disabled={busy}
              onClick={() =>
                void run(() =>
                  setStaffActive(profile.id, !profile.active, role),
                )
              }
            >
              {t(profile.active ? "deactivate" : "activate")}
            </Button>
          </div>
        ))}
      </section>
    </div>
  );
}

function RolesPanel({ data, busy, run, role, t }: PanelProps) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    void run(() =>
      assignStaffRole(
        {
          staffId: String(form.get("staffId")),
          title: String(form.get("title")),
          department: String(form.get("department")),
          validFrom: String(form.get("validFrom")),
        },
        role,
      ),
    );
    event.currentTarget.reset();
  };
  return (
    <div className="admin-layout">
      <form className="panel admin-form" onSubmit={submit}>
        <h2>{t("assignRole")}</h2>
        <label>
          {t("person")}
          <select name="staffId" required>
            {data.staffProfiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("roleTitle")}
          <input name="title" required />
        </label>
        <label>
          {t("department")}
          <input name="department" required />
        </label>
        <label>
          {t("validFrom")}
          <input name="validFrom" type="date" required />
        </label>
        <Button variant="primary" disabled={busy} type="submit">
          {t("save")}
        </Button>
      </form>
      <section className="panel admin-table-list">
        {data.staffRoles
          .slice()
          .reverse()
          .map((assignment) => (
            <div className="admin-row" key={assignment.id}>
              <div>
                <strong>
                  {
                    data.staffProfiles.find(
                      (profile) => profile.id === assignment.staffId,
                    )?.name
                  }
                </strong>
                <p>
                  {assignment.title} · {assignment.department}
                </p>
              </div>
              <span>
                {assignment.validFrom} — {assignment.validTo ?? t("current")}
              </span>
            </div>
          ))}
      </section>
    </div>
  );
}

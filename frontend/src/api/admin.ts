import { DEMO_MODE } from "./config";
import { ApiError, request } from "./client";
import { mutate, readStore } from "../mock/store";
import type {
  AccountRole,
  DistributionList,
  StaffProfile,
  StaffRoleAssignment,
  UserAccount,
} from "../types/meeting";

function requireAdmin(role: AccountRole) {
  if (role !== "admin") throw new ApiError("permissionDenied");
}

export async function getAdminData() {
  if (!DEMO_MODE)
    return request<{
      accounts: UserAccount[];
      staffProfiles: StaffProfile[];
      staffRoles: StaffRoleAssignment[];
      distributionLists: DistributionList[];
    }>("/admin");
  const store = readStore();
  return {
    accounts: store.accounts,
    staffProfiles: store.staffProfiles,
    staffRoles: store.staffRoles,
    distributionLists: store.distributionLists,
  };
}

export async function saveAccount(
  input: Pick<UserAccount, "username" | "email" | "role" | "staffProfileId">,
  actorRole: AccountRole,
) {
  requireAdmin(actorRole);
  if (!input.username.trim()) throw new ApiError("required");
  if (!DEMO_MODE)
    return request<UserAccount>("/admin/users", {
      method: "POST",
      body: JSON.stringify(input),
    });
  return mutate((store) => {
    if (
      store.accounts.some(
        (account) => account.username === input.username.trim(),
      )
    )
      throw new ApiError("duplicateAccount");
    const account: UserAccount = {
      ...input,
      id: crypto.randomUUID(),
      username: input.username.trim(),
      active: true,
      createdAt: new Date().toISOString(),
      createdBy: "demo-admin",
    };
    store.accounts.push(account);
    return account;
  });
}

export async function setAccountActive(
  id: string,
  active: boolean,
  actorRole: AccountRole,
) {
  requireAdmin(actorRole);
  if (!DEMO_MODE)
    return request<UserAccount>(`/admin/users/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ active }),
    });
  return mutate((store) => {
    const account = store.accounts.find((item) => item.id === id);
    if (!account) throw new ApiError("notFound");
    account.active = active;
    return account;
  });
}

export async function saveStaffProfile(
  input: Pick<StaffProfile, "name" | "email"> & { id?: string },
  actorRole: AccountRole,
) {
  requireAdmin(actorRole);
  if (!input.name.trim() || !input.email.trim()) throw new ApiError("required");
  if (!DEMO_MODE)
    return request<StaffProfile>(
      input.id
        ? `/admin/people/${encodeURIComponent(input.id)}`
        : "/admin/people",
      {
        method: input.id ? "PATCH" : "POST",
        body: JSON.stringify(input),
      },
    );
  return mutate((store) => {
    const existing = input.id
      ? store.staffProfiles.find((item) => item.id === input.id)
      : undefined;
    if (input.id && !existing) throw new ApiError("notFound");
    const value: StaffProfile = existing ?? {
      id: crypto.randomUUID(),
      name: "",
      email: "",
      active: true,
      createdAt: new Date().toISOString(),
      createdBy: "demo-admin",
    };
    value.name = input.name.trim();
    value.email = input.email.trim();
    if (!existing) store.staffProfiles.push(value);
    const legacy = store.people.find((person) => person.id === value.id);
    if (legacy) Object.assign(legacy, { name: value.name, email: value.email });
    else
      store.people.push({
        id: value.id,
        name: value.name,
        email: value.email,
        active: true,
      });
    return value;
  });
}

export async function setStaffActive(
  id: string,
  active: boolean,
  actorRole: AccountRole,
) {
  requireAdmin(actorRole);
  if (!DEMO_MODE)
    return request<StaffProfile>(`/admin/people/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ active }),
    });
  return mutate((store) => {
    const profile = store.staffProfiles.find((item) => item.id === id);
    if (!profile) throw new ApiError("notFound");
    profile.active = active;
    const person = store.people.find((item) => item.id === id);
    if (person) person.active = active;
    return profile;
  });
}

export async function assignStaffRole(
  input: Pick<
    StaffRoleAssignment,
    "staffId" | "title" | "department" | "validFrom"
  >,
  actorRole: AccountRole,
) {
  requireAdmin(actorRole);
  if (!input.title.trim() || !input.validFrom) throw new ApiError("required");
  if (!DEMO_MODE)
    return request<StaffRoleAssignment>(
      `/admin/people/${encodeURIComponent(input.staffId)}/roles`,
      {
        method: "POST",
        body: JSON.stringify(input),
      },
    );
  return mutate((store) => {
    if (!store.staffProfiles.some((profile) => profile.id === input.staffId))
      throw new ApiError("notFound");
    for (const role of store.staffRoles.filter(
      (role) => role.staffId === input.staffId && role.validTo === null,
    ))
      role.validTo = input.validFrom;
    const role: StaffRoleAssignment = {
      ...input,
      id: crypto.randomUUID(),
      title: input.title.trim(),
      validTo: null,
      createdBy: "demo-admin",
    };
    store.staffRoles.push(role);
    const person = store.people.find((item) => item.id === input.staffId);
    if (person) person.role = role.title;
    return role;
  });
}

export async function setDistributionListActive(
  id: string,
  active: boolean,
  actorRole: AccountRole,
) {
  requireAdmin(actorRole);
  if (!DEMO_MODE)
    return request<DistributionList>(`/admin/lists/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ active }),
    });
  return mutate((store) => {
    const list = store.distributionLists.find((item) => item.id === id);
    if (!list) throw new ApiError("notFound");
    list.active = active;
    return list;
  });
}

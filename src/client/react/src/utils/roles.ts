/**
 * roles.ts
 * Account roles from the allowlist: "researcher" (full access) and "teacher" (teacher dashboard).
 */

import type { User } from "../contexts/AuthContext";

/** Whether the signed-in user has a role. Users from before roles existed count as researchers. */
export const hasRole = (
  user: User | null,
  role: "researcher" | "teacher",
): boolean => {
  if (!user) return false;
  return (user.roles ?? ["researcher"]).includes(role);
};

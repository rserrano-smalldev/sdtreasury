import { api, setToken } from "./api";

/** If we arrived from Odoo (/sso/odoo#token=...), exchange the token for a session. */
export async function consumeOdooLogin(): Promise<boolean> {
  if (window.location.pathname !== "/sso/odoo") return false;
  const token = new URLSearchParams(window.location.hash.slice(1)).get("token");
  // Drop the token from the address bar and history straight away.
  window.history.replaceState(null, "", "/");
  if (!token) return false;
  const { access_token } = await api<{ access_token: string }>("/auth/odoo-sso", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
  setToken(access_token);
  return true;
}

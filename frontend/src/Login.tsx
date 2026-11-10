import { useState } from "react";
import { api, setToken } from "./api";

// Development login. Production uses Cognito (and SSO from Odoo).
export function Login({ onLogin }: { onLogin: () => void }) {
  const [slug, setSlug] = useState("smalldev");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const { access_token } = await api<{ access_token: string }>("/auth/dev-token", {
        method: "POST",
        body: JSON.stringify({ tenant_slug: slug, roles: ["admin"] }),
      });
      setToken(access_token);
      onLogin();
    } catch {
      setError("No se ha podido iniciar sesión. ¿Existe el tenant?");
    }
  }

  return (
    <form className="card login" onSubmit={submit}>
      <h1>SD Treasury</h1>
      <label>
        Tenant
        <input value={slug} onChange={(e) => setSlug(e.target.value)} />
      </label>
      <button type="submit">Entrar (desarrollo)</button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}

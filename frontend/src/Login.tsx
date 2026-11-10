import { useState } from "react";
import { api, setToken } from "./api";

const DEV_LOGIN = import.meta.env.DEV || import.meta.env.VITE_DEV_LOGIN === "true";

export function Login({ onLogin, failed }: { onLogin: () => void; failed?: boolean }) {
  const [slug, setSlug] = useState("demo");
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
    <div className="card login">
      <h1>SD Treasury</h1>
      {failed && (
        <p className="error">No se ha podido entrar desde Odoo. Vuelve a abrir Tesorería en Odoo.</p>
      )}
      <p>
        Entra desde tu Odoo: <strong>Contabilidad → Tesorería</strong>.
      </p>
      {DEV_LOGIN && (
        <form onSubmit={submit} className="login-form">
          <label>
            Tenant (solo desarrollo)
            <input value={slug} onChange={(e) => setSlug(e.target.value)} />
          </label>
          <button type="submit">Entrar (desarrollo)</button>
          {error && <p className="error">{error}</p>}
        </form>
      )}
    </div>
  );
}

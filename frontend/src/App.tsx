import { useEffect, useState } from "react";
import { getToken, setToken } from "./api";
import { Login } from "./Login";
import { PositionView } from "./PositionView";
import { consumeOdooLogin } from "./sso";

type State = "checking" | "anonymous" | "ready" | "sso_failed";

export function App() {
  const [state, setState] = useState<State>("checking");

  useEffect(() => {
    consumeOdooLogin()
      .then(() => setState(getToken() ? "ready" : "anonymous"))
      .catch(() => setState("sso_failed"));
  }, []);

  if (state === "checking") return <p className="center muted">Entrando…</p>;
  if (state !== "ready")
    return (
      <Login
        failed={state === "sso_failed"}
        onLogin={() => setState("ready")}
      />
    );
  return (
    <div className="layout">
      <header>
        <strong>SD Treasury</strong>
        <button
          className="link"
          onClick={() => {
            setToken(null);
            setState("anonymous");
          }}
        >
          Salir
        </button>
      </header>
      <main>
        <PositionView />
      </main>
    </div>
  );
}

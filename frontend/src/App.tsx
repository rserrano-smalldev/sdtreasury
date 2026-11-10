import { useState } from "react";
import { getToken, setToken } from "./api";
import { Login } from "./Login";
import { PositionView } from "./PositionView";

export function App() {
  const [loggedIn, setLoggedIn] = useState(Boolean(getToken()));

  if (!loggedIn) return <Login onLogin={() => setLoggedIn(true)} />;
  return (
    <div className="layout">
      <header>
        <strong>SD Treasury</strong>
        <button
          className="link"
          onClick={() => {
            setToken(null);
            setLoggedIn(false);
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

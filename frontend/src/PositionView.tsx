import { useQuery } from "@tanstack/react-query";
import { api, Company, Position } from "./api";
import { dateTime, money } from "./format";

export function PositionView() {
  const companies = useQuery({ queryKey: ["companies"], queryFn: () => api<Company[]>("/companies") });
  const position = useQuery({ queryKey: ["position"], queryFn: () => api<Position>("/position") });

  if (position.isLoading || companies.isLoading) return <p>Cargando…</p>;
  if (position.error) return <p className="error">Error al cargar la posición de caja.</p>;

  const data = position.data!;
  const companyName = new Map((companies.data ?? []).map((c) => [c.id, c.name]));
  const locked = (companies.data ?? []).filter((c) => !c.modules.includes("liquidity"));

  return (
    <section>
      <h2>Posición de caja</h2>
      <p className="muted">Saldos a {dateTime(data.as_of)}</p>

      <div className="kpis">
        {data.totals.map((t) => (
          <div className="card kpi" key={t.currency}>
            <span className="muted">Saldo bancario</span>
            <strong>{money(t.balance, t.currency)}</strong>
            <span className="muted">
              Cobros pendientes {money(t.receivables, t.currency)} · Pagos pendientes{" "}
              {money(t.payables, t.currency)}
            </span>
          </div>
        ))}
      </div>

      <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Cuenta</th>
            <th>Sociedad</th>
            <th>IBAN</th>
            <th>Origen</th>
            <th className="num">Saldo</th>
          </tr>
        </thead>
        <tbody>
          {data.accounts.map((a) => (
            <tr key={a.id}>
              <td>{a.name}</td>
              <td>{companyName.get(a.company_id)}</td>
              <td>{a.iban ?? "—"}</td>
              <td>{a.sync_source === "online_sync" ? "Sincronización bancaria" : "Manual"}</td>
              <td className={`num ${Number(a.balance) < 0 ? "neg" : ""}`}>
                {money(a.balance, a.currency)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>

      {locked.length > 0 && (
        <p className="muted">
          Sin módulo Liquidez: {locked.map((c) => c.name).join(", ")}. Contacta con SmallDev para
          activarlo.
        </p>
      )}
    </section>
  );
}

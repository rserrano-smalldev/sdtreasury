export function money(value: string | number, currency = "EUR"): string {
  return new Intl.NumberFormat("es-ES", { style: "currency", currency }).format(Number(value));
}

export function dateTime(value: string | null): string {
  return value ? new Date(value).toLocaleString("es-ES") : "—";
}

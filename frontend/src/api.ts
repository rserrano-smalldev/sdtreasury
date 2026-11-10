const TOKEN_KEY = "sdt_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: session lasts until reload */
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!res.ok) {
    if (res.status === 401 && token) {
      // Session expired: back to the login screen.
      setToken(null);
      window.location.reload();
    }
    throw new ApiError(res.status, await res.text());
  }
  return res.json() as Promise<T>;
}

export interface BankAccount {
  id: string;
  company_id: string;
  name: string;
  iban: string | null;
  bank_name: string | null;
  currency: string;
  sync_source: string | null;
  balance: string;
  balance_at: string | null;
}

export interface Position {
  as_of: string | null;
  totals: { currency: string; balance: string; receivables: string; payables: string }[];
  accounts: BankAccount[];
}

export interface Company {
  id: string;
  name: string;
  currency: string;
  modules: string[];
}

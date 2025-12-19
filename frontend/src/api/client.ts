import Cookies from "js-cookie";
import type {
  TokenResponse,
  UserProfile,
  Prediction,
  PredictionEnqueueResponse,
  Transaction
} from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";
const AUTH_COOKIE_KEY = "auth_token";

function parseApiErrorMessage(text: string): string {
  // FastAPI чаще всего возвращает: {"detail": "..."} (или detail может быть массивом/объектом)
  const trimmed = (text ?? "").trim();
  if (!trimmed) return "";

  try {
    const obj = JSON.parse(trimmed);
    const detail = (obj as any)?.detail;

    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (typeof first === "string") return first;
      // Pydantic errors: [{loc, msg, type}]
      if (first && typeof first === "object" && "msg" in first) return String((first as any).msg);
      return JSON.stringify(first);
    }
    if (detail && typeof detail === "object") return JSON.stringify(detail);
  } catch {
    // не JSON — вернём как есть
  }

  return trimmed;
}

function mapToFriendlyMessage(message: string): string {
  // Недостаточный баланс для генерации
  if (message.includes("Not enough credits")) {
    return "Недостаточно средств. Для генерации пополните баланс";
  }
  // На будущее: если бэкенд начнёт отдавать русское сообщение
  if (message.toLowerCase().includes("недостаточно") && message.toLowerCase().includes("кредит")) {
    return "Недостаточно средств. Для генерации пополните баланс";
  }
  return message;
}

async function getFriendlyError(res: Response): Promise<string> {
  const raw = await res.text();
  const parsed = parseApiErrorMessage(raw);
  const msg = parsed || `HTTP error ${res.status}`;
  return mapToFriendlyMessage(msg);
}


export function getAuthToken(): string | undefined {
  return Cookies.get(AUTH_COOKIE_KEY);
}

export function setAuthToken(token: string | undefined) {
  if (!token) {
    Cookies.remove(AUTH_COOKIE_KEY);
    return;
  }
  Cookies.set(AUTH_COOKIE_KEY, token, {
    path: "/",
    sameSite: "lax"
    // secure: true — включить для https
  });
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  useAuth = true
): Promise<T> {
  const baseHeaders: Record<string, string> = {
    "Content-Type": "application/json"
  };

  if (options.headers) {
    if (options.headers instanceof Headers) {
      for (const [key, value] of options.headers.entries()) {
        baseHeaders[key] = value;
      }
    } else if (Array.isArray(options.headers)) {
      for (const [key, value] of options.headers) {
        baseHeaders[key] = value;
      }
    } else {
      Object.assign(baseHeaders, options.headers as Record<string, string>);
    }
  }

  if (useAuth) {
    const token = getAuthToken();
    if (token) {
      baseHeaders["Authorization"] = `Bearer ${token}`;
    }
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",   // <--- важно для HttpOnly-куки
    ...options,
    headers: baseHeaders
  });

  if (!res.ok) {
    throw new Error(await getFriendlyError(res));
  }

  return res.json() as Promise<T>;
}

/* AUTH */

export async function login(email: string, password: string): Promise<TokenResponse> {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);

  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body,
    credentials: "include"   // <--- чтобы кука access_token сохранилась
  });

  if (!res.ok) {
    throw new Error(await getFriendlyError(res));
  }

  return res.json() as Promise<TokenResponse>;
}

export async function register(email: string, password: string): Promise<void> {
  await request<void>(
    "/auth/register",
    {
      method: "POST",
      body: JSON.stringify({ email, password })
    },
    false
  );
}

export async function getMeProfile(): Promise<UserProfile> {
  return request<UserProfile>("/me/profile");
}

/* BALANCE & TRANSACTIONS */

export async function getMyBalance(): Promise<{ balance_credits: number }> {
  return request<{ balance_credits: number }>("/me/balance");
}

export async function depositMyBalance(
  amount: number,
  description?: string
): Promise<{ balance_credits: number }> {
  return request("/me/balance/deposit", {
    method: "POST",
    body: JSON.stringify({ amount, description })
  });
}

export async function getMyTransactions(): Promise<Transaction[]> {
  return request("/me/transactions");
}

/* PREDICTIONS */

export async function enqueuePrediction(
  prompt: string,
  modelId?: number
): Promise<PredictionEnqueueResponse> {
  return request("/predictions", {
    method: "POST",
    body: JSON.stringify({ prompt, model_id: modelId ?? null })
  });
}

export async function getMyPredictions(): Promise<Prediction[]> {
  return request("/predictions");
}

export async function getDemoPrediction(taskId: string): Promise<Prediction> {
  return request<Prediction>(`/predictions/demo/${taskId}`, {}, false);
}

export async function claimDemoPrediction(
  taskId: string
): Promise<{ message: string }> {
  return request<{ message: string }>("/predictions/demo/claim", {
    method: "POST",
    body: JSON.stringify({ task_id: taskId })
  });
}

/* ADMIN */

export async function adminGetUsers(): Promise<UserProfile[]> {
  return request("/admin/users");
}

export async function adminChangeUserBalance(params: {
  user_id: number;
  amount: number;
  description?: string;
}): Promise<UserProfile> {
  return request("/admin/users/balance", {
    method: "POST",
    body: JSON.stringify(params)
  });
}

export async function adminGetTransactions(): Promise<Transaction[]> {
  return request("/admin/transactions");
}

export async function adminGetPredictions(): Promise<Prediction[]> {
  return request("/admin/predictions");
}

export async function adminDeleteUser(userId: number): Promise<{ deleted_user_id: number; message: string }> {
  return request<{ deleted_user_id: number; message: string }>(`/admin/users/${userId}`, {
    method: "DELETE",
  });
}


/* IMAGES DOWNLOAD */

export async function downloadPredictionImage(predictionId: number): Promise<Blob> {
  const token = getAuthToken();
  if (!token) {
    throw new Error("Not authenticated");
  }

  const res = await fetch(`${API_BASE_URL}/predictions/${predictionId}/download`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    credentials: "include",
  });

  if (!res.ok) {
    throw new Error(await getFriendlyError(res));
  }

  return await res.blob();
}


/* DEMO USER (для первой генерации) */

const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL;
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD;

let demoToken: string | null = null;

export async function ensureDemoToken(): Promise<string> {
  if (demoToken) return demoToken;
  if (!DEMO_EMAIL || !DEMO_PASSWORD) {
    throw new Error("DEMO user credentials are not configured");
  }

  const tokenResponse = await login(DEMO_EMAIL, DEMO_PASSWORD);
  demoToken = tokenResponse.access_token;
  return demoToken;
}

export async function demoEnqueuePrediction(
  prompt: string,
  modelId?: number
): Promise<PredictionEnqueueResponse> {
  const token = await ensureDemoToken();

  const res = await fetch(`${API_BASE_URL}/predictions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({ prompt, model_id: modelId ?? null }),
    credentials: "include"  // кука для demo-юзера тоже сохранится
  });

  if (!res.ok) {
    throw new Error(await getFriendlyError(res));
  }

  return res.json() as Promise<PredictionEnqueueResponse>;
}
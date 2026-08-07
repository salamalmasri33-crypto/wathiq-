import axios, { AxiosHeaders } from "axios";
import { clearSession, getStoredToken } from "@/lib/auth-storage";

const DEFAULT_API_BASE_URL = "http://localhost:5281/api";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

const api = axios.create({
  baseURL: API_BASE_URL,
});

api.interceptors.request.use(
  (config) => {
    const token = getStoredToken();
    if (token) {
      config.headers = AxiosHeaders.from(config.headers);
      config.headers.set("Authorization", `Bearer ${token}`);
    }

    return config;
  },
  (error) => Promise.reject(error),
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const requestUrl = error.config?.url ?? "";
      const isAuthRequest =
        requestUrl.includes("/auth/login") ||
        requestUrl.includes("/auth/verify-2fa") ||
        requestUrl.includes("/auth/password/forgot") ||
        requestUrl.includes("/auth/password/reset");

      if (!isAuthRequest) {
        clearSession();
      }
    }

    return Promise.reject(error);
  },
);

export default api;

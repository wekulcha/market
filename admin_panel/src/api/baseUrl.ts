const API_BASE =
  import.meta.env.VITE_API_URL ??
  (import.meta.env.DEV ? "/api/v1" : "http://localhost:8000/api/v1");

export const BASE_URL = API_BASE;

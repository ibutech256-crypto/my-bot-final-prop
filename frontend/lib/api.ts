export const API_BASE_URL=process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
export async function apiGet<T>(path:string,token?:string):Promise<T>{const res=await fetch(`${API_BASE_URL}${path}`,{headers:token?{Authorization:`Bearer ${token}`}:{}});if(!res.ok)throw new Error(`API ${res.status}`);return res.json() as Promise<T>}

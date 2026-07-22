import { create } from "zustand";
type State={accessToken:string|null; setAccessToken:(token:string|null)=>void};
export const useSessionStore=create<State>(set=>({accessToken:null,setAccessToken:(accessToken)=>set({accessToken})}));

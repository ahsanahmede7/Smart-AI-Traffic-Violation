import {useEffect,useState} from "react";
const API=import.meta.env.VITE_API_URL||"http://127.0.0.1:8000";
export const getToken=()=>sessionStorage.getItem("tok");
export const evidenceUrl=n=>n?`${API}/evidence/${encodeURIComponent(n)}`:null;
export const toDate=t=>new Date(/Z|\+/.test(t)?t:t+"Z");
export async function api(path,opt={}){
  const r=await fetch(API+path,{...opt,headers:{"Content-Type":"application/json",...(getToken()&&{Authorization:"Bearer "+getToken()})}});
  if(r.status===401&&getToken()){sessionStorage.removeItem("tok");location.href="/login"}
  if(!r.ok)throw new Error(r.status===422?"Invalid input (password needs 6+ characters)":r.status===401?"Wrong username or password":"Request failed ("+r.status+")");
  return r.json();
}
export function usePoll(path,ms=10000){
  const[d,setD]=useState(null),[e,setE]=useState(null);
  useEffect(()=>{let on=true;setD(null);
    const f=()=>api(path).then(x=>on&&(setD(x),setE(null))).catch(x=>on&&setE(x.message==="Failed to fetch"?"Backend not reachable. Is uvicorn running?":x.message));
    f();const t=setInterval(f,ms);return()=>{on=false;clearInterval(t)}},[path,ms]);
  return[d,e];
}
export async function download(path,name){
  const r=await fetch(API+path,{headers:{Authorization:"Bearer "+getToken()}});
  if(!r.ok)throw new Error("Download failed ("+r.status+")");
  const u=URL.createObjectURL(await r.blob()),l=document.createElement("a");l.href=u;l.download=name;l.click();URL.revokeObjectURL(u);
}

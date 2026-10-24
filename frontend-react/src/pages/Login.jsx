import {useState} from "react"; import {useNavigate} from "react-router-dom"; import {ShieldCheck} from "lucide-react"; import {api} from "../api.js";
export default function Login(){
  const[u,setU]=useState("admin"),[p,setP]=useState(""),[err,setErr]=useState(""),[busy,setBusy]=useState(false),go=useNavigate();
  async function submit(e){e.preventDefault();setBusy(true);setErr("");
    try{const r=await api("/api/auth/login",{method:"POST",body:JSON.stringify({username:u,password:p})});sessionStorage.setItem("tok",r.token);go("/")}
    catch(x){setErr(x.message==="Failed to fetch"?"Backend not reachable. Is uvicorn running?":x.message)}finally{setBusy(false)}}
  return <div className="login"><form className="card" onSubmit={submit}>
    <div className="logo"><ShieldCheck size={28}/></div><h2>Smart Traffic AI</h2><p className="muted">Violation Monitoring Dashboard</p>
    <input className="inp" value={u} onChange={e=>setU(e.target.value)} placeholder="Username" autoFocus/>
    <input className="inp" type="password" value={p} onChange={e=>setP(e.target.value)} placeholder="Password"/>
    {err&&<small className="red">{err}</small>}<button className="btn" disabled={busy}>{busy?"Signing in…":"Sign in"}</button></form></div>;
}

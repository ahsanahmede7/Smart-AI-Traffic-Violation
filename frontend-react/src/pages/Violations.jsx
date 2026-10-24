import {useState} from "react"; import {Trash2,FileText,Pencil} from "lucide-react";
import {api,usePoll,evidenceUrl,toDate,download} from "../api.js"; import {Card,Badge,Loading,Err,Empty} from "../ui.jsx";
const TYPES=["","No Helmet","Wrong Way","Red Light","No Seat Belt"];
const ghost={background:"transparent",color:"var(--ink)",border:"1px solid var(--line)"};
const fineOf=(x,cfg)=>{ if(!cfg)return null; const rule=cfg.fines[x.type]; if(!rule)return null;
  const col=cfg.classes[x.vehicleClass||(x.type==="No Helmet"?"motorcycle":"")]; const a=col?rule.amounts[col]:null; return a==null?null:a; };
export default function Violations(){
  const[t,setT]=useState(""),[n,setN]=useState(0),[msg,setMsg]=useState("");
  const[d,e]=usePoll("/api/violations?limit=200"+(t?"&type="+encodeURIComponent(t):"")+"&r="+n);
  const[cfg]=usePoll("/api/fines",3600000);
  const run=async(path,ask)=>{if(!window.confirm(ask))return;try{const r=await api(path,{method:"DELETE"});setMsg(r.deleted+" record(s) deleted");setN(n+1)}catch(x){setMsg(x.message)}};
  const editPlate=async x=>{const v=window.prompt("Number plate (check the evidence image and enter the correct number):",x.plateText||"");if(v===null)return;
    try{await api("/api/violations/"+x.id,{method:"PATCH",body:JSON.stringify({plateText:v})});setMsg("Plate saved");setN(n+1)}catch(err){setMsg(err.message)}};
  const challan=x=>download("/api/violations/"+x.id+"/challan","challan_"+x.id.slice(-8)+".pdf").catch(err=>setMsg(err.message));
  return <><div className="page-hd"><h1>Violations</h1><div style={{display:"flex",gap:8}}>
      <select className="inp" value={t} onChange={x=>setT(x.target.value)}>{TYPES.map(x=><option key={x} value={x}>{x||"All types"}</option>)}</select>
      <button className="btn sm" style={{background:"#dc2626"}} onClick={()=>run("/api/violations?confirm=yes","This permanently deletes ALL violations and their evidence images. Continue?")}><Trash2 size={16}/> Delete all</button></div></div>
    {cfg&&<p className="muted" style={{margin:"0 0 10px",fontSize:12}}>Fine schedule: {cfg.name} (verified {cfg.verified}). Confirm against the official notification before issuing a challan.</p>}
    {msg&&<p className="muted">{msg}</p>}
    {e?<Err m={e}/>:!d?<Loading/>:<Card>{d.length?<div className="tbl"><table><thead><tr><th>Type</th><th>Vehicle</th><th>Number plate</th><th>Fine</th><th>Location</th><th>Conf.</th><th>Time</th><th>Evidence</th><th>Actions</th></tr></thead>
      <tbody>{d.map(x=>{const f=fineOf(x,cfg);return <tr key={x.id}><td><Badge type={x.type}/></td><td>#{x.vehicleId}</td>
        <td><div style={{display:"flex",alignItems:"center",gap:8}}>{x.plateImage&&<a href={evidenceUrl(x.plateImage)} target="_blank" rel="noreferrer"><img src={evidenceUrl(x.plateImage)} alt="plate" style={{height:28,borderRadius:4,border:"1px solid var(--line)"}}/></a>}
          <b>{x.plateText||(x.plateImage?"Verify":"—")}</b><button className="btn sm" style={ghost} title="Enter / correct the plate" onClick={()=>editPlate(x)}><Pencil size={14}/></button></div></td>
        <td>{f!=null?"PKR "+f.toLocaleString():<span className="muted">Officer to set</span>}</td>
        <td>{x.location}</td><td>{Math.round(x.confidence*100)}%</td><td>{toDate(x.timestamp).toLocaleString()}</td>
        <td>{x.evidenceImage?<a href={evidenceUrl(x.evidenceImage)} target="_blank" rel="noreferrer">View</a>:"—"}</td>
        <td><div style={{display:"flex",gap:6}}><button className="btn sm" style={ghost} title="Download challan PDF" onClick={()=>challan(x)}><FileText size={14}/> Challan</button>
          <button className="btn sm" style={{background:"transparent",color:"#dc2626"}} title="Delete" onClick={()=>run("/api/violations/"+x.id,"Delete this violation and its evidence image?")}><Trash2 size={16}/></button></div></td></tr>})}</tbody></table></div>:<Empty>No violations found.</Empty>}</Card>}</>;
}

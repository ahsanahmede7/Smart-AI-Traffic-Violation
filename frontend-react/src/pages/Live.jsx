import {useState,useEffect,useRef} from "react"; import {Upload,Camera,Square,Play,Video} from "lucide-react";
import {api,getToken,usePoll,toDate} from "../api.js"; import {Badge,Empty} from "../ui.jsx";
const API=import.meta.env.VITE_API_URL||"http://127.0.0.1:8000";
const KEY="liveJob";
const RULES=[["helmet","No Helmet","Riders without a helmet",null],["redlight","Red Light","Vehicles crossing the stop line on red","Needs calibration"],
  ["wrongway","Wrong Way","Vehicles against the legal direction","Needs calibration"],["seatbelt","No Seat Belt","Drivers without a visible seat belt","Experimental"]];
const DISP=[["helmets","Helmet boxes"],["vehicles","Vehicle boxes"],["ids","Vehicle IDs"],["plates","Plate boxes"],["belts","Seat-belt boxes"]];
const CSS=`
.lv{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(320px,1fr);gap:16px;align-items:start}
@media(max-width:1100px){.lv{grid-template-columns:1fr}}
.lv .panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}
.lv h3{margin:0 0 12px;font-size:13px;letter-spacing:.04em;text-transform:uppercase;color:var(--mut);font-weight:600}
.lv .stage{position:relative;aspect-ratio:16/9;background:#05080f;border-radius:10px;overflow:hidden;display:grid;place-items:center}
.lv .stage img{width:100%;height:100%;object-fit:contain;display:block}
.lv .ph{color:#94a3b8;text-align:center;padding:24px;font-size:14px}
.lv .bar{display:flex;gap:18px;flex-wrap:wrap;align-items:center;margin-top:12px;color:var(--mut);font-size:13px}.lv .bar b{color:var(--ink)}
.lv .pill{display:inline-flex;gap:6px;align-items:center;font-size:12px;font-weight:600;padding:3px 10px;border-radius:99px;border:1px solid var(--line)}
.lv .pill i{width:8px;height:8px;border-radius:50%;background:#94a3b8}.lv .pill.running i{background:#16a34a;animation:p 1.6s infinite}.lv .pill.failed i{background:#dc2626}.lv .pill.done i{background:#2563eb}
.lv .seg{display:flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}.lv .seg button{flex:1;border:0;background:transparent;color:var(--ink);padding:8px 10px;cursor:pointer;font:inherit;font-size:13px}
.lv .seg button.on{background:var(--navy);color:#fff}
.lv .sec{padding:14px 0;border-top:1px solid var(--line)}.lv .sec:first-of-type{border-top:0;padding-top:0}
.lv label.f{display:block;font-size:12px;color:var(--mut);margin:10px 0 4px}
.lv .file{display:flex;align-items:center;gap:10px;border:1px dashed var(--line);border-radius:8px;padding:10px 12px;cursor:pointer;font-size:13px}.lv .file span{color:var(--mut);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lv .rule{display:flex;gap:10px;align-items:flex-start;padding:8px 0}.lv .rule b{font-size:14px}.lv .rule small{display:block;color:var(--mut)}
.lv .tag{font-size:10px;font-weight:600;border-radius:5px;padding:1px 6px;margin-left:6px;background:#fef3c7;color:#92400e;vertical-align:middle}
.lv .chips{display:flex;gap:8px;flex-wrap:wrap}.lv .chip{display:flex;gap:6px;align-items:center;font-size:13px;border:1px solid var(--line);border-radius:99px;padding:4px 10px}
.lv .hint{color:var(--mut);font-size:12px;margin-top:6px}.lv .err{color:#dc2626;font-size:13px;margin:10px 0 0}
.lv .go{width:100%;justify-content:center;padding:12px;font-size:15px}
.lv .feed .row{display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid var(--line);font-size:13px}.lv .feed .row:last-child{border:0}`;

function Picker({file,need,pts,setPts,hint}){
  const cv=useRef(null),base=useRef(null),[dim,setDim]=useState(null);
  useEffect(()=>{
    setDim(null); if(!file)return; const url=URL.createObjectURL(file), v=document.createElement("video");
    v.muted=true; v.preload="auto"; v.src=url;
    v.onloadeddata=()=>{v.currentTime=Math.min(1,(v.duration||2)/2)};
    v.onseeked=()=>{const w=Math.min(v.videoWidth,960),h=Math.round(v.videoHeight*w/v.videoWidth),c=document.createElement("canvas");
      c.width=w;c.height=h;c.getContext("2d").drawImage(v,0,0,w,h);base.current=c;setDim({w,h,vw:v.videoWidth,vh:v.videoHeight})};
    v.onerror=()=>setDim({err:true});
    return()=>URL.revokeObjectURL(url);
  },[file]);
  useEffect(()=>{
    if(!dim||dim.err||!cv.current)return; const x=cv.current.getContext("2d"); x.drawImage(base.current,0,0);
    const P=pts.map(p=>[p[0]*dim.w/dim.vw,p[1]*dim.h/dim.vh]);
    [[0,1,"#ef4444"],[2,3,"#22c55e"]].forEach(([i,j,col])=>{
      if(P[i]){x.fillStyle=col;x.beginPath();x.arc(P[i][0],P[i][1],6,0,7);x.fill()}
      if(P[i]&&P[j]){x.strokeStyle=col;x.lineWidth=3;x.beginPath();x.moveTo(...P[i]);x.lineTo(...P[j]);x.stroke();x.beginPath();x.arc(P[j][0],P[j][1],6,0,7);x.fill()}});
  },[dim,pts]);
  if(!dim)return <p className="hint">Loading a frame from the video…</p>;
  if(dim.err)return <p className="err">This browser cannot preview the video. Use an MP4 (H.264) file for Red Light / Wrong Way.</p>;
  const click=e=>{if(pts.length>=need)return;const r=cv.current.getBoundingClientRect();
    setPts([...pts,[Math.round((e.clientX-r.left)*dim.vw/r.width),Math.round((e.clientY-r.top)*dim.vh/r.height)]])};
  return <div><p className="hint">{hint} <b>({pts.length}/{need} points)</b> <button className="btn sm" style={{marginLeft:8}} onClick={()=>setPts([])}>Reset</button></p>
    <canvas ref={cv} width={dim.w} height={dim.h} onClick={click} style={{width:"100%",cursor:"crosshair",borderRadius:8,marginTop:6}}/></div>;
}

export default function Live(){
  const[mode,setMode]=useState("file"),[cam,setCam]=useState("0"),[file,setFile]=useState(null),[loc,setLoc]=useState("Main Road"),[rules,setRules]=useState(["helmet"]),[pts,setPts]=useState([]);
  const[sens,setSens]=useState("balanced"),[speed,setSpeed]=useState("balanced"),[disp,setDisp]=useState(["helmets","plates"]),[plateTrack,setPlateTrack]=useState(true),[ocr,setOcr]=useState(false),[caps,setCaps]=useState(null);
  const[job,setJob]=useState(sessionStorage.getItem(KEY)),[st,setSt]=useState(null),[err,setErr]=useState(""),[busy,setBusy]=useState(false),[sk,setSk]=useState(0),[imgErr,setImgErr]=useState(false);
  const[v]=usePoll("/api/violations?limit=8",3000);
  const isCam=mode==="cam",red=!isCam&&rules.includes("redlight"),wrong=!isCam&&rules.includes("wrongway"),need=(red?2:0)+(wrong?2:0);
  const hint=[red&&"Step 1: click two points on the stop line (red).",wrong&&"Step 2: click the start and end of the legal traffic direction (green)."].filter(Boolean).join(" ");
  useEffect(()=>setPts([]),[file,red,wrong]);
  useEffect(()=>{api("/api/capabilities").then(setCaps).catch(()=>{})},[]);
  // returning to this page re-attaches to the job that kept running on the server
  useEffect(()=>{api("/api/jobs").then(l=>{if(l.length){const j=l.find(x=>x.status==="running")||l[0];setJob(j.id);setSt(j)}else setJob(null)}).catch(()=>{})},[]);
  useEffect(()=>{job?sessionStorage.setItem(KEY,job):sessionStorage.removeItem(KEY)},[job]);
  useEffect(()=>{if(!job)return;
    const f=()=>api("/api/jobs/"+job).then(setSt).catch(e=>{if(String(e.message).includes("404")){setJob(null);setSt(null)}});
    f();const t=setInterval(f,2000);return()=>clearInterval(t)},[job]);
  const toggle=k=>setRules(r=>r.includes(k)?r.filter(x=>x!==k):[...r,k]);
  const togDisp=k=>setDisp(d=>d.includes(k)?d.filter(x=>x!==k):[...d,k]);
  async function start(){
    if(!rules.length)return setErr("Select at least one violation to detect.");
    if(isCam&&(rules.includes("redlight")||rules.includes("wrongway")))return setErr("Camera mode supports No Helmet and No Seat Belt only. Red Light and Wrong Way need a video file for calibration.");
    if(!isCam&&!file)return setErr("Choose a video file first."); if(!isCam&&pts.length<need)return setErr("Calibration incomplete: click the required points on the video frame ("+pts.length+"/"+need+").");
    setBusy(true);setErr("");setSt(null);setJob(null);setImgErr(false);
    try{const fd=new FormData();fd.append("location",loc);fd.append("rules",rules.join(","));fd.append("sensitivity",sens);fd.append("speed",speed);fd.append("display",disp.join(","));fd.append("plate_track",plateTrack?"1":"0");fd.append("ocr",ocr?"1":"");
      if(isCam)fd.append("camera",cam);else{fd.append("file",file);
        if(red)fd.append("stop_line",pts.slice(0,2).map(p=>p.join(",")).join(","));
        if(wrong){const[a,b]=pts.slice(red?2:0,(red?2:0)+2);if(a[0]===b[0]&&a[1]===b[1])throw new Error("The two direction points must be different.");fd.append("allowed_dir",(b[0]-a[0])+","+(b[1]-a[1]))}}
      const r=await fetch(API+"/api/jobs",{method:"POST",headers:{Authorization:"Bearer "+getToken()},body:fd});
      const j=await r.json();if(!r.ok)throw new Error(typeof j.detail==="string"?j.detail:"Could not start the session.");setJob(j.id);
    }catch(e){setErr(e.message==="Failed to fetch"?"Cannot reach the backend. Is uvicorn running?":e.message)}finally{setBusy(false)}}
  const stop=()=>api("/api/jobs/"+job+"/stop",{method:"POST"}).then(setSt).catch(e=>setErr(e.message));
  const running=st&&st.status==="running", state=!job||!st?"idle":st.status;
  const label={idle:"Idle",running:"Running",done:"Completed",stopped:"Stopped",failed:"Failed"}[state]||state;
  const noPlate=caps&&!caps.plateModel;
  return <div className="lv"><style>{CSS}</style>
    <div>
      <div className="page-hd" style={{marginBottom:12}}><h1>Live Monitoring</h1><span className={"pill "+state}><i/>{label}</span></div>
      <div className="panel"><div className="stage">
        {job?<img key={sk} src={`${API}/api/jobs/${job}/stream?token=${getToken()}`} alt="Live detection feed" onLoad={()=>setImgErr(false)} onError={()=>setImgErr(true)}/>
          :<div className="ph"><Video size={34}/><p>No active session.<br/>Choose a source and press <b>Start detection</b>.</p></div>}
        {job&&running&&!st.hasFrame&&<div className="ph" style={{position:"absolute"}}>Loading models… the first frame can take 20–60 seconds.</div>}
      </div>
      {job&&<div className="bar"><span>Source <b>{st?st.source:"…"}</b></span><span>Elapsed <b>{st?st.seconds+" s":"…"}</b></span><span>Violations <b>{st?st.violations:0}</b></span>
        {running&&<button className="btn sm" style={{background:"#dc2626",marginLeft:"auto"}} onClick={stop}><Square size={14}/> Stop</button>}</div>}
      {imgErr&&<p className="err">The video stream could not connect (your login may have expired or the backend stopped). <button className="btn sm" onClick={()=>{setImgErr(false);setSk(sk+1)}}>Reconnect</button></p>}
      {st&&st.status==="failed"&&<pre className="err" style={{whiteSpace:"pre-wrap"}}>{st.error}</pre>}</div>
      <div className="panel feed"><h3>Latest detections</h3>{v&&v.length?v.map(x=><div className="row" key={x.id}><span><Badge type={x.type}/> <span className="muted">&nbsp;Vehicle #{x.vehicleId} · {x.location}{x.plateText?" · "+x.plateText:""}</span></span><span className="muted">{toDate(x.timestamp).toLocaleTimeString()}</span></div>):<Empty>No violations recorded yet.</Empty>}</div>
    </div>
    <div className="panel">
      <div className="sec"><h3>Source</h3>
        <div className="seg"><button className={mode==="file"?"on":""} onClick={()=>setMode("file")}>Video file</button><button className={mode==="cam"?"on":""} onClick={()=>setMode("cam")}>Camera</button></div>
        {isCam?<><label className="f">Camera index or stream URL</label><input className="inp" style={{width:"100%"}} value={cam} onChange={e=>setCam(e.target.value)} placeholder="0 = laptop camera, or rtsp://…"/>
            <p className="hint">0 is the camera of the computer running the backend. Close other apps that use the camera.</p></>
          :<><label className="f">Video</label><label className="file"><Upload size={16}/><span>{file?file.name:"Choose a video file (MP4, AVI, MOV, MKV)"}</span><input type="file" accept="video/*" hidden onChange={e=>setFile(e.target.files[0])}/></label></>}
        <label className="f">Location</label><input className="inp" style={{width:"100%"}} value={loc} onChange={e=>setLoc(e.target.value)} placeholder="e.g. Shahrah-e-Faisal"/></div>
      <div className="sec"><h3>Violations to detect</h3>
        {RULES.map(([k,t,d,tag])=>{const off=isCam&&(k==="redlight"||k==="wrongway");
          return <label key={k} className="rule" style={{opacity:off?.45:1}}><input type="checkbox" disabled={off} checked={!off&&rules.includes(k)} onChange={()=>toggle(k)}/><span><b>{t}</b>{tag&&<span className="tag">{tag}</span>}<small>{d}</small></span></label>})}
        {!isCam&&file&&need>0&&<Picker file={file} need={need} pts={pts} setPts={setPts} hint={hint}/>}</div>
      <div className="sec"><h3>Detection settings</h3>
        <label className="f" style={{marginTop:0}}>Helmet sensitivity</label>
        <div className="seg">{[["strict","Strict"],["balanced","Balanced"],["sensitive","Sensitive"]].map(([k,l])=><button key={k} className={sens===k?"on":""} onClick={()=>setSens(k)}>{l}</button>)}</div>
        <p className="hint">Strict: fewer false alarms, may miss some. Sensitive: catches more, more false alarms.</p>
        <label className="f">Processing speed</label>
        <div className="seg">{[["fast","Fast"],["balanced","Balanced"],["accurate","Accurate"]].map(([k,l])=><button key={k} className={speed===k?"on":""} onClick={()=>setSpeed(k)}>{l}</button>)}</div></div>
      <div className="sec"><h3>On-screen overlay</h3><div className="chips">{DISP.map(([k,l])=><label key={k} className="chip"><input type="checkbox" checked={disp.includes(k)} onChange={()=>togDisp(k)}/>{l}</label>)}</div>
        <p className="hint">For a clean view keep only Helmet and Plate boxes.</p></div>
      <div className="sec"><h3>Number plates</h3>
        <label className="rule"><input type="checkbox" disabled={noPlate} checked={plateTrack&&!noPlate} onChange={e=>setPlateTrack(e.target.checked)}/><span><b>Plate tracking</b><small>Keeps the clearest plate image for every tracked vehicle</small></span></label>
        <label className="rule"><input type="checkbox" disabled={!caps||!caps.ocr} checked={ocr&&!!caps&&caps.ocr} onChange={e=>setOcr(e.target.checked)}/><span><b>Read plate text (OCR)</b><small>Unverified accuracy: an officer should confirm the number</small></span></label>
        {noPlate&&<p className="err">Plate model not found (Models/LicennsePlate/best.pt).</p>}
        {caps&&!caps.ocr&&<p className="hint">OCR is not installed. Run <code>pip install easyocr</code>, or type the plate on the Violations page.</p>}</div>
      {err&&<p className="err">{err}</p>}
      <button className="btn go" onClick={start} disabled={busy||running}>{isCam?<Camera size={16}/>:<Play size={16}/>}{busy?"Starting…":running?"Session running":"Start detection"}</button>
    </div></div>;
}

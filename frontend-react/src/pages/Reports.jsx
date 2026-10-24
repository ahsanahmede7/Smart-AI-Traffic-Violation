import {Printer,Download} from "lucide-react"; import {usePoll,download} from "../api.js"; import {Card,Loading,Err} from "../ui.jsx";
export default function Reports(){
  const[r,e]=usePoll("/api/reports",30000); if(e)return <Err m={e}/>; if(!r)return <Loading/>;
  return <><div className="page-hd"><h1>Daily Report</h1><div style={{display:"flex",gap:8}}><button className="btn sm" onClick={()=>download("/api/reports/pdf","daily_report.pdf").catch(e=>alert(e.message))}><Download size={16}/> Download PDF</button><button className="btn sm" onClick={()=>window.print()}><Printer size={16}/> Print</button></div></div>
    <Card title={"SMART TRAFFIC REPORT · "+r.date}><div className="item"><span>Total violations today</span><b>{r.totalViolations}</b></div>
      {Object.entries(r.byType).map(([k,v])=><div className="item" key={k}><span>{k}</span><b>{v}</b></div>)}</Card></>;
}

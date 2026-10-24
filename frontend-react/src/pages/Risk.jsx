import {usePoll} from "../api.js"; import {Card,Loading,Err} from "../ui.jsx";
const CLS={"LOW":"medium","MEDIUM":"high","HIGH":"critical","VERY HIGH":"critical"};
export default function Risk(){
  const[r,e]=usePoll("/api/predict",300000); if(e)return <Err m={e}/>; if(!r)return <Loading/>;
  const max=Math.max(1,...r.map(x=>x.expected));
  return <><div className="page-hd"><h1>Violation Risk Forecast</h1></div>
    <Card title="Today, by hour (UTC) - Random Forest">
      {r.map(x=><div className="item" key={x.hour}>
        <span style={{width:60}}>{String(x.hour).padStart(2,"0")}:00</span>
        <div style={{flex:1,margin:"0 12px",background:"var(--bg)",borderRadius:6,height:10}}>
          <div style={{width:(x.expected/max*100)+"%",height:10,borderRadius:6,background:"var(--blue)"}}/></div>
        <span style={{width:50,textAlign:"right"}}>{x.expected}</span>
        <span className={"badge "+CLS[x.risk]} style={{marginLeft:12,width:80,textAlign:"center"}}>{x.risk}</span></div>)}
    </Card>
    <small className="muted">Forecast is based on past hourly counts. With little real data it follows the demo pattern.</small></>;
}

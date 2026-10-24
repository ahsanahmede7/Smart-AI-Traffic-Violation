import {BarChart,Bar,XAxis,YAxis,Tooltip,ResponsiveContainer,Cell} from "recharts";
import {usePoll} from "../api.js"; import {Card,Loading,Err,Empty,COLORS} from "../ui.jsx";
const ax={tick:{fill:"var(--mut)",fontSize:11},axisLine:false,tickLine:false};
export default function Analytics(){
  const[a,e]=usePoll("/api/analytics"),[pr]=usePoll("/api/prediction",60000); if(e)return <Err m={e}/>; if(!a)return <Loading/>;
  const hours=Array.from({length:24},(_,h)=>({h:h+":00",n:(a.hourly.find(x=>x.hour===h)||{}).count||0}));
  const types=Object.entries(a.byType).map(([name,n])=>({name,n}));
  const RC={HIGH:"#ef4444",MEDIUM:"#f59e0b",LOW:"#16a34a"};
  const pred=pr&&pr.ready?pr.hours.map(x=>({...x,h:x.hour+":00"})):[];
  return <><div className="page-hd"><h1>Analytics</h1></div>
    <Card title={"Violation risk prediction"+(pr&&pr.ready?" · "+pr.date+" (UTC)":"")}>{!pr?<Empty>Loading…</Empty>:!pr.ready?<Empty>{pr.message} (now: {pr.total})</Empty>:<>
      <div style={{height:240}}><ResponsiveContainer><BarChart data={pred}><XAxis dataKey="h" interval={2} {...ax}/><YAxis width={28} {...ax}/><Tooltip formatter={(v,n,p)=>[v+" ("+p.payload.risk+")","Predicted violations"]}/><Bar dataKey="predicted" radius={[4,4,0,0]}>{pred.map(p=><Cell key={p.hour} fill={RC[p.risk]}/>)}</Bar></BarChart></ResponsiveContainer></div>
      <small className="muted">{pr.model} trained on {pr.trainedOnDays} day(s), {pr.totalRecords} records. Risk is relative to the busiest predicted hour.</small></>}</Card>
    <Card title="Hourly distribution (UTC)"><div style={{height:260}}><ResponsiveContainer><BarChart data={hours}><XAxis dataKey="h" interval={2} {...ax}/><YAxis allowDecimals={false} width={28} {...ax}/><Tooltip/><Bar dataKey="n" name="Violations" fill="#2563eb" radius={[4,4,0,0]}/></BarChart></ResponsiveContainer></div></Card>
    <div className="two"><Card title="By violation type">{types.length?<div style={{height:240}}><ResponsiveContainer><BarChart data={types} layout="vertical"><XAxis type="number" allowDecimals={false} {...ax}/><YAxis type="category" dataKey="name" width={90} {...ax}/><Tooltip/><Bar dataKey="n" name="Violations" radius={[0,4,4,0]}>{types.map((t,i)=><Cell key={t.name} fill={COLORS[i%COLORS.length]}/>)}</Bar></BarChart></ResponsiveContainer></div>:<Empty>No data yet.</Empty>}</Card>
      <Card title="By location">{a.locations.length?a.locations.map(l=><div className="item" key={l.location}><span>{l.location}</span><b>{l.count}</b></div>):<Empty>No data yet.</Empty>}</Card></div></>;
}

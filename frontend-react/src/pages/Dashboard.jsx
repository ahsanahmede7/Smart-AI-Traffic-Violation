import {AlertTriangle,Car,MapPin,Layers} from "lucide-react";
import {AreaChart,Area,XAxis,YAxis,Tooltip,ResponsiveContainer,PieChart,Pie,Cell} from "recharts";
import {usePoll,evidenceUrl,toDate} from "../api.js"; import {Card,Stat,Badge,Loading,Err,Empty,COLORS} from "../ui.jsx";
export default function Dashboard(){
  const[s,e]=usePoll("/api/statistics"),[v]=usePoll("/api/violations?limit=6"),[a]=usePoll("/api/analytics");
  if(e)return <Err m={e}/>; if(!s||!v||!a)return <Loading/>;
  const hours=Array.from({length:24},(_,h)=>({h:h+":00",n:(a.hourly.find(x=>x.hour===h)||{}).count||0}));
  const types=Object.entries(s.byType).map(([name,value])=>({name,value}));
  return <><div className="page-hd"><h1>Overview</h1><span className="live"><i/> Live · refreshes every 10s</span></div>
    <div className="stats"><Stat label="Total Violations" value={s.total} icon={AlertTriangle} hint="all time"/>
      <Stat label="Vehicles Flagged" value={s.vehicles} icon={Car} hint="unique tracked IDs"/>
      <Stat label="Locations" value={a.locations.length} icon={MapPin} hint="with violations"/>
      <Stat label="Violation Types" value={types.length} icon={Layers} hint="detected so far"/></div>
    <div className="row"><Card title="Violations by hour (UTC)">
      <div style={{height:260}}><ResponsiveContainer><AreaChart data={hours}><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#ef4444" stopOpacity=".4"/><stop offset="100%" stopColor="#ef4444" stopOpacity="0"/></linearGradient></defs>
        <XAxis dataKey="h" tick={{fill:"var(--mut)",fontSize:11}} interval={2} axisLine={false} tickLine={false}/><YAxis allowDecimals={false} tick={{fill:"var(--mut)",fontSize:11}} axisLine={false} tickLine={false} width={28}/>
        <Tooltip/><Area type="monotone" dataKey="n" name="Violations" stroke="#ef4444" strokeWidth={2} fill="url(#g)"/></AreaChart></ResponsiveContainer></div></Card>
      <Card title="Recent Violations">{v.length?v.map(x=><div className="item" key={x.id}><div><Badge type={x.type}/><small className="muted"> ID {x.vehicleId} · {x.location}</small></div>
        <small className="muted">{toDate(x.timestamp).toLocaleTimeString()}{x.evidenceImage&&<> · <a href={evidenceUrl(x.evidenceImage)} target="_blank" rel="noreferrer">Evidence</a></>}</small></div>)
        :<Empty>No violations yet. Run the AI pipeline.</Empty>}</Card></div>
    <Card title="Violation distribution">{types.length?<div className="dist"><div style={{height:220,width:220}}><ResponsiveContainer><PieChart><Pie data={types} dataKey="value" innerRadius={55} outerRadius={90} paddingAngle={2}>{types.map((t,i)=><Cell key={t.name} fill={COLORS[i%COLORS.length]}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer></div>
      <ul>{types.map((t,i)=><li key={t.name}><i style={{background:COLORS[i%COLORS.length]}}/>{t.name}<b>{Math.round(t.value*100/s.total)}%</b></li>)}</ul></div>:<Empty>No data yet.</Empty>}</Card></>;
}

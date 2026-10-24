import {usePoll} from "../api.js"; import {Card,Loading,Err,Empty} from "../ui.jsx";
export default function Vehicles(){
  const[d,e]=usePoll("/api/vehicles"); if(e)return <Err m={e}/>; if(!d)return <Loading/>;
  return <><div className="page-hd"><h1>Vehicles</h1><span className="muted">{d.length} flagged</span></div>
    <Card>{d.length?<div className="chips">{d.map(id=><span className="chip" key={id}>Vehicle #{id}</span>)}</div>:<Empty>No flagged vehicles yet.</Empty>}</Card></>;
}

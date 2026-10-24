export const SEV={"Red Light":"critical","Wrong Way":"critical","No Helmet":"medium","Triple Riding":"high","Speeding":"high"};
export const COLORS=["#2563eb","#ef4444","#f59e0b","#16a34a","#8b5cf6","#06b6d4"];
export const Badge=({type})=><span className={"badge "+(SEV[type]||"high")}>{type}</span>;
export const Card=({title,right,children,className=""})=><section className={"card "+className}>{title&&<div className="hd"><h3>{title}</h3>{right}</div>}{children}</section>;
export const Stat=({label,value,icon:I,hint})=><div className="card stat"><div><p>{label}</p><h2>{value}</h2><small>{hint}</small></div><div className="ic"><I size={20}/></div></div>;
export const Loading=()=><div className="muted pad">Loading…</div>;
export const Err=({m})=><div className="card err">{m}</div>;
export const Empty=({children})=><div className="muted pad">{children}</div>;

import { usePoll, evidenceUrl, toDate } from "../api.js"; import { Card, Loading, Err, Empty, Badge } from "../ui.jsx";
export default function Alerts() {
  const [r, e] = usePoll("/api/alerts?minutes=1440", 5000); if (e) return <Err m={e} />; if (!r) return <Loading />;
  return <><div className="page-hd"><h1>Live Alerts</h1></div>
    <Card title="Last 24 hours (refreshes every 5 s)">
      {r.length === 0 && <Empty>No violations in the last 24 hours.</Empty>}
      {r.map(a => <div className="item" key={a.id}>
        <span><Badge type={a.type} /> &nbsp;Vehicle {a.vehicleId} · {Math.round(a.confidence * 100)}% · {a.location}</span>
        <span className="muted">{toDate(a.timestamp).toLocaleTimeString()} {evidenceUrl(a) && <a href={evidenceUrl(a)} target="_blank" rel="noreferrer">evidence</a>}</span></div>)}
    </Card></>;
}


import {Routes,Route,Navigate,NavLink,Outlet,useNavigate} from "react-router-dom";
import {LayoutDashboard,AlertTriangle,Car,BarChart3,FileText,Bell,TrendingUp,LogOut,ShieldCheck,Video} from "lucide-react";
import {getToken} from "./api.js";
import Live from "./pages/Live.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Violations from "./pages/Violations.jsx";
import Alerts from "./pages/Alerts.jsx";
import Risk from "./pages/Risk.jsx";
import Vehicles from "./pages/Vehicles.jsx";
import Analytics from "./pages/Analytics.jsx";
import Reports from "./pages/Reports.jsx";

const nav=[
  ["/","Overview",LayoutDashboard],
  ["/violations","Violations",AlertTriangle],
  ["/vehicles","Vehicles",Car],
  ["/analytics","Analytics",BarChart3],
  ["/alerts","Alerts",Bell],
  ["/risk","Risk",TrendingUp],
  ["/reports","Reports",FileText],
  ["/live","Live Monitoring",Video]
];

function Layout(){
  const go=useNavigate();

  if(!getToken()) return <Navigate to="/login" replace/>;

  return <div className="app">
    <aside>
      <div className="brand">
        <ShieldCheck size={22}/>
        <span>Smart Traffic AI</span>
      </div>

      <nav>
        {nav.map(([to,l,I])=>(
          <NavLink key={to} to={to} end={to==="/"}>
            <I size={18}/>{l}
          </NavLink>
        ))}
      </nav>

      <button className="out" onClick={()=>{
        sessionStorage.removeItem("tok");
        go("/login");
      }}>
        <LogOut size={18}/>Logout
      </button>
    </aside>

    <main><Outlet/></main>
  </div>;
}

export default function App(){
  return <Routes>
    <Route path="/login" element={<Login/>}/>

    <Route element={<Layout/>}>
      <Route index element={<Dashboard/>}/>
      <Route path="violations" element={<Violations/>}/>
      <Route path="vehicles" element={<Vehicles/>}/>
      <Route path="analytics" element={<Analytics/>}/>
      <Route path="reports" element={<Reports/>}/>
      <Route path="alerts" element={<Alerts/>}/>
      <Route path="risk" element={<Risk/>}/>
      <Route path="live" element={<Live/>}/>
    </Route>

    <Route path="*" element={<Navigate to="/"/>}/>
  </Routes>;
}

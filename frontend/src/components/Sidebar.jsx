import { Activity, BarChart3, CalendarDays, ChevronLeft, ClipboardList, HelpCircle, LockKeyhole, Menu, Settings2, Sparkles, TrendingUp, UserRound } from "lucide-react";
import { AvatarView } from "./Avatar.jsx";
import { BrandLogo } from "./Brand.jsx";

const nav = [["Ma",Activity],["Naptár",CalendarDays],["Trendek",BarChart3],["Cél",TrendingUp],["Insights",Sparkles],["Napló",ClipboardList],["Profil",UserRound]];
export function Sidebar({collapsed,onToggle,active,onActive,profile,locked=[],garminStatus}) { const initials=(profile?.name||"Attila").split(/\s+/).map(x=>x[0]).join("").slice(0,2).toUpperCase();return <aside className={collapsed?"sidebar collapsed":"sidebar"}>
  <div className="brand"><BrandLogo compact={collapsed}/></div>
  <nav>{nav.map(([label,Icon])=>{const isLocked=locked.includes(label);return <button className={[active===label?"active":"",isLocked?"locked":""].join(" ").trim()} disabled={isLocked} aria-disabled={isLocked} title={isLocked?"Az első Garmin-szinkron után érhető el":undefined} onClick={()=>onActive(label)} key={label}><Icon size={16}/><span>{label}</span>{isLocked&&<LockKeyhole className="nav-lock" aria-label="zárolva"/>}</button>})}</nav>
  <div className="side-bottom"><button><HelpCircle size={16}/><span>Súgó</span></button><button onClick={()=>onActive("Beállítások")}><Settings2 size={16}/><span>Beállítások</span></button><div className="profile"><AvatarView profile={profile} size="small"/><div><b>{profile?.name||"Attila"}</b><small>{garminStatus?.status==="connected"?"Garmin csatlakoztatva":"Nincs Garmin-kapcsolat"}</small></div></div></div>
  <button className="collapse" onClick={onToggle}>{collapsed?<Menu size={17}/>:<ChevronLeft size={17}/>}</button>
</aside> }

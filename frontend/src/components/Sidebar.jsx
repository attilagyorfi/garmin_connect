import { Activity, BarChart3, CalendarDays, ChevronLeft, ClipboardList, LayoutDashboard, LockKeyhole, Medal, Menu, Settings2, Sparkles, Target, UserRound } from "lucide-react";
import { AvatarView } from "./Avatar.jsx";
import { BrandLogo } from "./Brand.jsx";

const nav = [["Áttekintés",LayoutDashboard],["Ma",Activity],["Naptár",CalendarDays],["Trendek",BarChart3],["Cél",Target],["Insights",Sparkles],["Hol tartasz?",Medal],["Napló",ClipboardList],["Profil",UserRound]];
// Display-only names; the internal page key stays unchanged.
// The label is hidden when collapsed or on a narrow screen, so the aria-label carries the name and the lock.
const NAV_LABELS = {"Insights":"Összefüggések"};
export function Sidebar({collapsed,onToggle,active,onActive,profile,locked=[],garminStatus}) { const initials=(profile?.name||"Attila").split(/\s+/).map(x=>x[0]).join("").slice(0,2).toUpperCase();return <aside className={collapsed?"sidebar collapsed":"sidebar"} aria-label="Fő navigáció">
  <div className="brand"><BrandLogo compact={collapsed}/></div>
  <nav data-tour="nav">{nav.map(([label,Icon])=>{const isLocked=locked.includes(label),name=NAV_LABELS[label]||label;return <button aria-label={isLocked?`${name}, zárolva`:name} aria-current={active===label?"page":undefined} className={[active===label?"active":"",isLocked?"locked":""].join(" ").trim()} disabled={isLocked} aria-disabled={isLocked} title={isLocked?"Az első Garmin-szinkron után nyílik meg":undefined} onClick={()=>onActive(label)} key={label} data-tour={label}><Icon size={16} aria-hidden="true"/><span>{name}</span>{isLocked&&<LockKeyhole className="nav-lock" aria-hidden="true"/>}</button>})}</nav>
  <div className="side-bottom"><button aria-label="Beállítások" aria-current={active==="Beállítások"?"page":undefined} onClick={()=>onActive("Beállítások")} data-tour="settings"><Settings2 size={16} aria-hidden="true"/><span>Beállítások</span></button><div className="profile"><AvatarView profile={profile} size="small"/><div><b>{profile?.name||"Attila"}</b><small>{garminStatus?.status==="connected"?"Garmin csatlakoztatva":"Nincs Garmin-kapcsolat"}</small></div></div></div>
  <button className="collapse" onClick={onToggle} aria-label={collapsed?"Oldalsáv kinyitása":"Oldalsáv összecsukása"} aria-expanded={!collapsed}>{collapsed?<Menu size={17}/>:<ChevronLeft size={17}/>}</button>
</aside> }

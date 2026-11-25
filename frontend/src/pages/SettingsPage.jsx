import { useEffect, useState } from "react";
import { Compass, LogOut } from "lucide-react";
import { AccentPicker } from "../components/AccentPicker.jsx";
import { AccountDeletionCard, ActiveSessionsCard, AdminAccessCard, DataExportCard, DataManagementOverview, PasswordChangeCard } from "../components/AccountSettings.jsx";
import { AvatarPicker } from "../components/AvatarPicker.jsx";
import { GarminConnectionCard } from "../components/GarminConnectionCard.jsx";
import { PageHeader } from "../components/PageHeader.jsx";

const Group = ({id,eyebrow,title,text,children}) => <section className="settings-group" id={id} aria-labelledby={`${id}-title`}><div className="settings-group-heading"><span className="eyebrow">{eyebrow}</span><h2 id={`${id}-title`}>{title}</h2><p>{text}</p></div>{children}</section>;

export function SettingsPage({accent,onAccent,profile,onProfileSave,user,onLogout,garminStatus,onGarminStatus,onPasswordChanged,onAccountDeleted,onStartTour}){const [draft,setDraft]=useState(accent),[avatarDraft,setAvatarDraft]=useState(profile),[saved,setSaved]=useState(false);useEffect(()=>setAvatarDraft(profile),[profile]);
  return <><PageHeader eyebrow="SZEMÉLYRE SZABÁS" title="Beállítások"/><div className="accent-page settings-stack">
    <nav className="settings-section-nav" aria-label="Beállítási csoportok"><span>UGRÁS IDE</span><a href="#settings-data">Garmin és adatok</a><a href="#settings-personalization">Személyre szabás</a><a href="#settings-account">Fiók és biztonság</a>{user?.role==="admin"&&<a href="#settings-admin">Adminisztráció</a>}</nav>
    <Group id="settings-data" eyebrow="KAPCSOLAT ÉS ADATOK" title="Garmin és adatok" text="Itt kötheted össze vagy választhatod le a Garmin-fiókodat, és megnézheted, milyen adataid vannak."><GarminConnectionCard onStatus={onGarminStatus}/><DataManagementOverview garminStatus={garminStatus}/></Group>
    <Group id="settings-personalization" eyebrow="MEGJELENÉS" title="Személyre szabás" text="A profilképed és a választott színed minden belépés után megmarad.">
      <section className="card accent-card"><span className="eyebrow">PROFILKÉP</span><h2>A te képed</h2><p>Tölts fel saját képet, vagy válassz egy sportos avatart.</p><AvatarPicker profile={avatarDraft} onChange={value=>{setAvatarDraft(value);setSaved(false)}}/><div className="accent-actions"><button onClick={()=>setAvatarDraft(profile)}>Visszaállítás</button><button className="primary" onClick={()=>{onProfileSave(avatarDraft);setSaved(true)}}>{saved?"Mentve":"Profilkép mentése"}</button></div></section>
      <section className="card accent-card"><span className="eyebrow">MEGJELENÉS</span><h2>Az alkalmazás színe</h2><p>Ilyen színűek lesznek a kiemelések, a grafikonok, az aktív menüpont és a fő gombok.</p><AccentPicker value={draft} onChange={value=>{setDraft(value);setSaved(false)}}/><div className="accent-actions"><button onClick={()=>setDraft(accent)}>Visszaállítás</button><button className="primary" onClick={()=>{onAccent(draft);setSaved(true)}}>{saved?"Mentve":"Választás mentése"}</button></div></section></Group>
    <Group id="settings-account" eyebrow="FIÓK" title="Fiók és biztonság" text="Itt kezelheted a jelszavadat, a bejelentkezett eszközeidet és a saját adataidat.">
      <section className="card account-card"><span className="eyebrow">FIÓK</span><h2>{user?.name}</h2><p>{user?.email}</p><button className="logout-button" onClick={onLogout}><LogOut size={17}/> Kijelentkezés</button></section>
      <section className="card account-card tour-restart-card"><span className="eyebrow">BEMUTATÓ</span><h2>Nézd meg újra a bemutatót</h2><p>Lépésről lépésre végigvezetünk az alkalmazáson, a napi javaslattól a felkészülési terveken át az Edzőtársig.</p><button className="primary" onClick={onStartTour}><Compass size={17} aria-hidden="true"/> Bemutató újraindítása</button></section>
      <PasswordChangeCard onChanged={onPasswordChanged}/><DataExportCard/><ActiveSessionsCard/><AccountDeletionCard onDeleted={onAccountDeleted}/></Group>
    {user?.role==="admin"&&<Group id="settings-admin" eyebrow="ADMIN" title="Adminisztráció" text="Itt kezelheted a felhasználókat és a meghívókat."><AdminAccessCard/></Group>}
  </div></>}

import { useEffect, useState } from "react";
import { LogOut } from "lucide-react";
import { AccentPicker } from "../components/AccentPicker.jsx";
import { AccountDeletionCard, ActiveSessionsCard, AdminAccessCard, DataExportCard, DataManagementOverview, PasswordChangeCard } from "../components/AccountSettings.jsx";
import { AvatarPicker } from "../components/AvatarPicker.jsx";
import { GarminConnectionCard } from "../components/GarminConnectionCard.jsx";
import { PageHeader } from "../components/PageHeader.jsx";

const Group = ({id,eyebrow,title,text,children}) => <section className="settings-group" id={id} aria-labelledby={`${id}-title`}><div className="settings-group-heading"><span className="eyebrow">{eyebrow}</span><h2 id={`${id}-title`}>{title}</h2><p>{text}</p></div>{children}</section>;

export function SettingsPage({accent,onAccent,profile,onProfileSave,user,onLogout,garminStatus,onGarminStatus,onPasswordChanged,onAccountDeleted}){const [draft,setDraft]=useState(accent),[avatarDraft,setAvatarDraft]=useState(profile),[saved,setSaved]=useState(false);useEffect(()=>setAvatarDraft(profile),[profile]);
  return <><PageHeader eyebrow="SZEMÉLYRE SZABÁS" title="Beállítások"/><main className="accent-page settings-stack">
    <nav className="settings-section-nav" aria-label="Beállítási csoportok"><span>UGRÁS IDE</span><a href="#settings-data">Garmin és adatok</a><a href="#settings-personalization">Személyre szabás</a><a href="#settings-account">Fiók és biztonság</a>{user?.role==="admin"&&<a href="#settings-admin">Adminisztráció</a>}</nav>
    <Group id="settings-data" eyebrow="KAPCSOLAT ÉS ADATOK" title="Garmin és adatok" text="Itt kezelheted a Garmin-kapcsolatot, és ellenőrizheted, milyen adatok állnak rendelkezésre."><GarminConnectionCard onStatus={onGarminStatus}/><DataManagementOverview garminStatus={garminStatus}/></Group>
    <Group id="settings-personalization" eyebrow="MEGJELENÉS" title="Személyre szabás" text="A profilképed és az akcentusszín minden belépés után megmarad.">
      <section className="card accent-card"><span className="eyebrow">PROFILKÉP</span><h2>Személyes megjelenés</h2><p>Tölts fel saját profilképet, vagy válassz a sportos avatarok közül.</p><AvatarPicker profile={avatarDraft} onChange={value=>{setAvatarDraft(value);setSaved(false)}}/><div className="accent-actions"><button onClick={()=>setAvatarDraft(profile)}>Visszaállítás</button><button className="primary" onClick={()=>{onProfileSave(avatarDraft);setSaved(true)}}>{saved?"Mentve":"Profilkép mentése"}</button></div></section>
      <section className="card accent-card"><span className="eyebrow">MEGJELENÉS</span><h2>Akcentusszín</h2><p>Válaszd ki azt a színt, amely a kiemeléseken, grafikonokon, aktív menüpontokon és elsődleges műveleteken jelenjen meg.</p><AccentPicker value={draft} onChange={value=>{setDraft(value);setSaved(false)}}/><div className="accent-actions"><button onClick={()=>setDraft(accent)}>Visszaállítás</button><button className="primary" onClick={()=>{onAccent(draft);setSaved(true)}}>{saved?"Mentve":"Választás mentése"}</button></div></section></Group>
    <Group id="settings-account" eyebrow="FIÓK" title="Fiók és biztonság" text="A belépési adatok, aktív eszközök és saját adataid kezelése egy helyen.">
      <section className="card account-card"><span className="eyebrow">FIÓK</span><h2>{user?.name}</h2><p>{user?.email}</p><button className="logout-button" onClick={onLogout}><LogOut size={17}/> Kijelentkezés</button></section>
      <PasswordChangeCard onChanged={onPasswordChanged}/><DataExportCard/><ActiveSessionsCard/><AccountDeletionCard onDeleted={onAccountDeleted}/></Group>
    {user?.role==="admin"&&<Group id="settings-admin" eyebrow="ADMIN" title="Adminisztráció" text="A zárt rendszer felhasználóihoz és meghívóihoz kapcsolódó műveletek."><AdminAccessCard/></Group>}
  </main></>}

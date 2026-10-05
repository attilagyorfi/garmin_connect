import { useEffect, useState } from "react";
import brandMarkUrl from "./assets/hybrid-athlete-mark-on-dark.svg";
import { BrandSplash, forceSplashPreview, splashWasShown } from "./components/Brand.jsx";
import { ExplainabilityLayer, MetricHeaderLayer } from "./components/Explainability.jsx";
import { Sidebar } from "./components/Sidebar.jsx";
import { accentOptions } from "./lib/accents.js";
import { fetchCloudState, mergeCloudState, patchCloudState } from "./lib/api.js";
import { defaultProfile, readProfile } from "./lib/profile.js";
import { AuthScreen } from "./pages/AuthScreen.jsx";
import { GoalPage } from "./pages/GoalPage.jsx";
import { InsightsPage } from "./pages/InsightsPage.jsx";
import { LiveJournalPage } from "./pages/LiveJournalPage.jsx";
import { LiveTrendsPage } from "./pages/LiveTrendsPage.jsx";
import { PersistentCalendarPage } from "./pages/PersistentCalendarPage.jsx";
import { PersonalOnboarding } from "./pages/PersonalOnboarding.jsx";
import { Placeholder } from "./pages/Placeholder.jsx";
import { ProfilePage } from "./pages/ProfilePage.jsx";
import { SettingsPage } from "./pages/SettingsPage.jsx";
import { TodayLive } from "./pages/TodayLive.jsx";

export function App(){
  const [collapsed,setCollapsed]=useState(false),[active,setActive]=useState("Ma"),[accent,setAccent]=useState(()=>localStorage.getItem("hybrid-accent")||"teal"),[profile,setProfile]=useState(readProfile),[onboarded,setOnboarded]=useState(()=>localStorage.getItem("hybrid-onboarding-version")==="2"),[cloudState,setCloudState]=useState(null),[showSplash,setShowSplash]=useState(()=>forceSplashPreview()||!splashWasShown()),[user,setUser]=useState(null),[authReady,setAuthReady]=useState(false);
  const applyAccent=value=>{const option=accentOptions.find(x=>x.id===value)||accentOptions[0],root=document.documentElement;setAccent(option.id);localStorage.setItem("hybrid-accent",option.id);root.style.setProperty("--accent",option.color);root.style.setProperty("--accent-soft",option.soft);root.style.setProperty("--accent-deep",option.deep);root.style.setProperty("--accent-text",option.text)};
  const saveProfile=value=>{setProfile(value);localStorage.setItem("hybrid-profile",JSON.stringify(value))};
  const saveCloudPatch=patch=>{setCloudState(current=>mergeCloudState(current,patch));patchCloudState(patch).then(setCloudState).catch(()=>{})};
  const saveProfileCloud=value=>{saveProfile(value);saveCloudPatch({profile:value})},applyAccentCloud=value=>{applyAccent(value);saveCloudPatch({accent:value})};
  useEffect(()=>applyAccent(accent),[]);
  useEffect(()=>{let activeRequest=true;fetch("/api/auth").then(response=>response.ok?response.json():{user:null}).then(body=>{if(activeRequest)setUser(body.user||null)}).catch(()=>{}).finally(()=>activeRequest&&setAuthReady(true));return()=>{activeRequest=false}},[]);
  useEffect(()=>{if(!user)return;let activeRequest=true;setCloudState(null);fetchCloudState().then(remote=>{if(!activeRequest)return;setCloudState(remote);if(remote.profile){saveProfile(remote.profile);localStorage.setItem("hybrid-onboarding-version","2");setOnboarded(true)}else{setProfile({...defaultProfile,name:user.name||"Sportoló"});setOnboarded(false)}if(remote.accent)applyAccent(remote.accent)}).catch(()=>{});return()=>{activeRequest=false}},[user?.id]);
  const logout=async()=>{await fetch("/api/auth",{method:"DELETE"}).catch(()=>{});setUser(null);setCloudState(null)};
  const pages={"Ma":<TodayLive profile={profile} cloudState={cloudState} onCloudPatch={saveCloudPatch}/>,"Naptár":<PersistentCalendarPage profile={profile} cloudState={cloudState} onCloudPatch={saveCloudPatch}/>,"Trendek":<LiveTrendsPage profile={profile}/>,"Cél":<GoalPage profile={profile} onEdit={()=>setActive("Profil")} cloudState={cloudState} onCloudPatch={saveCloudPatch}/>,"Insights":<InsightsPage profile={profile}/>,"Napló":<LiveJournalPage cloudState={cloudState} onCloudPatch={saveCloudPatch}/>,"Profil":<ProfilePage profile={profile} onSave={saveProfileCloud}/>,"Beállítások":<SettingsPage accent={accent} onAccent={applyAccentCloud} profile={profile} onProfileSave={saveProfileCloud} user={user} onLogout={logout}/>};
  const finishSplash=()=>{globalThis.sessionStorage?.setItem("hybrid-splash-shown","1");setShowSplash(false)};
  if(!authReady)return <div className="auth-loading"><img src={brandMarkUrl} alt=""/><span>Biztonságos munkamenet ellenőrzése…</span></div>;
  if(!user)return <AuthScreen onAuthenticated={setUser}/>;
  return <div className="app"><Sidebar collapsed={collapsed} onToggle={()=>setCollapsed(!collapsed)} active={active} onActive={setActive} profile={profile}/><div className="content">{pages[active]||<Placeholder page={active}/>}</div><ExplainabilityLayer page={active}/><MetricHeaderLayer page={active}/>{showSplash&&onboarded&&<BrandSplash onDone={finishSplash}/>} {!onboarded&&<PersonalOnboarding profile={{...profile,name:user.name||profile.name}} accent={accent} onAccent={applyAccentCloud} onSave={saveProfileCloud} onDone={()=>{localStorage.setItem("hybrid-onboarding-version","2");setOnboarded(true)}}/>}</div>
}

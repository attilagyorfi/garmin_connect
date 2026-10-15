import { useEffect, useState } from "react";
import { EVENT_CHOICES } from "../components/GoalChooser.jsx";
import { AvatarView } from "../components/Avatar.jsx";
import { PageHeader } from "../components/PageHeader.jsx";
import { ProfileFields } from "../components/ProfileFields.jsx";

// The event as the athlete chose it: its name if given, otherwise the event type, with the date when known.
const eventSummary = profile => {
  const label = profile.eventName || EVENT_CHOICES.find(item => item.key === profile.eventType)?.label;
  if (!label) return "Nincs megadva";
  return profile.eventDate ? `${label} · ${new Date(`${profile.eventDate}T12:00:00`).toLocaleDateString("hu-HU", { year: "numeric", month: "long", day: "numeric" })}` : label;
};

export function ProfilePage({profile,onSave}){const [draft,setDraft]=useState(profile),[saved,setSaved]=useState(false);useEffect(()=>setDraft(profile),[profile]);return <><PageHeader eyebrow="SZEMÉLYES ALAPOK" title="Profil"/><div className="profile-page"><section className="card profile-card"><span className="eyebrow">EDZÉSPROFIL</span><h2>Az ajánlások személyes kerete</h2><ProfileFields value={draft} onChange={value=>{setDraft(value);setSaved(false)}}/><div className="profile-save">{saved&&<span>Változtatások elmentve</span>}<button className="primary" onClick={()=>{onSave(draft);setSaved(true)}}>Profil mentése</button></div></section><aside className="card profile-summary"><span className="eyebrow">ÖSSZEFOGLALÓ</span><h2>Jelenlegi profil</h2><div className="summary-name"><AvatarView profile={profile} size="large"/><div><strong>{profile.name}</strong><small>{profile.experience}</small></div></div><div className="summary-list"><div><span>Fő cél</span><b>{profile.goal}</b></div><div><span>Heti keret</span><b>{profile.weeklyHours} óra</b></div><div><span>Erő / kardió</span><b>{profile.strengthRatio}% / {100-profile.strengthRatio}%</b></div><div><span>Edzésnapok</span><b>{profile.trainingDays.join(", ")}</b></div><div><span>Pihenőnap</span><b>{profile.restDay}</b></div><div><span>Következő esemény</span><b>{eventSummary(profile)}</b></div></div></aside></div></>}

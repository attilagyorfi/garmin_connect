import { Activity, Dumbbell, TrendingUp, UserRound } from "lucide-react";

export const avatarPresets={athlete:Activity,strength:Dumbbell,endurance:TrendingUp,classic:UserRound};
export function AvatarView({profile,size="normal"}){const initials=(profile?.name||"A").split(/\s+/).map(x=>x[0]).join("").slice(0,2).toUpperCase(),Icon=avatarPresets[profile?.avatarPreset]||UserRound;return <span className={`user-avatar ${size}`}>{profile?.avatarImage?<img src={profile.avatarImage} alt={`${profile.name||"Felhasználó"} profilképe`}/>:profile?.avatarPreset?<Icon aria-hidden="true"/>:<b>{initials}</b>}</span>}

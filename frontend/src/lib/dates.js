export const dayCodes=["V","H","K","Sze","Cs","P","Szo"];
export const isoDate=date=>{const local=new Date(date);local.setMinutes(local.getMinutes()-local.getTimezoneOffset());return local.toISOString().slice(0,10)};
// The athlete's own rest day. Without a valid one, the days outside the training days count; without either, none does.
export const isPlannedRestDay=(profile,date)=>{const day=dayCodes[date.getDay()],trainingDays=profile?.trainingDays;return dayCodes.includes(profile?.restDay)?profile.restDay===day:Array.isArray(trainingDays)&&trainingDays.length>0&&!trainingDays.includes(day)};
export const days=["H","K","Sze","Cs","P","Szo","V"];
export const shiftIsoDate=(value,days)=>{const date=new Date(`${value}T12:00:00`);date.setDate(date.getDate()+Number(days));return isoDate(date)};

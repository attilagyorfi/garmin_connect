export const dayCodes=["V","H","K","Sze","Cs","P","Szo"];
export const isoDate=date=>{const local=new Date(date);local.setMinutes(local.getMinutes()-local.getTimezoneOffset());return local.toISOString().slice(0,10)};
export const days=["H","K","Sze","Cs","P","Szo","V"];
export const shiftIsoDate=(value,days)=>{const date=new Date(`${value}T12:00:00`);date.setDate(date.getDate()+Number(days));return isoDate(date)};

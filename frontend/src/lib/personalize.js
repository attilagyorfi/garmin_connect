import { defaultProfile } from "./profile.js";

const goalModes={"Futóteljesítmény":{title:"Zone 2 futás",quality:"Minőségi futóedzés",focus:"futóteljesítmény"},"Erőfejlesztés":{title:"Technikai erőedzés",quality:"Progresszív erőedzés",focus:"erőfejlesztés"},"Hegyi állóképesség":{title:"Emelkedős állóképességi edzés",quality:"Hegyi specifikus edzés",focus:"hegyi állóképesség"},"Általános egészség":{title:"Könnyű aerob átmozgatás",quality:"Kiegyensúlyozott teljes testes edzés",focus:"általános egészség"},"Hibrid teljesítmény":{title:"Zone 2 alapozás",quality:"Minőségi hibrid edzés",focus:"hibrid teljesítmény"}};
export function personalizeDashboard(data,profile,checkin){
  const safeProfile=profile||defaultProfile,base=data||{},mode=goalModes[safeProfile.goal]||goalModes["Hibrid teljesítmény"],readiness=Number(base.readiness??78),week=base.week||{};
  const sessions=base.sessions||[],latest=sessions[0]?.date?new Date(sessions[0].date):new Date(),weekStart=new Date(latest);weekStart.setDate(latest.getDate()-6);
  const recent=sessions.filter(item=>new Date(item.date)>=weekStart),actualMinutes=recent.reduce((sum,item)=>sum+Number(item.durationMin||0),0),strengthMinutes=recent.filter(item=>item.type==="Erő").reduce((sum,item)=>sum+Number(item.durationMin||0),0);
  const targetMinutes=Math.max(60,Number(safeProfile.weeklyHours||8)*60),progress=Math.min(100,Math.round(actualMinutes/targetMinutes*100)),actualStrength=actualMinutes?Math.round(strengthMinutes/actualMinutes*100):0;
  const available=Math.max(1,safeProfile.trainingDays?.length||1),dailyBudget=Math.max(25,Math.min(90,Math.round(targetMinutes/available/5)*5)),remaining=Math.max(0,targetMinutes-actualMinutes);
  const fatiguePenalty=checkin?Math.max(0,(Number(checkin.fatigue)-2)*6)+Math.max(0,(Number(checkin.stress)-3)*4)+Math.max(0,(Number(checkin.soreness)-3)*4)+Math.max(0,(3-Number(checkin.motivation))*3):0;
  const adjustedReadiness=Math.max(0,Math.round(checkin?.illness?Math.min(readiness-fatiguePenalty,30):checkin?.pain?Math.min(readiness-fatiguePenalty,45):readiness-fatiguePenalty));
  const protectedDay=adjustedReadiness<60||checkin?.illness||checkin?.pain||/regener|pihenő/i.test(base.decision?.title||"");
  const title=checkin?.illness?"Teljes pihenő":checkin?.pain?"Fájdalommentes mobilitás":protectedDay?(base.decision?.title||"Aktív regeneráció"):(adjustedReadiness>=80?mode.quality:mode.title);
  const duration=protectedDay?(base.decision?.duration||"20–45 perc"):`${Math.min(dailyBudget,Math.max(30,remaining||dailyBudget))} perc`;
  const goalReason=`A ${safeProfile.goal.toLowerCase()} célodhoz és a heti ${safeProfile.weeklyHours} órás keretedhez igazítva.`;
  const limitationNote=safeProfile.limitations?.trim()?" A megadott korlátozásaidat az edzés kiválasztásakor tartsd szem előtt.":"";
  const checkinReason=checkin?.illness?"A jelzett betegségérzet miatt ma a pihenés az elsődleges.":checkin?.pain?"A jelzett fájdalom miatt csak fájdalommentes átmozgatás javasolt.":fatiguePenalty>0?` A mai check-in ${fatiguePenalty} ponttal óvatosabbá tette az ajánlást.`:"";
  const decision={...(base.decision||{}),title,duration:checkin?.illness?"0–20 perc":duration,intensity:checkin?.illness?"pihenés":checkin?.pain?"fájdalommentes":base.decision?.intensity,rationale:`${base.decision?.rationale||"A regenerációs jelek alapján."}${checkinReason} ${goalReason}${limitationNote}`};
  const insights=[
    `${actualMinutes} perc készült el a heti ${targetMinutes} perces személyes keretedből.`,
    actualStrength<safeProfile.strengthRatio?`Az erőedzés aránya ${actualStrength}%; a célod ${safeProfile.strengthRatio}%, ezért a következő terhelhető napon érdemes erőblokkot választani.`:`Az erő–kardió arányod illeszkedik a ${safeProfile.strengthRatio}/${100-safeProfile.strengthRatio}%-os célhoz.`,
    safeProfile.eventName&&safeProfile.eventDate?`${safeProfile.eventName}: ${Math.max(0,Math.ceil((new Date(safeProfile.eventDate)-new Date())/86400000))} nap van hátra.`:`A következő ajánlások fő fókusza: ${mode.focus}.`
  ];
  return {decision,adjustedReadiness,band:adjustedReadiness>=70?"terhelhető":adjustedReadiness>=45?"óvatosan":"regeneráció",week:{actualMinutes,targetMinutes,progress,actualStrength,targetStrength:safeProfile.strengthRatio,daysDone:new Set(recent.map(x=>x.date)).size,daysTarget:available,totalLoad:week.total_load||0},insights};
}

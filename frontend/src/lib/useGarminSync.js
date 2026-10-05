import { useEffect, useRef, useState } from "react";

// Drives the resumable /api/sync job step by step; resumes a running job after a reload.
export function useGarminSync({onCompleted}={}){
  const [syncing,setSyncing]=useState(false),[job,setJob]=useState(null),[error,setError]=useState(""),completed=useRef(onCompleted);
  completed.current=onCompleted;
  const start=async(initialRunId=null)=>{setSyncing(true);setError("");let runId=initialRunId;try{for(let step=0;step<20000;step+=1){const r=await fetch("/api/sync",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(runId?{run_id:runId}:{})}),text=await r.text();let body=null;try{body=JSON.parse(text)}catch{if(r.status===404||/page could not be found|doctype/i.test(text))throw new Error("Az online Garmin-szinkron még nincs bekötve ezen az előnézeten.");throw new Error("A szinkronizáló szolgáltatás érvénytelen választ adott.")}if(!r.ok&&r.status!==202)throw new Error(body?.error||body?.message||`A szinkron nem sikerült (${r.status}).`);setJob(body);runId=body.run_id;if(body.status==="completed"){await completed.current?.();break}if(body.status==="failed")throw new Error(body.message||"A szinkron megszakadt.");await new Promise(resolve=>setTimeout(resolve,350))}}catch(e){setError(e.message||"A szinkron nem sikerült.")}finally{setSyncing(false)}};
  useEffect(()=>{fetch("/api/sync").then(r=>r.ok?r.json():null).then(value=>{if(value?.status==="running"){setJob(value);start(value.run_id)}else if(value)setJob(value)}).catch(()=>{})},[]);
  return {syncing,job,error,setError,start};
}

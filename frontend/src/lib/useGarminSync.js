import { useEffect, useRef, useState } from "react";

const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

// Drives the resumable /api/sync job step by step; resumes a running job after a reload.
// The server schedules back-off on Garmin rate limits (retry_after_seconds); a run that
// still failed keeps its progress and can be continued with its run_id (resumeRunId).
export function useGarminSync({onCompleted}={}){
  const [syncing,setSyncing]=useState(false),[job,setJob]=useState(null),[error,setError]=useState(""),completed=useRef(onCompleted);
  completed.current=onCompleted;
  const start=async(initialRunId=null)=>{setSyncing(true);setError("");let runId=initialRunId;try{for(let step=0;step<20000;step+=1){const r=await fetch("/api/sync",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(runId?{run_id:runId}:{})}),text=await r.text();let body=null;try{body=JSON.parse(text)}catch{if(r.status===404||/page could not be found|doctype/i.test(text))throw new Error("Ezen az előnézeten még nem működik a Garmin-szinkron.");throw new Error("A szinkron hibás választ kapott. Próbáld újra pár perc múlva.")}if(body?.run_id){setJob(body);runId=body.run_id}if(!r.ok&&r.status!==202)throw new Error(body?.error||body?.message||`Nem sikerült a szinkron (${r.status}). Próbáld újra pár perc múlva.`);if(body.status==="completed"){window.dispatchEvent(new Event("hybrid-dashboard-refresh"));await completed.current?.();break}if(body.status==="failed")throw new Error(body.message||"Megszakadt a szinkron. Próbáld újra.");await wait(Math.max(350,Number(body.retry_after_seconds||0)*1000))}}catch(e){setError(e.message||"Nem sikerült a szinkron. Próbáld újra pár perc múlva.")}finally{setSyncing(false)}};
  useEffect(()=>{fetch("/api/sync").then(r=>r.ok?r.json():null).then(value=>{if(value?.status==="running"){setJob(value);start(value.run_id)}else if(value)setJob(value)}).catch(()=>{})},[]);
  const resumeRunId=job?.status==="failed"&&job?.resumable?job.run_id:null;
  return {syncing,job,error,setError,start,resumeRunId};
}

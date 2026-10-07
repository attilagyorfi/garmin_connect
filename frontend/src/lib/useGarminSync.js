import { useEffect, useRef, useState } from "react";

const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

// Drives the resumable /api/sync job step by step; resumes a running job after a reload.
// The server schedules back-off on Garmin rate limits (retry_after_seconds); a run that
// still failed keeps its progress and can be continued with its run_id (resumeRunId).
export function useGarminSync({onCompleted}={}){
  const [syncing,setSyncing]=useState(false),[job,setJob]=useState(null),[error,setError]=useState(""),completed=useRef(onCompleted);
  completed.current=onCompleted;
  const start=async(initialRunId=null)=>{setSyncing(true);setError("");let runId=initialRunId;try{for(let step=0;step<20000;step+=1){const r=await fetch("/api/sync",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(runId?{run_id:runId}:{})}),text=await r.text();let body=null;try{body=JSON.parse(text)}catch{if(r.status===404||/page could not be found|doctype/i.test(text))throw new Error("Az online Garmin-szinkron még nincs bekötve ezen az előnézeten.");throw new Error("A szinkronizáló szolgáltatás érvénytelen választ adott.")}if(body?.run_id){setJob(body);runId=body.run_id}if(!r.ok&&r.status!==202)throw new Error(body?.error||body?.message||`A szinkron nem sikerült (${r.status}).`);if(body.status==="completed"){window.dispatchEvent(new Event("hybrid-dashboard-refresh"));await completed.current?.();break}if(body.status==="failed")throw new Error(body.message||"A szinkron megszakadt.");await wait(Math.max(350,Number(body.retry_after_seconds||0)*1000))}}catch(e){setError(e.message||"A szinkron nem sikerült.")}finally{setSyncing(false)}};
  useEffect(()=>{fetch("/api/sync").then(r=>r.ok?r.json():null).then(value=>{if(value?.status==="running"){setJob(value);start(value.run_id)}else if(value)setJob(value)}).catch(()=>{})},[]);
  const resumeRunId=job?.status==="failed"&&job?.resumable?job.run_id:null;
  return {syncing,job,error,setError,start,resumeRunId};
}

import { useCallback, useEffect, useRef, useState } from "react";

// Dashboard snapshot with an explicit state: "loading" | "ready" | "empty" (no sync yet) | "error".
// Reloads when a sync finishes ("hybrid-dashboard-refresh"); never substitutes sample data.
// Once there is data, a failed reload keeps it ("ready" + refreshError). Only the latest request's answer counts.
export function useDashboardState(){
  const [state,setState]=useState({status:"loading",data:null,refreshError:false}),latest=useRef(0);
  const load=useCallback(async()=>{const request=++latest.current,apply=next=>{if(request===latest.current)setState(next)},failed=()=>apply(current=>current.data?{...current,refreshError:true}:{status:"error",data:null,refreshError:false});try{const response=await fetch("/api/dashboard",{cache:"no-store"}),value=await response.json().catch(()=>null);if(response.status===404&&value?.code==="no_dashboard_data")apply({status:"empty",data:null,refreshError:false});else if(!response.ok||!value||typeof value!=="object"||Array.isArray(value))failed();else apply({status:"ready",data:value,refreshError:false})}catch{failed()}},[]);
  const reload=useCallback(()=>{setState(current=>current.data?{...current,refreshError:false}:{status:"loading",data:null,refreshError:false});return load()},[load]);
  useEffect(()=>{load();window.addEventListener("hybrid-dashboard-refresh",load);return()=>{latest.current+=1;window.removeEventListener("hybrid-dashboard-refresh",load)}},[load]);
  return {...state,reload};
}
export async function fetchCloudState(){const response=await fetch("/api/state");if(!response.ok)throw new Error("cloud-state-unavailable");return response.json()}
export async function patchCloudState(patch){const response=await fetch("/api/state",{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(patch)});if(!response.ok)throw new Error("cloud-state-save-failed");return response.json()}
export function mergeCloudState(current,patch){const next={...(current||{}),...patch};if(patch.checkin)next.checkins={...(current?.checkins||{}),[patch.checkin.date]:patch.checkin.value};if(patch.feedback)next.feedback={...(current?.feedback||{}),[patch.feedback.activityId]:patch.feedback.value};if(patch.plan)next.plans=[...(current?.plans||[]).filter(item=>item.id!==patch.plan.id),patch.plan];if(patch.plans){const replaceDates=new Set(patch.replacePlanDates||[]),plans=new Map((current?.plans||[]).filter(item=>!replaceDates.has(item.date)).map(item=>[item.id,item]));patch.plans.forEach(item=>plans.set(item.id,item));next.plans=[...plans.values()]}if(patch.deletePlan)next.plans=(current?.plans||[]).filter(item=>item.id!==patch.deletePlan);delete next.checkin;delete next.feedback;delete next.plan;delete next.deletePlan;delete next.replacePlanDates;return next}
export async function authRequest(payload){const response=await fetch("/api/auth",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}),body=await response.json().catch(()=>({}));if(!response.ok)throw Object.assign(new Error(body.error||"Ez most nem sikerült. Próbáld újra pár perc múlva."),{code:body.code||""});return body}
export function clearLocalPersonalData(){try{Object.keys(localStorage).filter(key=>key.startsWith("hybrid-")).forEach(key=>localStorage.removeItem(key))}catch{}try{sessionStorage.clear()}catch{}}

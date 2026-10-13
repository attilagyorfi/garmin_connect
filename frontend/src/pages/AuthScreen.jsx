import { useState } from "react";
import { LockKeyhole } from "lucide-react";
import brandMarkUrl from "../assets/hybrid-athlete-mark-on-dark.svg";
import { authRequest } from "../lib/api.js";

const TITLES={login:["ÜDV ÚJRA","Lépj be a dashboardodba","Bejelentkezés"],register:["SZEMÉLYES MEGHÍVÓ","Hozd létre a meghívott fiókodat","Meghívás elfogadása"],reset:["ÚJ JELSZÓ","Állíts be új jelszót","Jelszó mentése"],forgot:["ELFELEJTETT JELSZÓ","Kérj visszaállító levelet","Levél küldése"]};
const ACTIONS={reset:"reset_password",forgot:"request_password_reset"};

// Closed access: accounts are created from an admin invite link (?invite=...). Passwords are reset from an e-mailed or
// admin-made link (?auth=reset&token=...); the request answers the same whether or not the address has an account.
export function AuthScreen({onAuthenticated,notice=""}){const query=new URLSearchParams(window.location.search),inviteToken=query.get("invite")||"",authToken=query.get("token")||"",[mode,setMode]=useState(query.get("auth")==="reset"?"reset":inviteToken?"register":"login"),[name,setName]=useState(""),[email,setEmail]=useState(""),[password,setPassword]=useState(""),[error,setError]=useState(""),[message,setMessage]=useState(notice),[busy,setBusy]=useState(false);
  const switchMode=next=>{setMode(next);setError("");setMessage("")};
  const submit=async event=>{event.preventDefault();setBusy(true);setError("");setMessage("");try{const result=await authRequest({action:ACTIONS[mode]||mode,email,password,name,token:authToken,inviteToken});if(result.user){window.history.replaceState(null,"",window.location.pathname);onAuthenticated(result.user)}else{setMessage(result.message||"A kérés sikeresen megtörtént.");if(mode==="reset"){window.history.replaceState(null,"",window.location.pathname);setMode("login");setPassword("")}if(mode==="forgot")setMode("login")}}catch(reason){setError(reason.message)}finally{setBusy(false)}};
  const [eyebrow,title,action]=TITLES[mode];
  return <main className="auth-shell"><section className="auth-brand"><img src={brandMarkUrl} alt="Hybrid Athlete"/><span className="eyebrow">HYBRID ATHLETE</span><h1>A teljesítményed.<br/>Érthetően.</h1><p>Személyes edzésadatok, fejlődéstörténet és döntéstámogatás egy biztonságos fiókban.</p></section>
    <section className="auth-card card">{inviteToken&&mode!=="reset"&&<div className="auth-tabs"><button className={mode==="login"?"active":""} onClick={()=>switchMode("login")}>Bejelentkezés</button><button className={mode==="register"?"active":""} onClick={()=>switchMode("register")}>Meghívás elfogadása</button></div>}
      <span className="eyebrow">{eyebrow}</span><h2>{title}</h2>
      <form onSubmit={submit}>{mode==="register"&&<label>Név<input autoComplete="name" value={name} onChange={event=>setName(event.target.value)} required maxLength="80"/></label>}{mode!=="reset"&&<label>E-mail-cím<input type="email" autoComplete="email" value={email} onChange={event=>setEmail(event.target.value)} required/></label>}{mode!=="forgot"&&<label>{mode==="reset"?"Új jelszó":"Jelszó"}<input type="password" autoComplete={mode==="login"?"current-password":"new-password"} value={password} onChange={event=>setPassword(event.target.value)} minLength="10" required/><small>Legalább 10 karakter</small></label>}
        {message&&<p className="auth-success" role="status">{message}</p>}{error&&<p className="auth-error" role="alert">{error}</p>}
        <button className="primary" disabled={busy}>{busy?"Feldolgozás…":action}</button>
        {mode==="login"&&<button type="button" className="auth-link" onClick={()=>switchMode("forgot")}>Elfelejtetted a jelszavad?</button>}
        {mode==="login"&&<p className="auth-admin-note">Új fiók csak meghívóval nyitható.</p>}
        {mode==="forgot"&&<p className="auth-admin-note">Ha a címhez aktív fiók tartozik, egy 30 percig érvényes, egyszer használható linket küldünk.</p>}
        {(mode==="reset"||mode==="forgot")&&<button type="button" className="auth-link" onClick={()=>switchMode("login")}>Vissza a bejelentkezéshez</button>}</form>
      <p className="auth-privacy"><LockKeyhole size={15}/> A munkamenetet biztonságos, HttpOnly cookie védi. A Garmin-adataid elkülönítve maradnak.</p></section></main>}

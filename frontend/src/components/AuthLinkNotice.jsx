import { LogOut } from "lucide-react";
import brandMarkUrl from "../assets/hybrid-athlete-mark-on-dark.svg";

const KINDS = {
  verify: ["E-MAIL-MEGERŐSÍTÉS", "Ez egy e-mail-megerősítő link", "Ezzel a linkkel egy fiók e-mail-címét lehet megerősíteni."],
  reset: ["JELSZÓ-VISSZAÁLLÍTÁS", "Ez egy jelszó-visszaállító link", "Ezzel a linkkel egy fiók jelszavát lehet visszaállítani."],
  invite: ["MEGHÍVÓ", "Ez egy meghívó link", "Ezzel a linkkel új fiókot lehet létrehozni."],
};

/** Which account link (?auth=verify|reset&token=…, ?invite=…) the current URL carries, if any. */
export function pendingAuthLink(search = window.location.search) {
  const query = new URLSearchParams(search);
  if (query.get("invite")) return "invite";
  const kind = query.get("auth");
  return (kind === "verify" || kind === "reset") && query.get("token") ? kind : null;
}

// Opened while signed in, an account link must not be swallowed silently: it may belong to another account.
export function AuthLinkNotice({ kind, user, onSignOut, onStay }) {
  const [eyebrow, title, text] = KINDS[kind];
  return <main className="auth-shell"><section className="auth-brand"><img src={brandMarkUrl} alt="Hybrid Athlete"/><span className="eyebrow">HYBRID ATHLETE</span><h1>A teljesítményed.<br/>Érthetően.</h1></section>
    <section className="auth-card card"><span className="eyebrow">{eyebrow}</span><h2>{title}</h2>
      <p className="auth-admin-note">{text} Most ezzel a fiókkal vagy bent: <b>{user.email}</b>. Ha a link másik fiókhoz tartozik, jelentkezz ki, és a link magától folytatódik.</p>
      <button className="primary" onClick={onSignOut}><LogOut size={16} aria-hidden="true"/> Kijelentkezés és folytatás</button>
      <button type="button" className="auth-link" onClick={onStay}>Maradok, nem kell a link</button>
    </section></main>;
}

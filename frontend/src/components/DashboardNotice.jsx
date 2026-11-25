// What the dashboard data is doing right now (see useDashboardState). Shows nothing while up-to-date data is on screen.
export function DashboardNotice({status,refreshError=false,onRetry}){
  if(status==="loading")return <p className="dashboard-notice" role="status">Töltjük az adataidat…</p>;
  if(status==="empty")return <p className="dashboard-notice" role="status">Még nincs szinkronizált Garmin-adat. Szinkront az Áttekintés vagy a Ma oldalon indíthatsz.</p>;
  if(status!=="error"&&!refreshError)return null;
  return <div className="dashboard-notice"><p role="alert">{status==="error"?"Nem sikerült betölteni az adataidat. Próbáld újra pár perc múlva.":"Nem sikerült frissíteni az adataidat. A korábban betöltötteket látod."}</p><button type="button" onClick={onRetry}>Próbáld újra</button></div>;
}

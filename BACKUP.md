# Biztonsági mentés és visszaállítás

Az alkalmazás helyi állapota alapértelmezetten a `data/` könyvtárban van.

## Mentendő adatok

- `data/training.sqlite3`: check-inek, edzésvisszajelzések, célok, tervek és modellverziók.
- `data/garmin_cache.json`: a szinkronizált Garmin-történet.
- `data/.garmin_tokens/`: bejelentkezési tokenek; ezt csak titkosított, privát mentésbe szabad tenni.

Az alkalmazást állítsd le a SQLite-fájl másolása előtt. A mentést ne commitold Gitbe, és ne töltsd nyilvános felhőtárhelyre.

## Visszaállítás

1. Állítsd le az alkalmazást.
2. Másold vissza a fájlokat ugyanabba a `CACHE_DIR` könyvtárba.
3. Indítsd el az alkalmazást; az SQLite-sémát automatikusan az aktuális verzióra migrálja.
4. Ellenőrizd a Beállítások oldalon az aktivitás-, wellness- és modellverzió-darabszámot.

Ha csak a Garmin-cache hiányzik, az **Összes rendelkezésre álló adat** szinkronnal újraépíthető. A manuális SQLite-adatok nem építhetők újra a Garminból.

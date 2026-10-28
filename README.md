# EstLat · Delfi TV kalender

Automaatselt uuenev iPhone’i tellitav kalender Eesti klubide EstLat League mängudele, mille ülekanne on Delfi TV avalikus kavas. Igal mängul on 15 minuti meeldetuletus.

## Andmeallikad ja valik

- Liiga päris HTML: https://www.estlatbl.com/en/game-center
- Delfi kava: https://tv.delfi.ee/leht/ulekanded-kava/
- Selle lehe JavaScripti kasutatav avalik API: https://portal-feeds.api.delfi.ee/portal-feeds-proxy/v1/stream-schedule?channel=tv.delfi.ee

Kontrollitud 28.10.2026 otse mõlema veebiallika vastu: 161 liigamängu, 13 korvpalliülekannet ja 7 vastet. Liiga leht kuvab tulevaste mängude tabelit; Delfi avaldab kava piiratud ajaks. Kalender ei sisalda kõiki hooaja mänge ette: mäng lisandub siis, kui selle Delfi ülekanne on avaldatud.

Võrdlus kasutab mõlemat võistkonda ja kohalikku kuupäeva, lubades ainult selgelt määratud nimevasteid (Läti Ülikool, Riia Zelli, Riia VEF). Eurosarja mängud ei läbi liigakava kontrolli. Eesti klubide loend on failis `calendar_builder.py` ning vajab hooaja/klubide muutumisel ülevaatamist.

Algusaeg tuleb liiga kavast ajavööndis Europe/Tallinn; .ics salvestab ajad UTC-s, mistõttu iPhone kuvab need oma kohaliku ajavööndi järgi. Riia ja Tallinna kellaaeg ning suveaja reeglid ühtivad. Delfi ülekande algus võib mängu algusest erineda kuni tunni võrra; suurema vastuolu korral uuendus peatub. Lõppaeg on hinnanguliselt 2 tundi pärast algust.

## Käivitamine

Vajalik Python 3.9+ (Actions kasutab 3.12).

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
python calendar_builder.py
```

Võrguvaba kontroll salvestatud pärisandmetega:

```sh
python calendar_builder.py --fixtures tests/fixtures --output /tmp/estlat-preview
```

`docs/calendar.ics` on tellitav kalender, `docs/state.json` hoiab sündmuste stabiilseid ID-sid ja versioone ning `docs/status.json` näitab viimast edukat uuendust. Sama mängu aja muutmine uuendab olemasolevat sündmust. Eemaldatud tulevane ülekanne märgitakse tühistatuks; viimase 30 päeva ajalugu säilib. Liiga lehelt eemaldunud tulevane mäng tühistatakse samuti. Ühe allika tõrge või ootamatu vorming peatab avaldamise ja jätab senise avaliku kalendri alles. Edukas, ent tühi Delfi korvpallikava loetakse tegelikult tühjaks kavaks.

## GitHub Pages

Avalda isikliku konto avalikus repos nimega `estlat-delfi-calendar`, vaikeharu `main`. Lülita Settings → Pages → Source valikuks **GitHub Actions**. Vajadusel luba Actionsile lugemis- ja kirjutamisõigus. Käivita töövoog **Update calendar** käsitsi.

Töövoog testib, laadib mõlemad allikad, uuendab kalendri ajalugu repos ja avaldab `docs` GitHub Pagesi. Ajakava on iga 6 tunni järel minut 17 UTC; GitHub võib käivitusi edasi lükata. Avalike repode ajastatud töövood võivad pika tegevusetuse järel peatuda; kontrolli Actionsi ja `status.json` värskust.

Kalendri URL on `https://KASUTAJANIMI.github.io/estlat-delfi-calendar/calendar.ics`. Avalehe nupp avab sama aadressi `webcal:` skeemiga.

## iPhone

Ava avalehe tellimisnupp iPhone’is ja kinnita kalendri tellimine. Alternatiivina lisa Calendar rakenduses uus tellitav kalender ja kleebi kalendri HTTPS-aadress. Menüünimed sõltuvad iOS-i versioonist. Luba tellitud kalendri märguanded ja kontrolli, et „Remove Alerts” poleks sisse lülitatud. Üksik .ics faili import ei loo automaatselt uuenevat tellimust.

Server uueneb iga 6 tunni järel, kuid iPhone otsustab oma värskendussageduse. VALARM on failis kontrollitud; päris iPhone’i tellimist ja teavituse ilmumist tuleb kasutaja telefonis kontrollida.

## Kontrollid

Neli testirühma kontrollivad pärisandmete vasteid ja eurosarja välistamist, iCal-i uuesti parsimist/CRLF-i/75-baidist reamurdmist/UTF-8 teksti, UTC ja suve-/talveaega, häiret, stabiilseid UID-sid, muutuste SEQUENCE-i, tühistamist ja allikavigu. Päris HTML/API näidised on `tests/fixtures/` all; need on 28.10.2026 kontrollnäidised, mitte jooksva kalendri allikas.

Varasemas ChatGPT vestluses mainitud ZIP ei olnud selles keskkonnas saadaval. See projekt on uuesti loodud ja kontrollitud pärisallikate põhjal.

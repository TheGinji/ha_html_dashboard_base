# Dashboard Base

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Tests](https://github.com/TheGinji/ha_html_dashboard_base/actions/workflows/tests.yaml/badge.svg)](https://github.com/TheGinji/ha_html_dashboard_base/actions/workflows/tests.yaml)
[![Validate](https://github.com/TheGinji/ha_html_dashboard_base/actions/workflows/validate.yaml/badge.svg)](https://github.com/TheGinji/ha_html_dashboard_base/actions/workflows/validate.yaml)
[![Licentie: MIT](https://img.shields.io/github/license/TheGinji/ha_html_dashboard_base)](LICENSE)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-steun%20mij-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/theginji)

Draai je eigen HTML-dashboards als panelen in de zijbalk van Home Assistant, met een veilige koppeling naar alleen de entiteiten die jij per dashboard toestaat.

> **Status: vroege versie.** De automatische tests en de validatie zijn groen, maar de integratie is nog maar op één installatie geprobeerd. Schermafbeeldingen volgen. Gebruik het op eigen risico en meld problemen via Issues.

## In het kort (English)

Dashboard Base adds sidebar panels to Home Assistant, each running a single HTML file you upload. You can add up to five dashboards, each with its own file and its own list of allowed entities. A page runs in a sandboxed iframe and talks to Home Assistant only through a small bridge (`window.DashboardBase`), limited to the entities selected for that dashboard. The bridge can also read history and weather forecasts for charts, read-only and only for allowed entities. Early version, so far only tried on a single installation. The documentation below is in Dutch.

## Is dit voor jou?

**Ja, als** je zelf een dashboard als los HTML-bestand maakt (met de hand of met een AI-hulpmiddel) en dat als eigen paneel in de zijbalk wilt, zonder dat die pagina overal bij kan.

**Nee, als** je met de gewone dashboard-editor en kaarten van Home Assistant wilt werken. Gebruik dan de standaard dashboards.

Hoe het zich verhoudt tot andere manieren (op basis van hun eigen beschrijving, ik heb ze niet allemaal zelf vergeleken):

- **Webpage-dashboard of iframe-kaart met een bestand in `/config/www`:** simpel, maar zo'n pagina draait vanaf dezelfde herkomst als Home Assistant en kan in principe bij meer dan je bedoelt. Er is geen lijst met toegestane entiteiten.
- **hass_ingress:** voegt zijbalkpanelen toe voor webadressen en diensten die je al hebt. Het is niet bedoeld om een geüploade HTML-pagina met een entiteitskoppeling te draaien.
- **CasaBoard:** een aparte zelfgehoste app met editor, plus een zijbalkpaneel. Dashboard Base heeft geen editor en geen aparte server, alleen panelen voor jouw eigen bestanden.
- **Oikos:** een dashboardbouwer met losse kaarten, waaronder een HTML-kaart. Dashboard Base toont elk dashboard als één paneel van volledige grootte.

## Hoe het werkt

- Elk dashboard is een eigen instelling van de integratie, met een eigen naam, een eigen `.html`-bestand en een eigen lijst met toegestane entiteiten. Je kunt er maximaal vijf maken.
- Elk dashboard krijgt een eigen paneel in de zijbalk. Het paneel toont het bestand in een afgeschermd iframe.
- De pagina krijgt `window.DashboardBase` om standen te lezen, de geschiedenis en de weersverwachting op te vragen en services aan te roepen.
- Alleen de entiteiten die je bij dat dashboard aanvinkt zijn zichtbaar en bedienbaar. Een dashboard kan niet bij de lijst van een ander dashboard. Die controle gebeurt in Home Assistant zelf, niet alleen in de pagina.

## Installatie

**Via HACS (aangepaste repository)**

1. Open HACS, dan het menu rechtsboven, dan Aangepaste repositories.
2. Voeg `https://github.com/TheGinji/ha_html_dashboard_base` toe met het type Integration.
3. Download Dashboard Base en herstart Home Assistant.

**Handmatig:** kopieer de map `custom_components/html_dashboard_base` naar `custom_components` in je configuratiemap en herstart Home Assistant.

## Instellen

1. Ga naar Instellingen, Apparaten en diensten, Integratie toevoegen en kies Dashboard Base.
2. Kies een naam voor de zijbalk en de entiteiten die dit dashboard mag zien en bedienen.
3. Kies bij Upload HTML-dashboard je bestand. Dat kan ook later, via Configureren. Zonder bestand toont het dashboard een melding die uitlegt waar je een bestand uploadt.

Wil je nog een dashboard, bijvoorbeeld voor een andere ruimte, herhaal dan deze stappen via Integratie toevoegen. Bij het zesde dashboard stopt het formulier met een melding.

In Configureren van een dashboard (het tandwiel bij dat dashboard) zie je onder het veld Upload HTML-dashboard welk bestand er nu geladen is: de bestandsnaam, de grootte en de datum. Is de bestandsnaam niet bekend, bijvoorbeeld bij een bestand uit een oudere versie, dan zie je de titel van de pagina. Daaronder staat het vakje Verwijder HTML om het huidige bestand te wissen. Je kunt er ook de naam en de entiteiten wijzigen en een nieuw bestand kiezen. De gegevens van het huidige bestand blijven zichtbaar na het opslaan.

**Update van 0.1.x:** je bestaande dashboard wordt bij de update automatisch omgezet. Het houdt dezelfde naam, entiteiten, bestand en paneeladres. Terug naar 0.1.x kan daarna niet meer zonder de integratie te verwijderen en opnieuw toe te voegen.

Een algemeen sjabloon met demo-modus staat in [`templates/starter.html`](templates/starter.html). Download het en upload het als eerste dashboard. Open je het los in een browser, dan draait het met verzonnen gegevens.

Het sjabloon toont tegels per gebied. Een tik op een tegel schakelt, voert uit of drukt in. Een lamp die aanstaat krijgt een schuifbalk voor helderheid en, als de lamp dat kan, voor kleurtemperatuur. Een thermostaat of radiator krijgt knoppen voor de gewenste temperatuur. Bovenaan staat een grafiek van de temperatuursensoren (de laatste 24 uur) en de weersverwachting, als je die in de lijst hebt gezet en Dashboard Base 0.3.0 of nieuwer draait. Het gebruikt `registry()`, `states()`, `subscribe()`, `info()`, `call()`, `history()` en `forecast()`, dus je kunt het als voorbeeld voor je eigen bestand gebruiken.

De integratie maakt zelf geen entiteiten aan.

## Je eigen dashboard maken

Binnen het paneel bestaat `window.DashboardBase`:

```js
const entiteiten = await DashboardBase.registry();  // naam, gebied, type
const standen = await DashboardBase.states();       // huidige standen
const info = await DashboardBase.info();            // versie en domeinen die je mag bedienen
const stop = DashboardBase.subscribe((ev) => {      // bij elke wijziging
  console.log(ev.entity_id, ev.state);              // ev.state is null als de entiteit verdwijnt
});
await DashboardBase.call("light", "toggle", { entity_id: "light.voorbeeld" });

// Voor grafieken (zie hieronder):
const lijnen = await DashboardBase.history([{ entity_id: "sensor.voorbeeld" }], 24);
const verwachting = await DashboardBase.forecast("weather.voorbeeld");
```

Elke functie werkt voor het dashboard waarin je pagina draait. Je geeft zelf geen dashboard door.

Lezen is niet beperkt tot bepaalde domeinen: alles wat je aanvinkt (ook sensoren, het weer of de zon) is zichtbaar. De regels hieronder gelden alleen voor `call`:

- Het domein moet in de lijst staan: button, climate, cover, fan, humidifier, input_boolean, input_button, input_number, input_select, light, media_player, number, scene, script, select, switch, vacuum, water_heater. `info()` geeft die lijst terug als `call_domains`, zodat je hem niet in je bestand hoeft vast te zetten.
- `entity_id` is verplicht, moet bij dit dashboard toegestaan zijn en moet bij het domein passen.
- `device_id`, `area_id`, `floor_id` en `label_id` worden geweigerd, omdat je daarmee de lijst zou omzeilen.
- De aanroep loopt onder de ingelogde gebruiker.

### Geschiedenis en verwachting

Beide functies lezen alleen en werken alleen voor entiteiten in de lijst van dat dashboard. Een entiteit daarbuiten geeft de fout `not_allowed`.

`history(reeksen, uren)` geeft de geschiedenis uit de recorder van Home Assistant:

- `reeksen` is een lijst met `{ entity_id, attribute }`, maximaal 8. Met `attribute` krijg je de lijn van een kenmerk, bijvoorbeeld `current_temperature` (gemeten) en `temperature` (gewenst) van een thermostaat. Zonder `attribute` krijg je de stand zelf, zoals de waarde van een sensor.
- `uren` is 1 tot en met 168, standaard 24.
- Het antwoord is per reeks `{ entity_id, attribute, points }`, in dezelfde volgorde als je vraag. `points` is een lijst van `[tijd in milliseconden, waarde]`, maximaal 144 per reeks.
- Een waarde van `null` betekent dat er in dat stuk geen bruikbare meting was, bijvoorbeeld omdat de sensor niet beschikbaar was. Teken daar geen lijn doorheen. Een lege lijst betekent dat er helemaal geen gegevens zijn, bijvoorbeeld omdat de entiteit niet wordt vastgelegd.
- Heeft Home Assistant geen recorder, dan komt de fout `no_recorder`.

`forecast(entity_id, type)` geeft de weersverwachting van een weerentiteit:

- `type` is `hourly`, `daily` of `twice_daily`. Laat je het weg, dan wordt in die volgorde het eerste type gebruikt dat je weerintegratie geeft.
- Het antwoord is `{ type, points }`. `points` is een lijst van `[tijd in milliseconden, temperatuur, laagste temperatuur]`. De laagste temperatuur is er alleen bij `daily` en `twice_daily`, anders is die `null`.
- Bij `hourly` krijg je de komende 24 uur, inclusief het uur waar je nu in zit. Bij `daily` en `twice_daily` krijg je alle dagen die de weerintegratie geeft.
- Geeft de weerintegratie niets, dan komt de fout `no_forecast`.

Een oudere versie van de integratie kent deze twee functies niet. Controleer daarom met `typeof DashboardBase.history === "function"` voordat je ze gebruikt.

Maak er één los bestand van: lettertypen, afbeeldingen en scripts moeten in het bestand zelf zitten (bijvoorbeeld als `data:`-adres). Een klein lettertype als `data:`-adres past ruim binnen de 2 MB.

`localStorage`, `sessionStorage` en IndexedDB werken niet in het afgeschermde iframe. Bewaar dus geen voorkeuren (zoals een thema) in de pagina zelf, maar kies bij het laden een standaard.

## Veiligheid

- De pagina draait in een iframe met `sandbox="allow-scripts"`. Zonder `allow-same-origin` kan ze je Home Assistant-login niet lezen.
- Een strikte beveiligingsregel (CSP) blokkeert verbindingen naar buiten, zodat een pagina geen standen kan wegsturen.
- De lijst met toegestane entiteiten wordt in Home Assistant gecontroleerd, bij elke opdracht en per dashboard.
- Het paneel stuurt bij elke opdracht het eigen dashboard mee. Een pagina in het iframe kan dat niet zelf kiezen, dus ze kan niet bij de lijst van een ander dashboard.
- `history()` en `forecast()` lezen alleen, en alleen voor entiteiten in de lijst van dat dashboard. De antwoorden zijn klein: een beperkt aantal punten per lijn.
- De pagina wordt via de beveiligde verbinding geladen, niet via een openbaar webadres.

Wat dit niet dekt:

- Scènes en scripts die je toestaat kunnen zelf meer doen dan de lijst. Kies ze bewust.
- Een pagina kan wegnavigeren naar een ander adres. Het paneel stopt dan de koppeling, maar het eerste verzoek kan al verstuurd zijn.
- Upload alleen bestanden die je zelf hebt gemaakt of gelezen. Een kwaadaardig bestand is niet honderd procent uit te sluiten.

## Problemen oplossen

- **Geen paneel in de zijbalk:** herstart Home Assistant na het installeren en controleer of de integratie is toegevoegd.
- **Het dashboard toont een melding dat er nog geen HTML-bestand is:** upload een bestand via het tandwiel van dat dashboard, bij Upload HTML-dashboard.
- **Het paneel toont een melding over `entry_id`:** je app of browser gebruikt nog een oud paneelbestand uit de cache. Sluit de Home Assistant-app helemaal en open hem opnieuw, of ververs de pagina. Met één dashboard werkt een oud paneelbestand ook zonder die stap. Met meer dan één dashboard niet.
- **Een entiteit ontbreekt of "Niet toegestaan":** voeg de entiteit toe via Configureren van dat dashboard. Bedienen kan alleen voor de domeinen die `info()` teruggeeft.
- **Een grafiek blijft leeg:** de geschiedenis komt uit de recorder van Home Assistant. Staat de entiteit bij de uitzonderingen van de recorder, of is hij net nieuw, dan zijn er geen gegevens. Een oud paneelbestand uit de cache kent `history()` ook niet: sluit de app helemaal en open hem opnieuw.
- **Geen weersverwachting:** niet elke weerintegratie geeft uren of dagen. Kijk in Ontwikkelaarstools, Acties, bij `weather.get_forecasts`, welke types jouw weerentiteit geeft.
- **Ik kan geen dashboard meer toevoegen:** er zijn maximaal vijf. Verwijder er eerst een.
- **Melding dat het dashboard is weggenavigeerd:** haal `location.reload()`, `location.href` en links naar andere pagina's uit je bestand.
- **Lettertypen, afbeeldingen of scripts laden niet:** externe bronnen worden geblokkeerd. Zet ze in het bestand zelf.
- **Een voorkeur in je pagina (zoals het thema) is na verversen weg:** `localStorage` werkt niet in het afgeschermde iframe. Kies bij het laden een standaard, bijvoorbeeld op basis van het tijdstip.
- **Na een update ziet het paneel er nog hetzelfde uit, of staan er oude teksten in het formulier:** herstart Home Assistant en sluit de Home Assistant-app helemaal of ververs de pagina, zodat het nieuwe paneelbestand en de nieuwe vertalingen worden geladen.
- **Iets anders:** kijk in het logboek van Home Assistant en maak een Issue aan, zonder persoonlijke gegevens.

## Beperkingen

- Maximaal vijf dashboards, elk met een eigen paneel, bestand en lijst met entiteiten.
- Elk bestand mag maximaal 2 MB zijn, in UTF-8, en moet uit één HTML-bestand bestaan.
- Geen externe bronnen in de pagina.
- Geen `localStorage`, `sessionStorage` of IndexedDB in de pagina.
- Alleen services van de domeinen hierboven. Sloten, alarmen en dergelijke zitten er bewust niet bij.
- Geschiedenis: maximaal 8 lijnen tegelijk, 168 uur terug en 144 punten per lijn. De verwachting komt alleen van weerentiteiten in de lijst.
- Elk paneel is voor alle gebruikers zichtbaar, niet alleen voor beheerders. De lijst met toegestane entiteiten van een dashboard geldt voor iedereen die dat paneel opent.

## Verwijderen

Verwijder een dashboard via Instellingen, Apparaten en diensten, Dashboard Base, bij het dashboard zelf. Het geüploade bestand van dat dashboard wordt dan ook opgeruimd. De andere dashboards blijven staan. Verwijder je het laatste dashboard, dan kun je daarna eventueel de repository in HACS verwijderen.

## Kwaliteit

Aangepaste integraties hebben geen officiële kwaliteitsscore. Dit is wat we zelf hebben getoetst:

- Bij elke wijziging draaien automatische tests (pytest) met minstens 95% dekking. Ze controleren onder meer het laden en verwijderen, het omzetten van een oudere instelling, de instelling en de opties, het uploaden, meerdere dashboards naast elkaar, de koppeling met de regels voor toegestane entiteiten per dashboard, en het opvragen van geschiedenis en verwachting (met een nagebootste recorder en weerintegratie).
- Bij elke wijziging en elke week draaien de validatie van Home Assistant (Hassfest) en die van HACS.

Wat we nog niet breed hebben getoetst: andere installaties en schermformaten. Het paneel is tot nu toe op één installatie geprobeerd. De code is geschreven met hulp van een AI-hulpmiddel.

## Steun

Dashboard Base is gratis en open source. Heb je er plezier van, dan is een kopje koffie welkom, maar nooit verplicht.

[![Steun me op Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/theginji)

## Licentie

[MIT](LICENSE)

## Credits

Gemaakt door TheGinji, met hulp van Claude (Anthropic). Het paneel gebruikt de standaard `panel_custom` van Home Assistant.

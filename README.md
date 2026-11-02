# Dashboard Base

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Tests](https://github.com/TheGinji/ha_html_dashboard_base/actions/workflows/tests.yaml/badge.svg)](https://github.com/TheGinji/ha_html_dashboard_base/actions/workflows/tests.yaml)
[![Validate](https://github.com/TheGinji/ha_html_dashboard_base/actions/workflows/validate.yaml/badge.svg)](https://github.com/TheGinji/ha_html_dashboard_base/actions/workflows/validate.yaml)
[![Licentie: MIT](https://img.shields.io/github/license/TheGinji/ha_html_dashboard_base)](LICENSE)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-steun%20mij-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/theginji)

Draai je eigen HTML-dashboards als panelen in de zijbalk van Home Assistant, met een veilige koppeling naar alleen de entiteiten die jij per dashboard toestaat.

> **Status: vroege versie.** De automatische tests en de validatie zijn groen, maar de integratie is nog maar op één installatie geprobeerd. Schermafbeeldingen volgen. Gebruik het op eigen risico en meld problemen via Issues.

## In het kort (English)

Dashboard Base adds sidebar panels to Home Assistant, each running a single HTML file you upload. You can add up to five dashboards, each with its own file and its own list of allowed entities. A page runs in a sandboxed iframe and talks to Home Assistant only through a small bridge (`window.DashboardBase`), limited to the entities selected for that dashboard. Early version, so far only tried on a single installation. The documentation below is in Dutch.

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
- De pagina krijgt `window.DashboardBase` om standen te lezen en services aan te roepen.
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
3. Upload je HTML-bestand. Dat kan ook later, via Configureren. Zonder bestand zie je een korte melding dat er nog niets is geüpload.

Wil je nog een dashboard, bijvoorbeeld voor een andere ruimte, herhaal dan deze stappen via Integratie toevoegen. Bij het zesde dashboard stopt het formulier met een melding.

In Configureren van een dashboard zie je bovenaan welk bestand er nu geladen is: de titel van de pagina, de grootte en de datum van het bestand. Daar kun je ook de naam en de entiteiten wijzigen, een nieuw bestand uploaden of het huidige bestand verwijderen. Home Assistant geeft de oorspronkelijke bestandsnaam niet door, dus die kan ik niet tonen.

**Update van 0.1.x:** je bestaande dashboard wordt bij de update automatisch omgezet. Het houdt dezelfde naam, entiteiten, bestand en paneeladres. Terug naar 0.1.x kan daarna niet meer zonder de integratie te verwijderen en opnieuw toe te voegen.

Een algemeen sjabloon met demo-modus staat in [`templates/starter.html`](templates/starter.html). Download het en upload het als eerste dashboard. Open je het los in een browser, dan draait het met verzonnen gegevens.

Het sjabloon toont tegels per gebied. Een tik op een tegel schakelt, voert uit of drukt in. Een lamp die aanstaat krijgt een schuifbalk voor helderheid en, als de lamp dat kan, voor kleurtemperatuur. Een thermostaat of radiator krijgt knoppen voor de gewenste temperatuur. Het gebruikt alleen `registry()`, `states()`, `subscribe()`, `info()` en `call()`, dus je kunt het als voorbeeld voor je eigen bestand gebruiken.

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
```

Elke functie werkt voor het dashboard waarin je pagina draait. Je geeft zelf geen dashboard door.

Lezen is niet beperkt tot bepaalde domeinen: alles wat je aanvinkt (ook sensoren, het weer of de zon) is zichtbaar. De regels hieronder gelden alleen voor `call`:

- Het domein moet in de lijst staan: button, climate, cover, fan, humidifier, input_boolean, input_button, input_number, input_select, light, media_player, number, scene, script, select, switch, vacuum, water_heater. `info()` geeft die lijst terug als `call_domains`, zodat je hem niet in je bestand hoeft vast te zetten.
- `entity_id` is verplicht, moet bij dit dashboard toegestaan zijn en moet bij het domein passen.
- `device_id`, `area_id`, `floor_id` en `label_id` worden geweigerd, omdat je daarmee de lijst zou omzeilen.
- De aanroep loopt onder de ingelogde gebruiker.

Maak er één los bestand van: lettertypen, afbeeldingen en scripts moeten in het bestand zelf zitten (bijvoorbeeld als `data:`-adres). Een klein lettertype als `data:`-adres past ruim binnen de 2 MB.

`localStorage`, `sessionStorage` en IndexedDB werken niet in het afgeschermde iframe. Bewaar dus geen voorkeuren (zoals een thema) in de pagina zelf, maar kies bij het laden een standaard.

## Veiligheid

- De pagina draait in een iframe met `sandbox="allow-scripts"`. Zonder `allow-same-origin` kan ze je Home Assistant-login niet lezen.
- Een strikte beveiligingsregel (CSP) blokkeert verbindingen naar buiten, zodat een pagina geen standen kan wegsturen.
- De lijst met toegestane entiteiten wordt in Home Assistant gecontroleerd, bij elke opdracht en per dashboard.
- Het paneel stuurt bij elke opdracht het eigen dashboard mee. Een pagina in het iframe kan dat niet zelf kiezen, dus ze kan niet bij de lijst van een ander dashboard.
- De pagina wordt via de beveiligde verbinding geladen, niet via een openbaar webadres.

Wat dit niet dekt:

- Scènes en scripts die je toestaat kunnen zelf meer doen dan de lijst. Kies ze bewust.
- Een pagina kan wegnavigeren naar een ander adres. Het paneel stopt dan de koppeling, maar het eerste verzoek kan al verstuurd zijn.
- Upload alleen bestanden die je zelf hebt gemaakt of gelezen. Een kwaadaardig bestand is niet honderd procent uit te sluiten.

## Problemen oplossen

- **Geen paneel in de zijbalk:** herstart Home Assistant na het installeren en controleer of de integratie is toegevoegd.
- **Pagina met "Nog geen dashboard geüpload":** upload een bestand via Configureren van dat dashboard.
- **Een entiteit ontbreekt of "Niet toegestaan":** voeg de entiteit toe via Configureren van dat dashboard. Bedienen kan alleen voor de domeinen die `info()` teruggeeft.
- **Ik kan geen dashboard meer toevoegen:** er zijn maximaal vijf. Verwijder er eerst een.
- **Melding dat het dashboard is weggenavigeerd:** haal `location.reload()`, `location.href` en links naar andere pagina's uit je bestand.
- **Lettertypen, afbeeldingen of scripts laden niet:** externe bronnen worden geblokkeerd. Zet ze in het bestand zelf.
- **Een voorkeur in je pagina (zoals het thema) is na verversen weg:** `localStorage` werkt niet in het afgeschermde iframe. Kies bij het laden een standaard, bijvoorbeeld op basis van het tijdstip.
- **Na een update ziet het paneel er nog hetzelfde uit:** herstart Home Assistant en sluit de Home Assistant-app helemaal of ververs de pagina, zodat het nieuwe paneelbestand wordt geladen.
- **Iets anders:** kijk in het logboek van Home Assistant en maak een Issue aan, zonder persoonlijke gegevens.

## Beperkingen

- Maximaal vijf dashboards, elk met een eigen paneel, bestand en lijst met entiteiten.
- Elk bestand mag maximaal 2 MB zijn, in UTF-8, en moet uit één HTML-bestand bestaan.
- Geen externe bronnen in de pagina.
- Geen `localStorage`, `sessionStorage` of IndexedDB in de pagina.
- Alleen services van de domeinen hierboven. Sloten, alarmen en dergelijke zitten er bewust niet bij.
- Elk paneel is voor alle gebruikers zichtbaar, niet alleen voor beheerders. De lijst met toegestane entiteiten van een dashboard geldt voor iedereen die dat paneel opent.

## Verwijderen

Verwijder een dashboard via Instellingen, Apparaten en diensten, Dashboard Base, bij het dashboard zelf. Het geüploade bestand van dat dashboard wordt dan ook opgeruimd. De andere dashboards blijven staan. Verwijder je het laatste dashboard, dan kun je daarna eventueel de repository in HACS verwijderen.

## Kwaliteit

Aangepaste integraties hebben geen officiële kwaliteitsscore. Dit is wat we zelf hebben getoetst:

- Bij elke wijziging draaien automatische tests (pytest) met minstens 95% dekking. Ze controleren onder meer het laden en verwijderen, het omzetten van een oudere instelling, de instelling en de opties, het uploaden, meerdere dashboards naast elkaar, en de koppeling met de regels voor toegestane entiteiten per dashboard.
- Bij elke wijziging en elke week draaien de validatie van Home Assistant (Hassfest) en die van HACS.

Wat we nog niet breed hebben getoetst: andere installaties en schermformaten. Het paneel is tot nu toe op één installatie geprobeerd, met één dashboard. De code is geschreven met hulp van een AI-hulpmiddel.

## Steun

Dashboard Base is gratis en open source. Heb je er plezier van, dan is een kopje koffie welkom, maar nooit verplicht.

[![Steun me op Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/theginji)

## Licentie

[MIT](LICENSE)

## Credits

Gemaakt door TheGinji, met hulp van Claude (Anthropic). Het paneel gebruikt de standaard `panel_custom` van Home Assistant.

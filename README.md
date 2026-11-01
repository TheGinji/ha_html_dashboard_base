# Dashboard Base

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Licentie: MIT](https://img.shields.io/github/license/TheGinji/ha_html_dashboard_base)](LICENSE)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-steun%20mij-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/theginji)

Draai je eigen HTML-dashboard als paneel in de zijbalk van Home Assistant, met een veilige koppeling naar alleen de entiteiten die jij toestaat.

> **Status: vroege versie (0.1.0).** Het skelet staat, maar is nog niet getest op een echte installatie. Tests en schermafbeeldingen volgen. Gebruik het op eigen risico en meld problemen via Issues.

## In het kort (English)

Dashboard Base adds a sidebar panel to Home Assistant that runs a single HTML file you upload. The page runs in a sandboxed iframe and talks to Home Assistant only through a small bridge (`window.DashboardBase`), limited to the entities you select. Early version, not tested on a real installation yet. The documentation below is in Dutch.

## Is dit voor jou?

**Ja, als** je zelf een dashboard als los HTML-bestand maakt (met de hand of met een AI-hulpmiddel) en dat als eigen paneel in de zijbalk wilt, zonder dat die pagina overal bij kan.

**Nee, als** je met de gewone dashboard-editor en kaarten van Home Assistant wilt werken. Gebruik dan de standaard dashboards.

Hoe het zich verhoudt tot andere manieren (op basis van hun eigen beschrijving, ik heb ze niet allemaal zelf vergeleken):

- **Webpage-dashboard of iframe-kaart met een bestand in `/config/www`:** simpel, maar zo'n pagina draait vanaf dezelfde herkomst als Home Assistant en kan in principe bij meer dan je bedoelt. Er is geen lijst met toegestane entiteiten.
- **hass_ingress:** voegt zijbalkpanelen toe voor webadressen en diensten die je al hebt. Het is niet bedoeld om een geüploade HTML-pagina met een entiteitskoppeling te draaien.
- **CasaBoard:** een aparte zelfgehoste app met editor, plus een zijbalkpaneel. Dashboard Base heeft geen editor en geen aparte server, alleen een paneel voor jouw eigen bestand.
- **Oikos:** een dashboardbouwer met losse kaarten, waaronder een HTML-kaart. Dashboard Base is één paneel van volledige grootte.

## Hoe het werkt

- Je uploadt één `.html`-bestand via de instellingen van de integratie.
- Het paneel toont dat bestand in een afgeschermd iframe.
- De pagina krijgt `window.DashboardBase` om standen te lezen en services aan te roepen.
- Alleen de entiteiten die je zelf aanvinkt zijn zichtbaar en bedienbaar. Die controle gebeurt in Home Assistant zelf, niet alleen in de pagina.

## Installatie

**Via HACS (aangepaste repository)**

1. Open HACS, dan het menu rechtsboven, dan Aangepaste repositories.
2. Voeg `https://github.com/TheGinji/ha_html_dashboard_base` toe met het type Integration.
3. Download Dashboard Base en herstart Home Assistant.

**Handmatig:** kopieer de map `custom_components/html_dashboard_base` naar `custom_components` in je configuratiemap en herstart Home Assistant.

## Instellen

1. Ga naar Instellingen, Apparaten en diensten, Integratie toevoegen en kies Dashboard Base.
2. Kies een naam voor de zijbalk en de entiteiten die het dashboard mag zien en bedienen.
3. Upload je HTML-bestand. Dat kan ook later, via Configureren. Zonder bestand zie je een korte melding dat er nog niets is geüpload.

Een algemeen sjabloon met demo-modus staat in [`templates/starter.html`](templates/starter.html). Download het en upload het als eerste dashboard. Open je het los in een browser, dan draait het met verzonnen gegevens.

De integratie maakt zelf geen entiteiten aan.

## Je eigen dashboard maken

Binnen het paneel bestaat `window.DashboardBase`:

```js
const entiteiten = await DashboardBase.registry();  // naam, gebied, type
const standen = await DashboardBase.states();       // huidige standen
const stop = DashboardBase.subscribe((ev) => {      // bij elke wijziging
  console.log(ev.entity_id, ev.state);              // ev.state is null als de entiteit verdwijnt
});
await DashboardBase.call("light", "toggle", { entity_id: "light.voorbeeld" });
```

Regels voor `call`:

- Het domein moet in de lijst staan: button, climate, cover, fan, humidifier, input_boolean, input_button, input_number, input_select, light, media_player, number, scene, script, select, switch, vacuum, water_heater.
- `entity_id` is verplicht, moet toegestaan zijn en moet bij het domein passen.
- `device_id`, `area_id`, `floor_id` en `label_id` worden geweigerd, omdat je daarmee de lijst zou omzeilen.
- De aanroep loopt onder de ingelogde gebruiker.

Maak er één los bestand van: lettertypen, afbeeldingen en scripts moeten in het bestand zelf zitten (bijvoorbeeld als `data:`-adres).

## Veiligheid

- De pagina draait in een iframe met `sandbox="allow-scripts"`. Zonder `allow-same-origin` kan ze je Home Assistant-login niet lezen.
- Een strikte beveiligingsregel (CSP) blokkeert verbindingen naar buiten, zodat een pagina geen standen kan wegsturen.
- De lijst met toegestane entiteiten wordt in Home Assistant gecontroleerd, bij elke opdracht.
- De pagina wordt via de beveiligde verbinding geladen, niet via een openbaar webadres.

Wat dit niet dekt:

- Scènes en scripts die je toestaat kunnen zelf meer doen dan de lijst. Kies ze bewust.
- Een pagina kan wegnavigeren naar een ander adres. Het paneel stopt dan de koppeling, maar het eerste verzoek kan al verstuurd zijn.
- Upload alleen bestanden die je zelf hebt gemaakt of gelezen. Een kwaadaardig bestand is niet honderd procent uit te sluiten.

## Problemen oplossen

- **Geen paneel in de zijbalk:** herstart Home Assistant na het installeren en controleer of de integratie is toegevoegd.
- **Pagina met "Nog geen dashboard geüpload":** upload een bestand via Configureren.
- **Een entiteit ontbreekt of "Niet toegestaan":** voeg de entiteit toe via Configureren. Het domein moet in de lijst hierboven staan.
- **Melding dat het dashboard is weggenavigeerd:** haal `location.reload()`, `location.href` en links naar andere pagina's uit je bestand.
- **Lettertypen, afbeeldingen of scripts laden niet:** externe bronnen worden geblokkeerd. Zet ze in het bestand zelf.
- **Iets anders:** kijk in het logboek van Home Assistant en maak een Issue aan, zonder persoonlijke gegevens.

## Beperkingen

- Eén dashboard en één paneel per installatie.
- Het bestand mag maximaal 2 MB zijn, in UTF-8, en moet uit één HTML-bestand bestaan.
- Geen externe bronnen in de pagina.
- Alleen services van de domeinen hierboven. Sloten, alarmen en dergelijke zitten er bewust niet bij.
- Het paneel is voor alle gebruikers zichtbaar, niet alleen voor beheerders. De lijst met toegestane entiteiten geldt voor iedereen die het paneel opent.

## Verwijderen

Verwijder de integratie via Instellingen, Apparaten en diensten. Het geüploade bestand wordt dan ook opgeruimd. Verwijder daarna eventueel de repository in HACS.

## Kwaliteit

Aangepaste integraties hebben geen officiële kwaliteitsscore. Wat we tot nu toe hebben getoetst: nog niets op een echte installatie. De code is geschreven met hulp van een AI-hulpmiddel. Tests (pytest) en validatie (Hassfest en HACS) komen er nog bij. Zodra die bestaan, zie je de uitslag in de badges bovenaan.

## Steun

Dashboard Base is gratis en open source. Heb je er plezier van, dan is een kopje koffie welkom, maar nooit verplicht.

[![Steun me op Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/theginji)

## Licentie

[MIT](LICENSE)

## Credits

Gemaakt door TheGinji, met hulp van Claude (Anthropic). Het paneel gebruikt de standaard `panel_custom` van Home Assistant.

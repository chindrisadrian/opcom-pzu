# OPCOM PZU — Prețuri la 15 minute pentru Home Assistant

[![hacs][hacs-badge]][hacs] [![validare][ci-badge]][ci]

Integrare Home Assistant pentru prețurile de pe **Piața pentru Ziua Următoare (PZU)** operată de OPCOM, cu rezoluție de 15 minute. Îți arată cele 96 de intervale ale zilei (plus ziua următoare, după publicare) și îți spune **când să injectezi în rețea**: cele mai scumpe intervale, cea mai bună fereastră continuă și un semnal binar pe care îl poți lega direct la invertor.

Vine cu **propriul card personalizat** — nu ai nevoie de `apexcharts-card` sau alte resurse frontend. Cardul este înregistrat automat de integrare.

**Sursa datelor:** exportul oficial CSV OPCOM, indicele `ROPEX_DAM_15min`, în Lei/MWh brut, fără nicio ajustare.

---

## Instalare

### Prin HACS (recomandat)

1. HACS → meniul din dreapta sus → **Custom repositories**
2. URL `https://github.com/chindrisadrian/opcom-pzu`, categoria **Integration**
3. Caută **OPCOM PZU** în HACS și apasă **Download**
4. Restartează Home Assistant
5. **Settings → Devices & Services → Add Integration** → caută **OPCOM PZU**

Când o adaugi, alegi durata ferestrei de injecție, pragul de preț și percentila. Toate pot fi modificate oricând, fie din **Configure**, fie direct din entitățile `number` și `select` pe care le creează integrarea.

### Manual

Copiază folderul `custom_components/opcom_pzu/` în `/config/custom_components/` și restartează.

### Cardul

După instalare, în editorul dashboard-ului apasă **+ Add card** și caută **OPCOM PZU**. Nu trebuie să adaugi nimic la resurse — integrarea se ocupă de asta.

Dacă preferi YAML:

```yaml
type: custom:opcom-pzu-card
```

Asta e tot. Cardul își găsește automat senzorul.

| Opțiune | Implicit | Ce face |
|---|---|---|
| `entity` | detectat automat | senzorul de preț, dacă vrei să-l forțezi |
| `title` | `Pret PZU la 15 minute` | titlul cardului |
| `span` | `48h` | `48h` pentru azi + mâine, `today` doar pentru ziua curentă |
| `height` | `200` | înălțimea graficului în pixeli |

---

## Entități Create

### Senzori

| Entitate | Ce arată |
|---|---|
| `sensor.opcom_pzu_current_price` | prețul intervalului de 15 min în care te afli acum; **toate datele sunt în atribute** |
| `sensor.opcom_pzu_max_today` / `min_today` / `avg_today` | statistici pentru ziua curentă |
| `sensor.opcom_pzu_peak_hour_today` | ora celui mai scump interval |
| `sensor.opcom_pzu_max_tomorrow` | vârful de mâine, după publicare |
| `sensor.opcom_pzu_price_position_today` | percentila prețului curent (100% = cel mai scump interval al zilei) |
| `sensor.opcom_pzu_injection_window` | cea mai bună fereastră continuă, ex. `19:30 - 21:30` |
| `sensor.opcom_pzu_injection_window_price` | prețul mediu în acea fereastră |
| `sensor.opcom_pzu_next_peak` | cel mai scump interval viitor |
| `sensor.opcom_pzu_minutes_to_peak` | câte minute mai sunt până la el |
| `sensor.opcom_pzu_top_injection_hours` | cele mai scumpe 8 intervale din orizontul rămas |

### Semnale Binare

| Entitate | Când este `on` |
|---|---|
| `binary_sensor.opcom_pzu_good_moment_to_export` | **asta legi la invertor** — suntem în fereastra optimă **sau** prețul a depășit pragul |
| `binary_sensor.opcom_pzu_injection_window_active` | suntem în fereastra optimă |
| `binary_sensor.opcom_pzu_price_above_threshold` | prețul curent a depășit pragul absolut |
| `binary_sensor.opcom_pzu_price_in_top_percentile` | prețul curent se află în percentila configurată |

### Setări

| Entitate | Rol |
|---|---|
| `select.opcom_pzu_injection_window_duration` | 30 min / 1 h / 2 h / 3 h / 4 h |
| `number.opcom_pzu_injection_threshold` | prag absolut, în Lei/MWh |
| `number.opcom_pzu_injection_percentile` | prag relativ, în percentile |

Setați durata ferestrei la cât timp durează descărcarea bateriei la puterea de export dorită. Fereastra este căutată pe **orizontul rămas**: restul zilei de azi plus toată ziua de mâine, dacă prețurile sunt publicate.

---

## Automatizări

Cel mai simplu punct de plecare:

```yaml
automation:
  - alias: "OPCOM - start injectie"
    triggers:
      - trigger: state
        entity_id: binary_sensor.opcom_pzu_good_moment_to_export
        to: "on"
    conditions:
      - condition: numeric_state
        entity_id: sensor.battery_level                 # entitatea ta
        above: 30
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.inverter_battery_discharge  # entitatea ta

  - alias: "OPCOM - stop injectie"
    triggers:
      - trigger: state
        entity_id: binary_sensor.opcom_pzu_good_moment_to_export
        to: "off"
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.inverter_battery_discharge
```

Semnalul are un atribut `reason` care îți spune de ce s-a pornit — util în log-uri și notificări.

Notificare zilnică cu orele de mâine:

```yaml
automation:
  - alias: "OPCOM - orele de maine"
    triggers:
      - trigger: state
        entity_id: sensor.opcom_pzu_current_price
        attribute: tomorrow_valid
        to: true
    actions:
      - action: notify.persistent_notification
        data:
          title: "PZU Maine"
          message: >-
            Varf {{ states('sensor.opcom_pzu_max_tomorrow') }} Lei/MWh la
            {{ state_attr('sensor.opcom_pzu_max_tomorrow','hour') }}.
            Cele mai bune intervale: {{ states('sensor.opcom_pzu_top_injection_hours') }}
```

---

## Cum funcționează

Integrarea descarcă CSV-ul **o singură dată pe zi** pentru fiecare zi de livrare și ține rezultatul în memorie. La fiecare 5 minute — și exact la granița fiecărui interval de 15 minute — recalculează doar valorile derivate, fără să mai atingă OPCOM. Prețurile pentru ziua următoare sunt cerute doar după ora 12:00, cu o pauză de 10 minute între încercări, până când apar.

Timestamps sunt construite pornind de la miezul nopții locale convertite în UTC, adăugând 15 minute în UTC. Asta asigură că zilele cu schimbarea orei de vară/iarnă (care au 92 sau 100 de intervale în loc de 96) sunt calculate corect.

Atributele grele (cele 192 de intervale) sunt marcate ca **neînregistrate (unrecorded)**, deci nu îți umflă baza de date, dar rămân disponibile în timp real pentru card și template-uri.

---

## Troubleshooting

**Integrarea nu pornește.** Verifică log-ul în `Settings → System → Logs`. Pe pagina integrării ai și opțiunea **Download diagnostics**, care include ultima eroare de rețea și câte intervale au fost încărcate.

**Cardul arată "OPCOM data not yet available" sau senzorii sunt "Unavailable" imediat după instalare.** Este normal. Integrarea fie descarcă încă datele inițiale de la OPCOM, fie serverele OPCOM sunt temporar lente. Datele vor apărea automat la următoarea reîmprospătare de 5 minute, odată ce descărcarea reușește.

**`Custom element doesn't exist: opcom-pzu-card`.** Asta înseamnă că fișierul cardului nu a ajuns la browser. Verifică, în ordine:

1. Deschide `http://<adresa-ha>:8123/opcom_pzu_static/opcom-pzu-card.js` într-un tab nou. Dacă vezi codul JavaScript, serverul e în regulă și problema e doar de cache — treci la pasul 3. Dacă primești 404, mergi la pasul 2.
2. În `Settings → System → Logs`, caută `opcom_pzu`. La pornire, integrarea scrie o linie precum `The OPCOM PZU card is served at /opcom_pzu_static/...`. Dacă vezi o eroare în schimb, îți va spune exact ce lipsește.
3. Curăță cache-ul frontend-ului:
   - **În browser:** Curăță cache-ul (nu doar Ctrl+F5) — aplicația este un PWA cu service worker, care servește lista veche de resurse. Cel mai simplu test: deschide Home Assistant într-o fereastră incognito.
   - **În aplicația Companion:** Închide forțat aplicația din memoria telefonului și redeschide-o, sau mergi la App Settings și curăță cache-ul de frontend.

Ca soluție de rezervă, poți adăuga resursa manual: `Settings → Dashboards → meniul din dreapta sus → Resources → Add resource`, url `/opcom_pzu_static/opcom-pzu-card.js`, type **JavaScript Module**.

Pagina integrării are și opțiunea **Download diagnostics**, unde secțiunea `card` arată dacă fișierul a fost găsit și dacă resursa a fost înregistrată.

**Prețurile de mâine lipsesc.** Ele sunt publicate de obicei între 13:00 și 14:00 (ora României). Până atunci, atributul `tomorrow_valid` este `false` și senzorul este `Unavailable`.

**Orele sunt decalate.** Verifică fusul orar în `Settings → System → General`. Integrarea folosește timezone-ul configurat în Home Assistant.

---

## Note

Prețurile sunt **brute, de pe bursă, în Lei/MWh**, așa cum sunt publicate de OPCOM. Cât primești efectiv la injecție depinde de contractul tău — schema de prosumator sau contract dinamic, comisionul furnizorului, TVA. Pentru bani/kWh împarte la 10.

PZU este Piața pentru Ziua Următoare (DAM - Day-Ahead Market): prețurile sunt stabilite cu o zi înainte și nu se modifică. Nu este același lucru cu prețul de dezechilibru de pe piața de echilibrare (PE).

Proiect neoficial, neafiliat OPCOM SA.

---

## Dezvoltare

```bash
python3 tests/test_opcom.py       # parsare și calcul
python3 tests/test_structure.py   # manifest, traduceri, structura repo-ului
```

Licență MIT.

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[ci]: https://github.com/chindrisadrian/opcom-pzu/actions/workflows/validate.yml
[ci-badge]: https://github.com/chindrisadrian/opcom-pzu/actions/workflows/validate.yml/badge.svg

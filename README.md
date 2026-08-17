# OPCOM PZU — preturi la 15 minute pentru Home Assistant

[![hacs][hacs-badge]][hacs] [![validare][ci-badge]][ci]

Integrare Home Assistant pentru preturile din **Piata pentru Ziua Urmatoare**
operata de OPCOM, in rezolutie de 15 minute. Iti arata cele 96 de intervale ale
zilei (plus ziua urmatoare, dupa publicare) si iti spune **cand sa injectezi in
retea**: cele mai scumpe intervale, cea mai buna fereastra continua si un semnal
binar pe care il legi direct de invertor.

Vine cu **card propriu** — nu ai nevoie de apexcharts-card sau de alta resursa
de frontend. Cardul e inregistrat automat de integrare.

**Sursa datelor:** exportul CSV oficial al OPCOM, indicele `ROPEX_DAM_15min`,
in Lei/MWh brut, fara nicio ajustare.

---

## Instalare

### Prin HACS (recomandat)

1. HACS → meniul din dreapta sus → **Custom repositories**
2. Adresa `https://github.com/chindrisadrian/opcom`, categoria **Integration**
3. Cauta **OPCOM PZU** in HACS si apasa **Download**
4. Reporneste Home Assistant
5. **Settings → Devices & Services → Add Integration** → cauta **OPCOM PZU**

La adaugare alegi durata ferestrei de injectie, pragul de pret si percentila.
Toate se pot schimba oricand, fie din **Configure**, fie direct din entitatile
`number` si `select` pe care le creeaza integrarea.

### Manual

Copiaza folderul `custom_components/opcom_pzu/` in `/config/custom_components/`
si reporneste.

### Cardul

Dupa instalare, in editorul de dashboard apasa **+ Add card** si cauta
**OPCOM PZU**. Nu trebuie sa adaugi nimic la resurse — integrarea se ocupa.

Daca preferi YAML:

```yaml
type: custom:opcom-pzu-card
```

Atat. Cardul isi gaseste singur senzorul.

| Optiune | Implicit | Ce face |
|---|---|---|
| `entity` | detectat automat | senzorul de pret, daca vrei sa-l fixezi |
| `title` | `Pret PZU la 15 minute` | titlul cardului |
| `span` | `48h` | `48h` pentru azi + maine, `today` doar pentru ziua curenta |
| `height` | `200` | inaltimea graficului in pixeli |

---

## Entitatile create

### Senzori

| Entitate | Ce arata |
|---|---|
| `sensor.opcom_pzu_pret_curent` | pretul intervalului de 15 min in care esti acum; **toate datele sunt in atribute** |
| `sensor.opcom_pzu_maxim_azi` / `minim_azi` / `mediu_azi` | statistici pe ziua curenta |
| `sensor.opcom_pzu_ora_de_varf_azi` | ora celui mai scump interval |
| `sensor.opcom_pzu_maxim_maine` | varful de maine, dupa publicare |
| `sensor.opcom_pzu_pozitie_pret_azi` | percentila pretului curent (100 % = cel mai scump interval al zilei) |
| `sensor.opcom_pzu_fereastra_injectie` | cea mai buna fereastra continua, ex. `19:30 - 21:30` |
| `sensor.opcom_pzu_pret_fereastra_injectie` | pretul mediu din acea fereastra |
| `sensor.opcom_pzu_urmatorul_varf` | cel mai scump interval care urmeaza |
| `sensor.opcom_pzu_minute_pana_la_varf` | cate minute mai sunt pana la el |
| `sensor.opcom_pzu_ore_top_injectie` | cele mai scumpe 8 intervale din orizontul ramas |

### Semnale binare

| Entitate | Cand e `on` |
|---|---|
| `binary_sensor.opcom_pzu_moment_bun_injectie` | **acesta se leaga de invertor** — suntem in fereastra optima **sau** pretul a trecut de prag |
| `binary_sensor.opcom_pzu_fereastra_injectie_activa` | suntem in interiorul ferestrei optime |
| `binary_sensor.opcom_pzu_pret_peste_prag` | pretul curent a trecut de pragul absolut |
| `binary_sensor.opcom_pzu_pret_in_top_percentila` | pretul curent e in percentila configurata |

### Reglaje

| Entitate | Rol |
|---|---|
| `select.opcom_pzu_durata_fereastra_injectie` | 30 min / 1 h / 2 h / 3 h / 4 h |
| `number.opcom_pzu_prag_injectie` | pragul absolut, in Lei/MWh |
| `number.opcom_pzu_percentila_injectie` | pragul relativ, in percentile |

Pune durata ferestrei pe cat timp iti ia sa golesti bateria la puterea de export
dorita. Fereastra e cautata pe **orizontul ramas**: restul zilei de azi plus
toata ziua de maine, daca preturile sunt publicate.

> **Despre `entity_id`-uri:** numele entitatilor vin din traduceri, deci
> identificatorii de mai sus apar asa daca interfata ta e pe romana. Pe o
> instalare in engleza vor fi `sensor.opcom_pzu_current_price`,
> `binary_sensor.opcom_pzu_good_moment_to_export` s.a.m.d. Le vezi si le poti
> redenumi in **Settings → Devices & Services → Entities**.

---

## Automatizari

Cel mai simplu punct de plecare:

```yaml
automation:
  - alias: "OPCOM - porneste injectia"
    triggers:
      - trigger: state
        entity_id: binary_sensor.opcom_pzu_moment_bun_injectie
        to: "on"
    conditions:
      - condition: numeric_state
        entity_id: sensor.baterie_nivel                 # entitatea ta
        above: 30
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.invertor_descarcare_baterie # entitatea ta

  - alias: "OPCOM - opreste injectia"
    triggers:
      - trigger: state
        entity_id: binary_sensor.opcom_pzu_moment_bun_injectie
        to: "off"
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.invertor_descarcare_baterie
```

Semnalul are un atribut `motiv` care spune de ce s-a aprins — util in jurnal si
in notificari.

Notificare zilnica cu orele de maine:

```yaml
automation:
  - alias: "OPCOM - orele de maine"
    triggers:
      - trigger: state
        entity_id: sensor.opcom_pzu_pret_curent
        attribute: tomorrow_valid
        to: true
    actions:
      - action: notify.persistent_notification
        data:
          title: "PZU maine"
          message: >-
            Varf {{ states('sensor.opcom_pzu_maxim_maine') }} Lei/MWh la
            {{ state_attr('sensor.opcom_pzu_maxim_maine','ora') }}.
            Cele mai bune intervale: {{ states('sensor.opcom_pzu_ore_top_injectie') }}
```

---

## Cum functioneaza

Integrarea descarca CSV-ul **o singura data pe zi** pentru fiecare zi de livrare
si tine rezultatul in memorie. La fiecare 5 minute — si exact la granita fiecarui
interval de 15 minute — recalculeaza doar valorile derivate, fara sa mai atinga
OPCOM. Preturile pentru ziua urmatoare sunt cerute doar dupa ora 12:00, cu o
pauza de 10 minute intre incercari, pana cand apar.

Marcajele de timp se construiesc pornind de la miezul noptii local convertit in
UTC, adunand cate 15 minute in UTC. Asa ies corect si zilele cu schimbare de ora,
care au 92 sau 100 de intervale in loc de 96.

Atributele grele (cele 192 de intervale) sunt marcate ca **neinregistrate**, deci
nu umfla baza de date, dar raman disponibile in timp real pentru card si pentru
sabloane.

---

## Depanare

**Integrarea nu porneste.** Verifica jurnalul din `Settings → System → Logs`.
Pe pagina integrarii ai si **Download diagnostics**, care include ultima eroare
de retea si cate intervale au fost incarcate.

**`Custom element doesn't exist: opcom-pzu-card`.** Inseamna ca fisierul cardului
nu a ajuns in browser. Verifica, in ordine:

1. Deschide intr-un tab `http://<adresa-ta-ha>:8123/opcom_pzu_static/opcom-pzu-card.js`.
   Daca vezi codul JavaScript, serverul e in regula si problema e doar de cache —
   treci la pasul 3. Daca primesti 404, treci la pasul 2.
2. In `Settings → System → Logs`, cauta `opcom_pzu`. La pornire, integrarea scrie
   o linie de tip `Cardul OPCOM PZU este servit la /opcom_pzu_static/...`. Daca in
   loc de ea vezi o eroare, aceasta iti spune exact ce lipseste.
3. Goleste cache-ul browserului pentru Home Assistant, nu doar Ctrl+F5 — aplicatia
   e un PWA cu service worker, care serveste vechea lista de resurse. Cel mai
   simplu test: deschide Home Assistant intr-o fereastra privata.

Ca solutie de rezerva poti adauga resursa manual: `Settings → Dashboards →
meniul din dreapta sus → Resources → Add resource`, adresa
`/opcom_pzu_static/opcom-pzu-card.js`, tipul **JavaScript Module**.

Pagina integrarii are si **Download diagnostics**, unde sectiunea `card` arata
daca fisierul a fost gasit si daca resursa a fost inregistrata.

**Preturile de maine lipsesc.** Sunt publicate de regula intre 13:00 si 14:00.
Pana atunci atributul `tomorrow_valid` este `false`.

**Orele sunt decalate.** Verifica fusul orar din `Settings → System → General`.
Integrarea foloseste fusul configurat in Home Assistant.

---

## Note

Preturile sunt **brute, de bursa, in Lei/MWh**, asa cum le publica OPCOM. Ce
incasezi efectiv la injectie depinde de contractul tau — schema de prosumator sau
contract dinamic, comisionul furnizorului, TVA. Pentru bani/kWh imparte la 10.

PZU este piata pentru ziua urmatoare: preturile se stabilesc cu o zi inainte si
nu se mai schimba. Nu e acelasi lucru cu pretul de dezechilibru din piata de
echilibrare.

Proiect neoficial, fara nicio legatura cu OPCOM SA.

---

## Dezvoltare

```bash
python3 tests/test_opcom.py       # parsare si calcul
python3 tests/test_structure.py   # manifest, traduceri, structura repo
```

Licenta MIT.

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[ci]: https://github.com/chindrisadrian/opcom/actions/workflows/validate.yml
[ci-badge]: https://github.com/chindrisadrian/opcom/actions/workflows/validate.yml/badge.svg

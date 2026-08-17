# OPCOM PZU — 15-minute prices for Home Assistant

[![hacs][hacs-badge]][hacs] [![validare][ci-badge]][ci]

Home Assistant integration for prices from the **Day-Ahead Market** operated by OPCOM, in 15-minute resolution. It shows you the 96 intervals of the day (plus the next day, after publication) and tells you **when to inject into the grid**: the most expensive intervals, the best continuous window, and a binary signal that you can link directly to your inverter.

It comes with its **own custom card** — you don't need `apexcharts-card` or any other frontend resource. The card is registered automatically by the integration.

**Data source:** the official OPCOM CSV export, the `ROPEX_DAM_15min` index, in gross Lei/MWh, without any adjustment.

---

## Installation

### Via HACS (recommended)

1. HACS → top right menu → **Custom repositories**
2. URL `https://github.com/chindrisadrian/opcom-pzu`, category **Integration**
3. Search for **OPCOM PZU** in HACS and click **Download**
4. Restart Home Assistant
5. **Settings → Devices & Services → Add Integration** → search for **OPCOM PZU**

When adding, you choose the injection window duration, the price threshold, and the percentile. They can all be changed at any time, either from **Configure**, or directly from the `number` and `select` entities that the integration creates.

### Manual

Copy the `custom_components/opcom_pzu/` folder into `/config/custom_components/` and restart.

### The Card

After installation, in the dashboard editor click **+ Add card** and search for **OPCOM PZU**. You don't need to add anything to resources — the integration handles it.

If you prefer YAML:

```yaml
type: custom:opcom-pzu-card
```

That's it. The card finds its sensor automatically.

| Option | Default | What it does |
|---|---|---|
| `entity` | automatically detected | the price sensor, if you want to pin it |
| `title` | `Pret PZU la 15 minute` | card title |
| `span` | `48h` | `48h` for today + tomorrow, `today` for just the current day |
| `height` | `200` | graph height in pixels |

---

## Created Entities

### Sensors

| Entity | What it shows |
|---|---|
| `sensor.opcom_pzu_current_price` | the price of the 15-min interval you are in right now; **all data is in attributes** |
| `sensor.opcom_pzu_max_today` / `min_today` / `avg_today` | statistics for the current day |
| `sensor.opcom_pzu_peak_hour_today` | the time of the most expensive interval |
| `sensor.opcom_pzu_max_tomorrow` | tomorrow's peak, after publication |
| `sensor.opcom_pzu_price_position_today` | current price percentile (100% = the most expensive interval of the day) |
| `sensor.opcom_pzu_injection_window` | the best continuous window, e.g. `19:30 - 21:30` |
| `sensor.opcom_pzu_injection_window_price` | the average price in that window |
| `sensor.opcom_pzu_next_peak` | the most expensive upcoming interval |
| `sensor.opcom_pzu_minutes_to_peak` | how many minutes are left until it |
| `sensor.opcom_pzu_top_injection_hours` | the 8 most expensive intervals in the remaining horizon |

### Binary Signals

| Entity | When it is `on` |
|---|---|
| `binary_sensor.opcom_pzu_good_moment_to_export` | **this is what you link to the inverter** — we are in the optimal window **or** the price has crossed the threshold |
| `binary_sensor.opcom_pzu_injection_window_active` | we are inside the optimal window |
| `binary_sensor.opcom_pzu_price_above_threshold` | the current price has crossed the absolute threshold |
| `binary_sensor.opcom_pzu_price_in_top_percentile` | the current price is in the configured percentile |

### Settings

| Entity | Role |
|---|---|
| `select.opcom_pzu_injection_window_duration` | 30 min / 1 h / 2 h / 3 h / 4 h |
| `number.opcom_pzu_injection_threshold` | absolute threshold, in Lei/MWh |
| `number.opcom_pzu_injection_percentile` | relative threshold, in percentiles |

Set the window duration to how long it takes to empty your battery at the desired export power. The window is searched on the **remaining horizon**: the rest of today plus all of tomorrow, if the prices are published.

---

## Automations

The simplest starting point:

```yaml
automation:
  - alias: "OPCOM - start injection"
    triggers:
      - trigger: state
        entity_id: binary_sensor.opcom_pzu_good_moment_to_export
        to: "on"
    conditions:
      - condition: numeric_state
        entity_id: sensor.battery_level                 # your entity
        above: 30
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.inverter_battery_discharge  # your entity

  - alias: "OPCOM - stop injection"
    triggers:
      - trigger: state
        entity_id: binary_sensor.opcom_pzu_good_moment_to_export
        to: "off"
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.inverter_battery_discharge
```

The signal has a `reason` attribute which tells you why it turned on — useful in logs and notifications.

Daily notification with tomorrow's hours:

```yaml
automation:
  - alias: "OPCOM - tomorrow's hours"
    triggers:
      - trigger: state
        entity_id: sensor.opcom_pzu_current_price
        attribute: tomorrow_valid
        to: true
    actions:
      - action: notify.persistent_notification
        data:
          title: "DAM Tomorrow"
          message: >-
            Peak {{ states('sensor.opcom_pzu_max_tomorrow') }} Lei/MWh at
            {{ state_attr('sensor.opcom_pzu_max_tomorrow','hour') }}.
            Best intervals: {{ states('sensor.opcom_pzu_top_injection_hours') }}
```

---

## How it works

The integration downloads the CSV **only once a day** for each delivery day and keeps the result in memory. Every 5 minutes — and exactly at the boundary of each 15-minute interval — it recalculates only the derived values, without touching OPCOM again. Prices for the next day are requested only after 12:00, with a 10-minute pause between attempts, until they appear.

Timestamps are built starting from local midnight converted to UTC, adding 15 minutes in UTC. This ensures days with daylight saving time changes (which have 92 or 100 intervals instead of 96) are calculated correctly.

Heavy attributes (the 192 intervals) are marked as **unrecorded**, so they don't bloat your database, but remain available in real-time for the card and templates.

---

## Troubleshooting

**The integration doesn't start.** Check the log in `Settings → System → Logs`. On the integration page you also have **Download diagnostics**, which includes the last network error and how many intervals were loaded.

**`Custom element doesn't exist: opcom-pzu-card`.** This means the card file didn't reach the browser. Check, in order:

1. Open `http://<your-ha-address>:8123/opcom_pzu_static/opcom-pzu-card.js` in a tab. If you see the JavaScript code, the server is fine and the problem is just caching — skip to step 3. If you get a 404, go to step 2.
2. In `Settings → System → Logs`, search for `opcom_pzu`. At startup, the integration writes a line like `The OPCOM PZU card is served at /opcom_pzu_static/...`. If you see an error instead, it tells you exactly what's missing.
3. Clear the browser cache for Home Assistant, not just Ctrl+F5 — the app is a PWA with a service worker, which serves the old list of resources. The simplest test: open Home Assistant in an incognito window.

As a fallback you can add the resource manually: `Settings → Dashboards → top right menu → Resources → Add resource`, url `/opcom_pzu_static/opcom-pzu-card.js`, type **JavaScript Module**.

The integration page also has **Download diagnostics**, where the `card` section shows if the file was found and if the resource was registered.

**Tomorrow's prices are missing.** They are usually published between 13:00 and 14:00. Until then the `tomorrow_valid` attribute is `false`.

**Hours are shifted.** Check the time zone in `Settings → System → General`. The integration uses the timezone configured in Home Assistant.

---

## Notes

Prices are **raw, from the exchange, in Lei/MWh**, as published by OPCOM. What you actually earn upon injection depends on your contract — prosumer scheme or dynamic contract, supplier commission, VAT. For money/kWh divide by 10.

DAM is the Day-Ahead Market: prices are set one day in advance and do not change. It is not the same as the imbalance price from the balancing market.

Unofficial project, not affiliated with OPCOM SA.

---

## Development

```bash
python3 tests/test_opcom.py       # parsing and calculation
python3 tests/test_structure.py   # manifest, translations, repo structure
```

MIT License.

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[ci]: https://github.com/chindrisadrian/opcom-pzu/actions/workflows/validate.yml
[ci-badge]: https://github.com/chindrisadrian/opcom-pzu/actions/workflows/validate.yml/badge.svg

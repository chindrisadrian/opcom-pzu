"""Teste offline pentru logica OPCOM, cu date reale din 18/08/2026.

Ruleaza cu:  python3 tests/test_opcom.py
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "opcom_pzu"))
import opcom  # noqa: E402

TZ = ZoneInfo("Europe/Bucharest")

PRICES = [985.42,943.70,879.91,831.44,876.47,849.12,838.99,786.92,799.91,786.94,
          784.77,791.41,777.83,770.72,777.00,786.93,778.15,771.05,782.87,797.73,
          771.42,817.95,836.06,910.12,903.94,993.47,1000.09,1019.30,1039.54,1013.72,
          990.31,839.77,1055.96,1028.59,943.85,856.49,915.34,880.79,693.38,601.99,
          785.73,785.82,715.40,706.70,711.53,706.55,707.22,692.16,670.24,706.67,
          715.28,707.81,713.63,709.08,708.04,697.37,698.43,698.85,708.08,708.20,
          700.40,688.20,708.02,740.47,700.89,718.98,732.65,782.89,727.19,820.87,
          906.84,1036.69,899.22,936.88,1024.65,1103.85,1006.75,1029.16,1089.75,1154.43,
          1101.38,1080.34,1086.86,1107.62,1142.50,1111.44,1027.90,980.66,1049.95,1022.50,
          987.13,954.67,1004.25,932.81,913.71,864.67]

HEADER = ('"Zona de tranzactionare","Interval","Pret de Inchidere a Pietei [lei/MWh]",'
          '"Volum Tranzactionat [MW]","Volum Tranzactionat pe cumparare [MW]",'
          '"Volum Tranzactionat pe vanzare [MW]","Rezolutie"')


def make_csv(prices, tag="PT15M"):
    lines = ['"Data de livrare: 18/08/2026"', "", HEADER]
    for i, p in enumerate(prices, start=1):
        lines.append(f'"Romania","{i}","{p:.2f}","1500.0","1500.0","1500.0","{tag}"')
    lines += ["", '"ROPEX_DAM_Base*","(1-96)","860.83","40572.4"',
              '"ROPEX_DAM_Peak*","(33-80)","807.04","20942.2"',
              '"ROPEX_DAM_Off_peak*","(1-32) & (81-96)","914.61","19630.2"']
    return "\n".join(lines)


ok = True


def check(label, cond, extra=""):
    global ok
    print(("PASS  " if cond else "FAIL  ") + label + (f"   {extra}" if extra else ""))
    if not cond:
        ok = False


# ---- parsare --------------------------------------------------------------
day = date(2026, 8, 18)
slots = opcom.parse_csv(make_csv(PRICES), day, TZ)

check("96 intervale parsate", len(slots) == 96, f"got {len(slots)}")
check("blocul de sinteza ROPEX ignorat", all(1 <= s["interval"] <= 96 for s in slots))
check("interval 1 = 00:00 la +03:00",
      slots[0]["hour"] == "00:00" and slots[0]["start"].endswith("+03:00"), slots[0]["start"])
check("interval 1 pret corect", slots[0]["value"] == 985.42)
check("interval 96 = 23:45", slots[-1]["hour"] == "23:45")
check("ultimul end = 00:00 ziua urmatoare", slots[-1]["end"][:16].endswith("19T00:00"),
      slots[-1]["end"])
check("intervale contigue de 15 min",
      all(slots[i]["ts"] + 900 == slots[i + 1]["ts"] for i in range(95)))

# ---- statistici, verificate fata de indicii publicati de OPCOM ------------
st = opcom.day_stats(slots)
check("media = ROPEX_DAM_Base publicat (860.83)", abs(st["mean"] - 860.83) < 0.02,
      f"got {st['mean']}")
check("maxim 1154.43 la 19:45", st["max"] == 1154.43 and st["max_hour"] == "19:45")
check("minim 601.99 la 09:45", st["min"] == 601.99 and st["min_hour"] == "09:45")
check("Peak (33-80) = 807.04 publicat", abs(sum(PRICES[32:80]) / 48 - 807.04) < 0.02)
check("Off-peak = 914.61 publicat",
      abs((sum(PRICES[:32]) + sum(PRICES[80:])) / 48 - 914.61) < 0.02)

# ---- ferestre -------------------------------------------------------------
w2 = opcom.best_window(slots, 2)
brute = max(((i, sum(PRICES[i:i + 8]) / 8) for i in range(89)), key=lambda t: t[1])
check("fereastra 2h = optimul prin forta bruta",
      abs(w2["avg"] - brute[1]) < 0.01 and w2["from"] == slots[brute[0]]["hour"],
      f"{w2['label']} avg {w2['avg']}")
w1 = opcom.best_window(slots, 1)
b1 = max(((i, sum(PRICES[i:i + 4]) / 4) for i in range(93)), key=lambda t: t[1])
check("fereastra 1h = optimul prin forta bruta", abs(w1["avg"] - b1[1]) < 0.01, w1["label"])
check("fereastra mai lunga decat datele => None", opcom.best_window(slots[:4], 3) is None)
check("toate duratele configurabile produc o fereastra",
      all(opcom.best_window(slots, h) is not None for h, _ in opcom.WINDOW_SPECS))

tops = opcom.top_slots(slots, 8)
check("top 8 sortate cronologic", [t["start"] for t in tops] == sorted(t["start"] for t in tops))
check("top 8 = cele mai scumpe 8",
      sorted((t["value"] for t in tops), reverse=True) == sorted(PRICES, reverse=True)[:8])

# ---- schimbarea orei ------------------------------------------------------
oct_slots = opcom.parse_csv(make_csv([700.0] * 100), date(2026, 10, 25), TZ)
check("25/10/2026 are 100 intervale", len(oct_slots) == 100)
check("25/10 incepe +03:00 si se termina +02:00",
      oct_slots[0]["start"].endswith("+03:00") and oct_slots[-1]["end"].endswith("+02:00"))
check("25/10 se incheie la 00:00 pe 26", oct_slots[-1]["end"][:16].endswith("26T00:00"))

mar_slots = opcom.parse_csv(make_csv([700.0] * 92), date(2026, 3, 29), TZ)
check("29/03/2026 are 92 intervale", len(mar_slots) == 92)
check("29/03 se incheie la 00:00 pe 30", mar_slots[-1]["end"][:16].endswith("30T00:00"))

# ---- date proaste ---------------------------------------------------------
check("CSV gol => lista goala", opcom.parse_csv("", day, TZ) == [])
check("alta zona ignorata",
      opcom.parse_csv(HEADER + '\n"Ungaria","1","10","1","1","1","PT15M"', day, TZ) == [])
check("alta rezolutie ignorata", opcom.parse_csv(make_csv(PRICES[:24], tag="PT60M"), day, TZ) == [])
check("format romanesc acceptat",
      opcom.parse_csv(HEADER + '\n"Romania","1","1.074,94","1153.1","1","1","PT15M"',
                      day, TZ)[0]["value"] == 1074.94)
check("HTML in loc de CSV => lista goala",
      opcom.parse_csv("<html><body>eroare</body></html>", day, TZ) == [])

# ---- payload complet ------------------------------------------------------
now = datetime(2026, 8, 18, 14, 7, tzinfo=TZ)
tomorrow = opcom.parse_csv(make_csv(list(reversed(PRICES))), date(2026, 8, 19), TZ)
p = opcom.build_payload(slots, tomorrow, now)

check("state = pretul intervalului curent", p["state"] == PRICES[56], str(p["state"]))
check("interval curent = 57", p["current_interval"] == 57 and p["current_hour"] == "14:00")
check("azi si maine valide", p["today_valid"] and p["tomorrow_valid"])
check("orizont = 40 azi + 96 maine", p["horizon_slots"] == 136, str(p["horizon_slots"]))
check("rang corect", p["current_rank_today"] == sorted(PRICES, reverse=True).index(PRICES[56]) + 1)
check("ferestrele incep in orizont", p["best_window_1h"]["start"] >= "2026-08-18T14:00")
check("intervalele de maine sunt etichetate",
      any("(maine)" in s["label"] for s in p["best_slots"]))
check("intervalele de azi nu sunt etichetate gresit",
      all("(maine)" not in s["label"] for s in p["best_slots"] if s["start"].startswith("2026-08-18")))
check("toate cheile asteptate exista",
      all(k in p for k in ("raw_today", "raw_tomorrow", "today", "tomorrow", "best_slots",
                           "next_peak", "horizon_mean", "horizon_p75", "horizon_p90",
                           *(key for _, key in opcom.WINDOW_SPECS))))
check("payload serializabil JSON", isinstance(json.dumps(p), str))
check("payload sub 24 KB", len(json.dumps(p)) < 24000, f"{len(json.dumps(p))} bytes")

# fara datele de maine
p2 = opcom.build_payload(slots, [], now)
check("fara maine: tomorrow_valid False", p2["tomorrow_valid"] is False)
check("fara maine: orizont 40", p2["horizon_slots"] == 40)
check("fara maine: fara etichete (maine)",
      all("(maine)" not in s["label"] for s in p2["best_slots"]))

# fara niciun fel de date
p3 = opcom.build_payload([], [], now)
check("fara date: state None", p3["state"] is None)
check("fara date: fara exceptie si JSON valid", isinstance(json.dumps(p3), str))
check("fara date: ferestrele sunt None",
      all(p3[key] is None for _, key in opcom.WINDOW_SPECS))

# la miezul noptii, ultimul interval al zilei
midnight = datetime(2026, 8, 18, 23, 50, tzinfo=TZ)
p4 = opcom.build_payload(slots, tomorrow, midnight)
check("23:50 => intervalul 96", p4["current_interval"] == 96, str(p4["current_interval"]))
check("23:50 => orizontul contine ziua urmatoare", p4["horizon_slots"] == 97,
      str(p4["horizon_slots"]))

# ---- URL ------------------------------------------------------------------
check("URL construit corect",
      opcom.build_url(date(2026, 8, 5)).endswith("/05/08/2026/ro?resolution=15"),
      opcom.build_url(date(2026, 8, 5)))

print("\n" + ("TOATE TESTELE AU TRECUT" if ok else "EXISTA TESTE PICATE"))
sys.exit(0 if ok else 1)

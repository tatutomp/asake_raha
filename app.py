"""Flask-sovellus: volatiilien osakkeiden yön-yli-strategian dashboard.

Reitit:
  GET  /                     -> dashboard
  POST /api/recommend-buy    -> 5 ostokohdetta (aja ~20 min ennen sulkua)
  POST /api/recommend-sell   -> myyntiarvio eilisistä (aja ~20 min avauksen jälkeen)
  GET  /api/history          -> kaikki tallennetut suositukset
  GET  /api/latest           -> uusin merkintä

VAROITUS: Opetus- ja analyysityökalu. EI sijoitusneuvontaa.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template

import analyzer

app = Flask(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
PORTFOLIO_SIZE = 5


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_history() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_history(history: list) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = HISTORY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    os.replace(tmp, HISTORY_FILE)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/recommend-buy", methods=["POST"])
def recommend_buy():
    """Analysoi universumi ja tallenna päivän 5 ostokohdetta."""
    metrics = analyzer.analyze_universe()
    if not metrics:
        return jsonify({"error": "Dataa ei saatu ladattua. Yritä uudelleen."}), 502

    portfolio = analyzer.pick_portfolio(metrics, PORTFOLIO_SIZE)
    charts = analyzer.fetch_week_history([m.ticker for m in portfolio])
    entry = {
        "date": _today(),
        "created_at": _now_iso(),
        "status": "open",
        "portfolio": [
            {
                **m.to_dict(),
                "buy_price": m.price,
                "reason": analyzer.reason_text(m),
                "history": charts.get(m.ticker, []),
            }
            for m in portfolio
        ],
        "sells": [],
        "universe_size": len(metrics),
    }

    history = load_history()
    # Korvaa saman päivän mahdollinen aiempi avoin osto-osio
    history = [h for h in history
               if not (h["date"] == entry["date"] and h["status"] == "open")]
    history.insert(0, entry)
    save_history(history)
    return jsonify(entry)


@app.route("/api/recommend-sell", methods=["POST"])
def recommend_sell():
    """Arvioi uusin avoin positio-osio ja anna myyntisuositukset."""
    history = load_history()
    open_entry = next((h for h in history if h["status"] == "open"), None)
    if open_entry is None:
        return jsonify({"error": "Ei avoimia positioita. Tee ensin osto-suositus."}), 400

    positions = [
        {
            "ticker": p["ticker"],
            "buy_price": p.get("buy_price", p.get("price")),
            "buy_date": open_entry["date"],
        }
        for p in open_entry["portfolio"]
    ]
    sells = analyzer.evaluate_sells(positions)

    total_gap = [s["gap_pct"] for s in sells if s.get("gap_pct") is not None]
    avg_gap = round(sum(total_gap) / len(total_gap), 2) if total_gap else None

    open_entry["sells"] = sells
    open_entry["status"] = "closed"
    open_entry["closed_at"] = _now_iso()
    open_entry["avg_overnight_gap_pct"] = avg_gap
    save_history(history)
    return jsonify(open_entry)


@app.route("/api/history")
def api_history():
    return jsonify(load_history())


@app.route("/api/latest")
def api_latest():
    history = load_history()
    return jsonify(history[0] if history else None)


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    print("Avaa selaimessa: http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)

# 📈 Volatiliteetti-skanneri — yön yli -strategia

Web-sovellus joka analysoi Nasdaq-100 -osakkeiden volatiliteettia ja antaa
päivittäiset osto- ja myyntisuositukset **yön yli -strategialle**:

> Osta noin **20 min ennen Nasdaqin sulkua**, pidä yön yli, ja myy noin
> **20 min Nasdaqin avauksen jälkeen**. Portfoliossa on aina **5 osaketta**.

> ⚠️ **Ei sijoitusneuvontaa.** Tämä on opetus- ja analyysityökalu.
> Historiallinen volatiliteetti ei ennusta tulevia tuottoja.
> Yön yli -kaupankäynti on riskialtista — kaikki vastuu on sinun.

---

## Käynnistys

Kaksoisklikkaa **`start.bat`** — se käynnistää palvelimen ja avaa selaimen
osoitteeseen <http://127.0.0.1:5000>.

Tai komentoriviltä:

```powershell
py -3.12 -m pip install -r requirements.txt   # vain ensimmäisellä kerralla
py -3.12 app.py
```

---

## Päivittäinen käyttö

1. **🌆 Iltapäivitys — ~20 min ennen sulkua.**
   Paina *"Laske ostosuositukset"*. Sovellus analysoi koko Nasdaq-100:n ja
   ehdottaa 5 osaketta jotka ostetaan yön yli pidettäväksi. Lista tallentuu
   historiaan päivämäärällä.

2. **🌅 Aamupäivitys — ~20 min avauksen jälkeen (seuraavana päivänä).**
   Paina *"Laske myyntisuositukset"*. Sovellus hakee tuoreet hinnat,
   laskee yön yli -tuoton jokaiselle eilen ostetulle osakkeelle ja antaa
   myyntisuosituksen (voitto / stop loss / strategian mukainen sulku).

Kaikki päivät kertyvät **Historia**-osioon, josta näet menneet suositukset ja
toteutuneet yön yli -tuotot.

---

## Miten osakkeet valitaan

Jokaiselle osakkeelle lasketaan persentiilipisteet universumin sisällä ja
yhdistetään painotettuna kokonaispisteeksi (0–100):

| Komponentti      | Paino | Kuvaus |
|------------------|------:|--------|
| Volatiliteetti (ATR%) | 30 % | Kuinka paljon osake "heiluu" |
| Sulkuvahvuus     | 25 % | Sulkeeko lähellä päivän huippua (momentum sulkuun) |
| 5 pv momentum    | 20 % | Lyhyen aikavälin nousu |
| Gap-voittosuhde  | 15 % | Kuinka usein gappaa ylös yön yli (hist.) |
| Suhteellinen vaihto | 10 % | Tämän päivän kiinnostus vs. 20 pv ka. |

Myyntilogiikka: `+1.5 %` → ota voitto, `−1.0 %` → stop loss, muuten sulje
positio strategian mukaisesti. Kynnyksiä voi säätää tiedostossa
[`analyzer.py`](analyzer.py) (`TAKE_PROFIT`, `STOP_LOSS`, `WEIGHTS`).

---

## ☁️ Käyttö puhelimella (pilvideploy Renderiin)

Sovellus saadaan julkiseen `https://...`-osoitteeseen, joka toimii puhelimella
missä vain — eikä oma kone tarvitse olla päällä.

1. Mene <https://render.com> ja kirjaudu **"Sign in with GitHub"**.
2. **New +** → **Blueprint**.
3. Valitse repo **`tatutomp/asake_raha`** (anna Renderille lupa lukea repo).
4. Render lukee [`render.yaml`](render.yaml):n automaattisesti → paina **Apply**.
5. Odota muutama minuutti (asennus + käynnistys). Saat osoitteen muotoa
   `https://asake-raha.onrender.com` — avaa se puhelimella.

Jokaisen `git push`:n jälkeen Render päivittää sovelluksen automaattisesti.

> ℹ️ **Ilmaisen tason huomiot:** palvelu "nukahtaa" ~15 min käyttämättömyyden
> jälkeen, jolloin ensimmäinen avaus voi kestää ~30–60 s. Suositushistoria
> (`data/`) ei säily uudelleenkäynnistyksissä ilmaistasolla — demoon riittää,
> pysyvään käyttöön tarvitaan maksullinen levy.

## Tiedostot

| Tiedosto | Tarkoitus |
|----------|-----------|
| `app.py` | Flask-palvelin ja REST-API |
| `analyzer.py` | Volatiliteettianalyysi ja pisteytys |
| `tickers.py` | Nasdaq-100 -lista |
| `templates/index.html`, `static/` | Dashboard (HTML/CSS/JS) |
| `data/history.json` | Tallennettu suositushistoria (luodaan ajossa) |

## Huomioita datasta

- Data tulee Yahoo Financesta (`yfinance`), ilman API-avainta.
- "Ostohintana" käytetään viimeisintä valmista päiväsulkua ja
  "nykyhintana" tuoreinta saatavilla olevaa hintaa. Markkinan ollessa kiinni
  gap lasketaan viimeisistä saatavilla olevista hinnoista.
- Jos jokin ticker on poistunut pörssistä, se ohitetaan automaattisesti.

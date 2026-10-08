# ◆ EDGY – český trading Discord s prodejem strategie

Discord bot, který ti **sám postaví celý server** a **prodává přístup k tvé strategii**:

- jedním příkazem `/setup` vytvoří role, kategorie, kanály a oprávnění (všechno česky),
- pošle do kanálů uvítání, pravidla, upozornění o riziku, ceník, FAQ a podporu,
- nováček klikne na **✅ Souhlasím a vstupuji** → odemkne se mu komunita,
- zákazník zaplatí → dostane **aktivační kód** → klikne na **🔑 Aktivovat kód** → okamžitě je v **◆ The Edge** (Premium),
- 3 dny před koncem předplatného mu bot připomene prodloužení, po skončení mu Premium sebere,
- **tikety** pro platby převodem a dotazy (soukromý kanál jen pro zákazníka a tým),
- **mod-log** s přehledem nákupů, tiketů a nových členů.

---

## 🗂️ Jak bude server vypadat

| Kategorie | Kanály | Kdo vidí / píše |
|---|---|---|
| ◇ VSTUP | ✦・vstup · ✦・kodex · ✦・riziko · ✦・oznámení | všichni čtou, píše jen tým |
| ◇ SYSTÉM | ◆・přístup (ceník) · ◆・proof (výsledky) · ◆・zkušenosti · ◆・otázky-a-odpovědi | všichni čtou, zkušenosti píšou jen Edgy |
| ◇ KOMUNITA | ・chat · ・grafy · ・trhy-a-zprávy · ・mindset-a-risk · ・dotazy · ◇ Lounge | ◇ Člen a ◆ Edgy |
| ◆ THE EDGE | ◆・systém · ◆・signály · ◆・záznamy (jen čtení) · ◆・deník-obchodů · ◆・edge-chat · ◆ Live | jen ◆ Edgy (platící) |
| ◇ PODPORA | ・podpora (+ soukromé tikety) | všichni |
| ◈ TÝM | ・mod-log · ・porada | jen tým |

Server se jmenuje **EDGY** (edge = výhoda tradera, edgy = drzý). Placená sekce je **◆ THE EDGE**.
Role: **◈ Tým** › **◆ Edgy** (platící členové) › **◇ Člen**.

Tón serveru je sebevědomý a uzavřený, důvěru staví na transparentnosti: v ◆・proof se zveřejňují
všechny obchody včetně ztrát (výsledky v R, tedy v násobcích rizika).

---

## 🚀 Spuštění krok za krokem (cca 15 minut)

Tři věci musíš udělat ty, protože vyžadují tvůj Discord účet a počítač/server: Discord nedovoluje
botům zakládat servery a token bota si může vygenerovat jen vlastník aplikace.

### Krok 1 – Založ server

V aplikaci Discord klikni vlevo na **＋ (Přidat server)** → **Vytvořit vlastní** → **Pro mě a mé přátele**
→ zadej název **EDGY** → **Vytvořit**. Víc nic nenastavuj, zbytek udělá bot.

### Krok 2 – Vytvoř bota

1. Otevři <https://discord.com/developers/applications> → **New Application** → název (např. *EDGY Bot*) → **Create**.
2. Vlevo **Bot**:
   - **Reset Token** → **Copy** – tohle je `DISCORD_TOKEN` (nikomu ho neukazuj),
   - zapni **Server Members Intent** a ulož (**Save Changes**),
   - vypni **Public Bot**, ať si tvého bota nemůže přidat nikdo jiný.
3. Vlevo **General Information** zkopíruj **Application ID**.

### Krok 3 – Pozvi bota na server

Otevři v prohlížeči tento odkaz, místo `APPLICATION_ID` vlož ID z kroku 2:

```
https://discord.com/oauth2/authorize?client_id=APPLICATION_ID&permissions=8&scope=bot+applications.commands
```

Vyber svůj server → **Autorizovat**. (`permissions=8` = Administrator – bot potřebuje zakládat
kanály, role a nastavovat oprávnění.)

### Krok 4 – Spusť bota

Bot musí běžet **nonstop** (kvůli tlačítkům a hlídání předplatného). Na vyzkoušení stačí tvůj počítač,
na ostrý provoz doporučuju levný VPS (např. Hetzner, ~5 €/měsíc) s Dockerem.

**Windows – nejjednodušší cesta:**

1. Nainstaluj [Python](https://www.python.org/downloads/) (při instalaci zaškrtni *Add python.exe to PATH*).
2. Stáhni projekt jako ZIP: na GitHubu **Code → Download ZIP**, a rozbal ho.
3. Dvojklikni na **`start.bat`**. Napoprvé se otevře Poznámkový blok se souborem `.env` – za
   `DISCORD_TOKEN=` vlož token bota, ulož (`Ctrl+S`) a Poznámkový blok zavři. Bot se spustí.
4. Okno nech otevřené – když ho zavřeš, bot se vypne. Příště stačí zase dvojklik na `start.bat`.

Ostatní způsoby – nejdřív zkopíruj `.env.example` jako `.env` a vyplň `DISCORD_TOKEN`.

**Windows ručně** (potřebuješ [Python 3.11+](https://www.python.org/downloads/) – při instalaci zaškrtni *Add to PATH*):

```powershell
git clone https://github.com/malissVisual/tradingmoney.git
cd tradingmoney
copy .env.example .env
notepad .env
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py -m bot
```

**macOS / Linux:**

```bash
git clone https://github.com/malissVisual/tradingmoney.git
cd tradingmoney
cp .env.example .env && nano .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m bot
```

**VPS s Dockerem** (běží na pozadí a sám se po restartu znovu spustí):

```bash
git clone https://github.com/malissVisual/tradingmoney.git
cd tradingmoney
cp .env.example .env && nano .env
docker compose up -d --build
docker compose logs -f   # kontrola, že běží
```

Když v logu uvidíš `Přihlášen jako …`, bot je online.

### Krok 5 – Nech bota postavit server

Na serveru napiš do libovolného kanálu:

```
/setup uklidit_vychozi:True
```

Bot vytvoří všechno z tabulky výše a smaže výchozí `#general` a `Obecné`. Příkaz můžeš spouštět
kdykoli znovu – nic nezdvojí, jen doplní, co chybí, a srovná oprávnění.

### Krok 6 – Uprav texty a ceny

Texty jsou v adresáři [`texts/`](texts) (obyčejný text, první řádek je nadpis):

| Soubor | Kanál |
|---|---|
| `vitej.md` | ✦・vstup (s tlačítkem pro ověření) |
| `pravidla.md` | ✦・kodex |
| `riziko.md` | ✦・riziko |
| `cenik.md` | ◆・přístup (s tlačítky Koupit / Aktivovat kód) – **4 490 Kč / měsíc**, **22 000 Kč doživotně** |
| `vysledky.md` | ◆・proof – pod něj zveřejňuj každý obchod, i ztrátový |
| `faq.md` | ◆・otázky-a-odpovědi |
| `podpora.md` | ・podpora (s tlačítkem pro tiket) |
| `premium.md` | ◆・systém – uvítání v The Edge |

Po úpravě spusť znovu `/setup` – bot zprávy přepíše (nové neposílá). Když v textu necháš `XXX`
(nevyplněná hodnota), `/setup` tě na to upozorní. Zástupné značky: `{server}` = název serveru, `{#cenik}` = odkaz na kanál,
`{@premium}` = zmínka role (klíče najdeš v [`bot/layout.py`](bot/layout.py)).

Pak už jen do ◆・systém a ◆・záznamy nahraj svůj obsah a do ◆・proof své obchody.

---

## 💸 Jak prodávat

1. **Platba.** Vytvoř si platební odkazy a dej je do `.env` – měsíční jako `PAYMENT_URL`, doživotní jako
   `PAYMENT_URL_LIFETIME` (pak restartuj bota a spusť `/setup`). V ceníku se objeví tlačítka
   **🛒 Koupit měsíční** a **💎 Koupit doživotní**. Kde vytvořit odkaz:
   - [Stripe Payment Links](https://stripe.com/payments/payment-links) – karty, Apple/Google Pay, nízké poplatky,
   - [Lemon Squeezy](https://www.lemonsqueezy.com) / [Gumroad](https://gumroad.com) – prodávají za tebe a řeší i
     DPH v EU, vyšší poplatek, ale nejméně starostí,
   - **převodem** – zákazník otevře tiket, pošleš mu číslo účtu.
2. **Kód.** Po zaplacení vygeneruj kód:
   - měsíční (4 490 Kč): `/kody vytvorit dni:30 poznamka:Jan Novák`
   - doživotní (22 000 Kč): `/kody vytvorit dni:0 poznamka:Jan Novák`
3. **Předání.** Pošli kód zákazníkovi (e-mail, DM). Ten ho zadá tlačítkem **🔑 Aktivovat kód** v ceníku
   nebo příkazem `/aktivovat`. Hotovo – v mod-logu uvidíš, kdo co aktivoval.

Když je zákazník už na serveru, můžeš mu Premium dát i rovnou: `/premium pridat clen:@jméno dni:30`.
Prodloužení funguje stejně – nový kód přičte dny ke zbývajícímu času.

---

## ⌨️ Příkazy

| Příkaz | Kdo | Co dělá |
|---|---|---|
| `/setup [uklidit_vychozi]` | admin | vytvoří/opraví role, kanály a zprávy |
| `/kody vytvorit dni [pocet] [poznamka]` | admin | vygeneruje aktivační kódy |
| `/kody seznam` | admin | nepoužité kódy |
| `/kody zrusit kod` | admin | zruší nepoužitý kód |
| `/premium pridat clen dni` | admin | ručně přidá Premium (0 = doživotně) |
| `/premium odebrat clen` | admin | odebere Premium |
| `/premium seznam` | admin | aktivní Premium členové a do kdy |
| `/aktivovat kod` | každý | aktivuje Premium kódem |
| `/predplatne` | každý | do kdy mi platí Premium |

Admin příkazy běžní členové vůbec nevidí.

---

## 🛠️ Úpravy struktury

Kanály, role a oprávnění jsou popsané v [`bot/layout.py`](bot/layout.py). Přidej/uprav kanál, restartuj
bota a spusť `/setup`. Existující kanály bot nepřejmenovává, takže je můžeš klidně přejmenovat ručně v Discordu.

---

## ⚖️ Právní minimum (není to právní rada)

- **Živnost:** prodej vlastní strategie/kurzu je podnikání → živnostenský list (volná živnost) a příjmy danit.
- **Žádné investiční poradenství:** neraď konkrétním lidem na míru, nespravuj cizí peníze a nesahej na cizí
  účty – na to je potřeba licence ČNB. Upozornění v `texts/riziko.md` nech na serveru viditelné.
  Pokud budeš sdílet konkrétní obchodní signály, nech si ověřit, jestli to není regulované „investiční doporučení“.
- **Spotřebitelé** mají u nákupu online obecně 14 dní na odstoupení. U digitálního obsahu to jde vyloučit jen
  s jejich výslovným souhlasem před dodáním – mysli na to v obchodních podmínkách u platby.
- **GDPR:** ukládá se jen Discord ID, kódy a datum konce předplatného. Do obchodních podmínek / zásad napiš,
  jaké údaje zpracováváš.

Než začneš prodávat ve větším, vyplatí se hodinová konzultace s právníkem nebo účetní.

---

## 🧯 Řešení problémů

- **Příkazy se nezobrazují** – restartuj bota a v Discordu stiskni `Ctrl+R`.
- **„Zapni Server Members Intent“** – Developer Portal → Bot → Server Members Intent → Save.
- **Bot nemůže přidat roli** – Nastavení serveru → Role → přetáhni roli bota nad ◆ Edgy a ◇ Člen.
- **Discord odmítl token** – v Developer Portalu dej Reset Token a vlož nový do `.env`.

## 🔐 Bezpečnost

- Token je heslo bota. Když unikne, hned ho resetuj. Soubor `.env` je v `.gitignore` – na GitHub se nedostane.
- Zapni si na Discord účtu dvoufázové ověření.
- Zálohuj `data/bot.db` – jsou v ní kódy a předplatné.

---

## 👩‍💻 Pro vývojáře

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Testy běží proti simulovanému Discord serveru (bez připojení), takže ověří `/setup`, aktivaci kódů,
expiraci předplatného i tikety. Struktura kódu:

| Soubor | Obsah |
|---|---|
| `bot/layout.py` | role, kategorie, kanály a oprávnění |
| `bot/server_setup.py` | `/setup` – vytvoření a srovnání serveru |
| `bot/commands.py` | slash příkazy |
| `bot/views.py` | tlačítka a formulář pro kód |
| `bot/premium.py` | aktivace kódů, role Premium |
| `bot/tickets.py` | tikety |
| `bot/client.py` | události a hlídání předplatného |
| `bot/db.py` | SQLite databáze |

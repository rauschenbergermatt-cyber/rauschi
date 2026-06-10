#!/usr/bin/env python3
import os, re, smtplib, requests, json, time
from bs4 import BeautifulSoup
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

GMAIL_USER     = "rauschenberger.matt@gmail.com"
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TO_EMAIL       = "rauschenberger.matt@gmail.com"

CV_TEXT = """
Name: Matthäus Rauschenberger | geb. 26.02.1994 | Wien, Österreich
Sprachen: Deutsch (Muttersprache), Ungarisch (Muttersprache), Englisch (C1), Spanisch (A2)

BERUFSERFAHRUNG:
- 11/2025-04/2026: Mitunternehmer Mobilsaunen (Wintersaison), Offtours Kft., Budapest
  Gästebetreuung, Buchung, Empfang, Follow-Up, Saisonbetrieb
- 06/2025-10/2025: B2B Vertrieb Solarpark-Ausbau, RENA Solar Kft., Budapest
  Marktanalyse, Kundenakquise, Verhandlungen im Bereich erneuerbare Energien
- 04/2022-04/2025: B2B Vertrieb Energiemanagement, Prolan AG, Budakalász (3 Jahre)
  Key Account Management, Kundenakquise und -pflege,
  Betreuung der 120 relevantesten Geschäftskunden in Deutschland und Österreich
- 05/2017-04/2022: Einzelunternehmer Marketing & Sales, Donauschwaben Wein e.U., Wien (5 Jahre)
  Vermarktung (Weinhandel), Produktentwicklung (individuelle Labels, Weintourismus),
  Führung der Marke "Donauschwaben Wein", Kundenakquise, Vertrieb
- 12/2019-03/2020: Front Office Allrounder, Hotel Ultima Gstaad *****, Gstaad, Schweiz
  Gästebetreuung in der Schweizer Luxushotellerie, Transfers, Terminkoordination
- 01/2019-03/2019: Rezeptionist, Hotel Schwarzer Adler ****S, Kitzbühel
  Rechnungsvorbereitung, Beschwerdemanagement, Teamarbeit
- 07/2018-11/2018: Rezeptionist, Interalpen-Hotel Tyrol *****S, Telfs-Buchen
  Check-In/Check-Out, zentrale Schnittstelle im 5-Sterne-Superior-Betrieb
- 08/2016-01/2017: Praktikant Tourismus-Marketing, Österreich Werbung, Budapest
  Markenführung "Urlaub in Österreich" auf den Märkten HU/SK/SI/HR,
  Marktanalysen, Präsentationen, Presse- und Networking-Events

AUSBILDUNG:
- 08/2013-06/2016: BA Innovation & Management im Tourismus (Bachelor of Arts in Business), FH Salzburg
  Strategisches Management, Entrepreneurship im KMU, Marketingkommunikation, HRM, eMarketing
- 08/2014-01/2015: Auslandssemester Tourism Management, Universität Alicante (Erasmus+)
- 08/2012-12/2012: Tourismus Management, Budapester Wirtschaftshochschule
- 08/2008-06/2012: Abitur (Allgemeine Hochschulreife), Maria-Ward-Gymnasium, Budapest

AUSZEICHNUNGEN:
- Erhard Busek Würdigungspreis 2016 (FH Salzburg, interkulturellen Austausch Südosteuropa)
- Valeria-Koch-Preis 2017 (Landesselbstverwaltung der Ungarndeutschen)
- TUI Nachhaltigkeitspreis 1. Platz 2017 (ÖGAF, Tourismus-Forschungsarbeit des Jahres, "Via Suevia")
- Tourissimus Publikumspreis 2017 (ÖGAF)

FÄHIGKEITEN: Microsoft Office (Fortgeschritten), Führerschein B,
Analytisches Denken, Präsentationstechnik, Verhandlungsführung, Krisenmanagement
"""

SEARCHES = [
    {"label":"Vertrieb - Sales - Key Account","url":"https://www.karriere.at/jobs?keywords=sales+vertrieb+key+account+b2b&locations=Wien","max_jobs":4,"color":"#1a73e8"},
    {"label":"Office - Assistenz - Backoffice","url":"https://www.karriere.at/jobs?keywords=office+assistenz+backoffice+teamassistenz&locations=Wien","max_jobs":3,"color":"#34a853"},
]

HEADERS = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def brutto_zu_netto(brutto):
    sv_kv = brutto * 0.0387
    sv_pv = brutto * 0.1025
    sv_wf = brutto * 0.005
    sv_av = (0 if brutto<=1986 else brutto*0.01 if brutto<=2044 else brutto*0.02 if brutto<=2158 else brutto*0.03)
    sv = sv_kv + sv_pv + sv_wf + sv_av
    bmgl = (brutto - sv) * 12
    if bmgl <= 11693:   lst_j = 0.0
    elif bmgl <= 19134: lst_j = (bmgl-11693)*0.20
    elif bmgl <= 32075: lst_j = 1488.20+(bmgl-19134)*0.30
    elif bmgl <= 62080: lst_j = 5370.50+(bmgl-32075)*0.41
    elif bmgl <= 93120: lst_j = 17672.55+(bmgl-62080)*0.48
    else:               lst_j = 32567.75+(bmgl-93120)*0.50
    lst_sonder = max(0,(brutto-sv)*2-620)*0.06
    lst_m = (lst_j + lst_sonder) / 14
    return round(brutto - sv - lst_m)

def parse_gehalt(s):
    if not s: return None
    clean = s.replace(".","").replace(",",".").replace("\xa0"," ")
    m = re.search(r"\d+", clean)
    if not m: return None
    try: wert = float(re.sub(r"[^\d.]","",re.search(r"[\d.]+",clean).group()))
    except: return None
    if any(x in s for x in ["jaehrlich","jährlich","Jahr"]): return wert/12
    if any(x in s for x in ["monatlich","Monat"]): return wert
    if wert > 15000: return wert/12
    if wert >= 800:  return wert
    return None

def format_gehalt(s):
    if not s: return ""
    b = parse_gehalt(s)
    if b is None: return s
    n = brutto_zu_netto(b)
    return "Brutto ab EUR {:,.0f}/Mo  |  Netto ca. EUR {:,.0f}/Mo".format(b,n).replace(",",".")

def fetch_jobs(url, max_jobs):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        for h2 in soup.find_all("h2"):
            a = h2.find("a", href=lambda h: h and "/jobs/" in h and h.startswith("https"))
            if not a: continue
            title = a.get_text(strip=True)
            href  = a["href"].split("?")[0]
            if not title: continue
            company = salary = ""
            parent = h2.find_parent(["li","article","section","div"])
            if parent:
                comp = parent.find("a", href=lambda h: h and "/f/" in h)
                if comp: company = comp.get_text(strip=True)
                for txt in parent.stripped_strings:
                    if "EUR" in txt or chr(8364) in txt:
                        salary = txt.strip(); break
            jobs.append({"title":title,"company":company,"salary":salary,"url":href})
            if len(jobs) >= max_jobs: break
        return jobs or [{"title":"Heute keine Treffer.","company":"","salary":"","url":url}]
    except Exception as e:
        return [{"title":"Fehler: "+str(e),"company":"","salary":"","url":url}]

def fetch_job_description(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script","style","nav","header","footer"]):
            tag.decompose()
        main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"description|content|detail|job", re.I))
        text = (main or soup).get_text(separator="\n", strip=True)
        return text[:3000]
    except:
        return ""

def analyze_with_gemini(job_title, company, job_description):
    prompt = f"""Du bist Senior Recruiter in Wien. Analysiere diesen Lebenslauf gegen die Stelle.

LEBENSLAUF:
{CV_TEXT}

STELLE: {job_title} bei {company} (Wien)
STELLENBESCHREIBUNG:
{job_description or f"Position: {job_title} bei {company} in Wien"}

Antworte NUR mit einem JSON-Objekt (kein Markdown, kein Code-Block):
{{
  "score": <Zahl 1-10>,
  "begruendung": "<1 kurzer Satz warum dieser Score>",
  "cv_html": "<vollstaendiges optimiertes CV als HTML mit inline CSS>"
}}

Das optimierte CV soll:
- Auf Deutsch sein, professionell und klar
- Erfahrungen auf genau diese Stelle zugeschnitten
- Google XYZ Formel (Ergebnis, Messgröße, Methode) bei Bullets
- Starke Aktionsverben, keine Floskeln, keine "Responsible for"
- Zahlen wo vorhanden, [AUSFÜLLEN] als Platzhalter
- Sauber als HTML mit inline CSS formatiert (druckfertig, A4)
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4096}
    }
    try:
        r = requests.post(url, json=payload, headers={"Content-Type":"application/json"}, timeout=60)
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        text = re.sub(r"```json\s*","",text)
        text = re.sub(r"```\s*","",text)
        data = json.loads(text.strip())
        return int(data.get("score",5)), data.get("begruendung",""), data.get("cv_html","")
    except Exception as e:
        print(f"  Gemini Fehler: {e}")
        return 5, "", ""

def score_style(score):
    if score >= 8: return "#4caf50","#e8f5e9","#1b5e20"
    if score >= 5: return "#ff9800","#fff8e1","#e65100"
    return "#ef5350","#ffebee","#b71c1c"

def build_html(results):
    today = datetime.now().strftime("%d.%m.%Y")
    secs = ""
    for r in results:
        c = r["color"]
        rows = ""
        for j in r["jobs"]:
            g = format_gehalt(j["salary"])
            sal = (" &middot; <span style='color:#2e7d32;font-weight:600'>"+g+"</span>") if g else ""
            co  = (" &middot; "+j["company"]) if j["company"] else ""
            score = j.get("score", 5)
            bc, bgc, tc = score_style(score)
            begruendung = j.get("begruendung","")
            score_circle = f"<div style='text-align:center;flex-shrink:0'><div style='width:48px;height:48px;border-radius:50%;background:{bgc};border:2px solid {bc};display:flex;align-items:center;justify-content:center'><span style='font-size:20px;font-weight:700;color:{tc}'>{score}</span></div><div style='font-size:10px;color:#888;margin-top:2px'>/ 10</div></div>"
            cv_note = f"<div style='margin-top:8px;padding-top:8px;border-top:1px solid #e0e0e0;font-size:12px;color:#555'><b>Analyse:</b> {begruendung} &nbsp;&bull;&nbsp; <em>Optimiertes CV im Anhang</em></div>" if begruendung else "<div style='margin-top:8px;padding-top:8px;border-top:1px solid #e0e0e0;font-size:12px;color:#999'><em>Optimiertes CV im Anhang</em></div>"
            rows += f"<div style='border-left:4px solid {c};background:#f9f9f9;border-radius:0 4px 4px 0;padding:12px 16px;margin-bottom:10px'><div style='display:flex;justify-content:space-between;align-items:flex-start;gap:10px'><div><div style='font-weight:700;font-size:15px;margin-bottom:3px'><a href='{j['url']}' style='color:{c};text-decoration:none'>{j['title']}</a></div><div style='font-size:13px;color:#666'>Wien{co}{sal}</div></div>{score_circle}</div>{cv_note}</div>"
        secs += f"<div style='padding:20px 24px 8px'><div style='font-size:15px;font-weight:700;border-bottom:2px solid #eee;padding-bottom:6px;margin-bottom:12px'>{r['label']}</div>{rows}</div>"
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'></head><body style='margin:0;padding:20px;background:#f0f0f0;font-family:Arial,sans-serif'><div style='max-width:640px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12)'><div style='background:#1a73e8;color:#fff;padding:24px'><h1 style='margin:0;font-size:22px'>Job-Uebersicht Wien</h1><p style='margin:4px 0 0;opacity:.85;font-size:13px'>{today} - karriere.at</p></div>{secs}<div style='padding:14px 24px;font-size:11px;color:#aaa;border-top:1px solid #eee'>Automatisch generiert - {today} - Netto: AT 2025, ledig, 32 J. &nbsp;|&nbsp; Score: 🟢 8-10 🟡 5-7 🔴 1-4</div></div></body></html>"

def send_email(html, attachments):
    today = datetime.now().strftime("%d.%m.%Y")
    msg = MIMEMultipart("mixed")
    msg["Subject"] = "Jobs Wien - " + today
    msg["From"]    = GMAIL_USER
    msg["To"]      = TO_EMAIL
    msg.attach(MIMEText(html, "html", "utf-8"))
    for filename, content in attachments:
        part = MIMEBase("text", "html")
        part.set_payload(content.encode("utf-8"))
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename=\"{filename}\"")
        msg.attach(part)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
        srv.login(GMAIL_USER, GMAIL_PASSWORD)
        srv.sendmail(GMAIL_USER, TO_EMAIL, msg.as_string())
    print("E-Mail gesendet an " + TO_EMAIL)

def main():
    print("["+datetime.now().strftime("%H:%M:%S")+"] Starte Job-Suche...")
    results = []
    attachments = []
    for s in SEARCHES:
        print("  -> " + s["label"])
        jobs = fetch_jobs(s["url"], s["max_jobs"])
        enriched = []
        for j in jobs:
            j["score"] = 5
            j["begruendung"] = ""
            if not j["title"].startswith(("Heute keine","Fehler")):
                print("     Analysiere: " + j["title"])
                desc = fetch_job_description(j["url"])
                time.sleep(1)
                score, begr, cv_html = analyze_with_gemini(j["title"], j["company"], desc)
                j["score"] = score
                j["begruendung"] = begr
                if cv_html:
                    safe = re.sub(r"[^\w]","_",j["title"])[:35]
                    attachments.append((f"CV_optimiert_{safe}.html", cv_html))
                print(f"     Score: {score}/10")
            enriched.append(j)
        results.append(dict(s, jobs=enriched))
    html = build_html(results)
    send_email(html, attachments)
    print("Fertig.")

if __name__ == "__main__":
    main()

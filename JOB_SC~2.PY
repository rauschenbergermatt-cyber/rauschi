#!/usr/bin/env python3
import os, re, smtplib, requests
from bs4 import BeautifulSoup
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_USER     = "rauschenberger.matt@gmail.com"
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
TO_EMAIL       = "rauschenberger.matt@gmail.com"

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
    if any(x in s for x in ["jaehrlich","jährlich","jährlich","Jahr"]): return wert/12
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
            rows += "<div style='border-left:4px solid {c};background:#f9f9f9;border-radius:4px;padding:12px 16px;margin-bottom:10px'><div style='font-weight:700;font-size:15px;margin-bottom:3px'><a href='{u}' style='color:{c};text-decoration:none'>{t}</a></div><div style='font-size:13px;color:#666'>Wien{co}{sal}</div></div>".format(c=c,u=j["url"],t=j["title"],co=co,sal=sal)
        secs += "<div style='padding:20px 24px 8px'><div style='font-size:15px;font-weight:700;border-bottom:2px solid #eee;padding-bottom:6px;margin-bottom:12px'>{l}</div>{rows}</div>".format(l=r["label"],rows=rows)
    return "<!DOCTYPE html><html><head><meta charset='utf-8'></head><body style='margin:0;padding:20px;background:#f0f0f0;font-family:Arial,sans-serif'><div style='max-width:640px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.12)'><div style='background:#1a73e8;color:#fff;padding:24px'><h1 style='margin:0;font-size:22px'>Job-Uebersicht Wien</h1><p style='margin:4px 0 0;opacity:.85;font-size:13px'>{d} - karriere.at</p></div>{s}<div style='padding:14px 24px;font-size:11px;color:#aaa;border-top:1px solid #eee'>Automatisch generiert - {d} - Netto: AT 2025, ledig, 32 J.</div></div></body></html>".format(d=today,s=secs)

def send_email(html):
    today = datetime.now().strftime("%d.%m.%Y")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Jobs Wien - " + today
    msg["From"] = GMAIL_USER
    msg["To"]   = TO_EMAIL
    msg.attach(MIMEText(html,"html","utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
        srv.login(GMAIL_USER, GMAIL_PASSWORD)
        srv.sendmail(GMAIL_USER, TO_EMAIL, msg.as_string())
    print("E-Mail gesendet an " + TO_EMAIL)

def main():
    print("["+datetime.now().strftime("%H:%M:%S")+"] Starte Job-Suche...")
    results = []
    for s in SEARCHES:
        print("  -> " + s["label"])
        jobs = fetch_jobs(s["url"], s["max_jobs"])
        results.append(dict(s, jobs=jobs))
        print("     {} Jobs gefunden".format(len(jobs)))
    html = build_html(results)
    send_email(html)
    print("Fertig.")

if __name__ == "__main__":
    main()

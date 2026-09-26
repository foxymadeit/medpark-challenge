# python n8n/check_routing.py routing.json [mailpit-api-url]
"""Posts the backend's own payload (delivery.payload shape) to n8n for each meeting type and
checks what Mailpit received: recipients per type, subject, three PDF attachments."""
import base64, json, os, sys, time, urllib.error, urllib.request
HOOK = "http://127.0.0.1:5678/webhook/liminal-minutes"
SECRET = os.environ.get("LIMINAL_N8N_SECRET") or next(
    (l.split("=", 1)[1].strip() for l in open(".env") if l.startswith("LIMINAL_N8N_SECRET=")), "")
MAILPIT = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8025/api/v1"
ROUTING = json.load(open(sys.argv[1]))
pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
urllib.request.urlopen(urllib.request.Request(MAILPIT + "/messages", method="DELETE"))
ok = True
for t in ("medical", "executive", "administrative"):
    body = {"meetingId": f"test-{t}", "participant_emails": ["dr.rusu@hospital.local"], "distributionList": ROUTING[t],
            "minutes": {"title": f"Test {t} board\r\nBcc: attacker@example.com", "meeting_type": t, "language": "ro", "summary": "The board met.",
                        "attendees": ["Participant 1"], "decisions": ["Se aprobă protocolul ATI."],
                        "action_items": [{"text": "Send the report.", "owner": "Participant 2", "deadline": "2026-10-02", "source_quote": None}]},
            "documents": [{"fileName": f"MoM_2026-09-26_{t}_{l}.pdf", "mimeType": "application/pdf",
                           "data": base64.b64encode(pdf).decode()} for l in ("ro", "ru", "en")]}
    r = urllib.request.urlopen(urllib.request.Request(HOOK, data=json.dumps(body).encode(), method="POST",
                                                      headers={"Content-Type": "application/json", "X-Liminal-Secret": SECRET}), timeout=60)
    print(t, "webhook", r.status)
try:   # without the secret, n8n must refuse
    urllib.request.urlopen(urllib.request.Request(HOOK, data=b"{}", method="POST", headers={"Content-Type": "application/json",
                                                  "X-Liminal-Secret": "wrong"}), timeout=30)
    print("webhook without the right secret: ACCEPTED (bad)"); ok = False
except urllib.error.HTTPError as e:
    print("webhook without the right secret: refused", e.code)
time.sleep(2)
msgs = json.load(urllib.request.urlopen(MAILPIT + "/messages"))["messages"]
for m in msgs:
    to = sorted(a["Address"] for a in m["To"]); cc = sorted(a["Address"] for a in m["Cc"])
    t = next(k for k in ROUTING if k in m["Subject"].lower() or f"test {k}" in m["Subject"].lower())
    right = to == sorted(ROUTING[t])
    bcc = [a["Address"] for a in m.get("Bcc") or []]
    ok &= right and m["Attachments"] == 3 and not bcc and "\n" not in m["Subject"]
    print(f"{m['Subject']!r} to={to} cc={cc} attachments={m['Attachments']} {'OK' if right else 'WRONG LIST'}")
print("ALL OK" if ok and len(msgs) == 3 else f"FAILED ({len(msgs)} messages)")

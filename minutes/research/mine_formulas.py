import re, glob, json, collections
LEX = {
 "en": {"decision": [r"\bRESOLVED\b", r"\bresolved that\b", r"\b(the )?(board|committee) (APPROVED|approved)\b", r"\bAPPROVED\b", r"\bit was agreed\b", r"\b(board|committee) (AGREED|agreed)\b", r"\bratified\b", r"\bendorsed\b", r"\bmotion\b", r"\bcarried\b", r"\bunanimously\b"],
        "noting": [r"\b(the )?(board|committee) (NOTED|noted)\b", r"\bNOTED\b", r"\bit was noted\b", r"\breceived (the|a) (report|update|paper)\b", r"\bwas informed\b", r"\bwas assured\b", r"\bdiscussed\b", r"\bMembers noted\b"],
        "action": [r"\bACTION\b", r"\bAction:", r"\baction log\b", r"\bto (provide|circulate|report|bring|review|confirm) ", r"\bagreed to\b", r"\bwould (provide|report|circulate|bring)\b"],
        "deadline": [r"\bby (the )?(end of )?(January|February|March|April|May|June|July|August|September|October|November|December)\b", r"\bnext (meeting|month|board)\b", r"\bdue date\b", r"\btimescale\b", r"\b\d{1,2}(st|nd|rd|th)? (January|February|March|April|May|June|July|August|September|October|November|December) 20\d\d\b"]},
 "ro": {"decision": [r"\bs-a decis\b", r"\bse decide\b", r"\bse aprob[ăa]\b", r"\ba aprobat\b", r"\bs-a aprobat\b", r"\bse accept[ăa]\b", r"\bs-a hot[ăa]r[âî]t\b", r"\bhot[ăa]r[ăa][șs]te\b", r"\bHOT[ĂA]R[ÂÎ]RE", r"\bS-a votat\b", r"\bunanimitate\b", r"\bse respinge\b"],
        "noting": [r"\bse ia act\b", r"\ba luat act\b", r"\bia act\b", r"\ba informat\b", r"\ba prezentat\b", r"\ba men[țţt]ionat\b", r"\ba propus\b", r"\ba comunicat\b", r"\bse consider[ăa]\b", r"\bau discutat\b", r"\bse aduce la cuno[șs]tin[țţ][ăa]\b"],
        "action": [r"\bse oblig[ăa]\b", r"\bse [îi]ncredin[țţ]eaz[ăa]\b", r"\bse [îi]ns[ăa]rcineaz[ăa]\b", r"\bresponsabil\b", r"\bva asigura\b", r"\bvor asigura\b", r"\bva prezenta\b", r"\bdirec[țţ]iei? .{0,40} i se\b", r"\bsarcin[ăa]\b"],
        "deadline": [r"\btermen\b", r"\bp[âî]n[ăa] la\b", r"\b[îi]n termen de\b", r"\b\d{1,2}\.\d{1,2}\.20\d\d\b", r"\bpermanent\b", r"\blunar\b"]},
 "ru": {"decision": [r"РЕШИЛИ", r"ПОСТАНОВИЛИ", r"\bрешили\b", r"\bпостановили\b", r"\bрешение принято\b", r"\bединогласно\b", r"\bГОЛОСОВАЛИ\b", r"\bголосовали\b", r"\bутвердить\b", r"\bодобрить\b", r"\bпринять\b"],
        "noting": [r"СЛУШАЛИ", r"ВЫСТУПИЛИ", r"\bпринять к сведению\b", r"\bвыступил[аи]?\b", r"\bдоложил[аи]?\b", r"\bпредставил[аи]?\b", r"\bотметил[аи]?\b", r"\bрассмотрен[ыо]?\b", r"\bинформировал[аи]?\b"],
        "action": [r"\bпоручить\b", r"\bрекомендовать\b", r"\bобеспечить\b", r"\bорганизовать\b", r"\bпровести\b", r"\bответственн(ый|ые|ая)\b", r"\bподготовить\b", r"\bразработать\b"],
        "deadline": [r"\bсрок\b", r"\bв срок до\b", r"\bдо \d{1,2}\.\d{1,2}\.20\d\d\b", r"\b\d{1,2}\.\d{1,2}\.20\d\d\b", r"\bпостоянно\b", r"\bежемесячно\b", r"\bдо конца\b"]}}
docs = {l: sorted(f for f in glob.glob(f"{l}/*.txt") if not f.endswith((".full.txt", "urls.txt", "links.txt"))) for l in ("en", "ro", "ru")}
report = {}
for lang, files in docs.items():
    texts = {f: open(f, encoding="utf-8", errors="ignore").read() for f in files}
    texts = {f: t for f, t in texts.items() if len(t.split()) > 50}
    report[lang] = {"docs": len(texts), "words": sum(len(t.split()) for t in texts.values()), "categories": {}}
    for cat, pats in LEX[lang].items():
        rows = []
        for p in pats:
            hits, in_docs, ex = 0, 0, []
            for f, t in texts.items():
                ms = list(re.finditer(p, t, flags=re.I if lang != "ru" or p.islower() else 0))
                if ms:
                    hits += len(ms); in_docs += 1
                    if len(ex) < 2:
                        m = ms[0]; line = t[:m.start()].count("\n") + 1
                        s = t[max(0, m.start() - 110):m.end() + 160].replace("\n", " "); s = re.sub(r"\s+", " ", s)
                        ex.append({"doc": f.split("/")[1], "line": line, "quote": s})
            rows.append({"pattern": p, "hits": hits, "docs": in_docs, "examples": ex})
        report[lang]["categories"][cat] = sorted(rows, key=lambda r: -r["docs"])
json.dump(report, open("mined.json", "w"), ensure_ascii=False, indent=1)
for lang, r in report.items():
    print(f"\n#### {lang}: {r['docs']} docs, {r['words']} words")
    for cat, rows in r["categories"].items():
        print(f"  {cat}: " + ", ".join(f"{x['pattern'].replace(chr(92)+'b','')}={x['docs']}d/{x['hits']}" for x in rows if x['hits']))

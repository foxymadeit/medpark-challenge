"""Six scripted hospital meetings with answer keys, for choosing and tuning
the model. Written by us, synthetic, no real people or patients.

Each line is (speaker, text, tags). Tags mark what minutes must capture:
  D:key            a line that settles decision `key`
  A:key:owner:iso  a line where `owner` takes action `key`, due `iso` ("" if none)
  NOTD             a proposal or question nobody adopted: citing only this is a false decision
  OLD:key          an earlier version of decision `key` that a later line reverses
  PAT:Name         a patient's name is said on this line (must never reach the minutes)
  P:key            where decision `key` was first proposed (eval/long.py only; the scorer ignores it)
The meeting date is Thursday 24 September 2026, so "până vineri" is 2026-09-25.

python -m eval.meetings  writes eval/data/<id>.txt and <id>.gold.json
"""

import json
from pathlib import Path

DATE = "2026-09-24"

MEETINGS = {
 "med01": ("medical", [
  (1, "Bună ziua, colegi. Începem Consiliul Medical. Avem trei subiecte: pacienta din salonul 12, paturile ATI și protocolul de sepsis.", ""),
  (1, "Primul subiect. Doctore, vă rog.", ""),
  (2, "Pacienta Maria Lungu, 67 de ani, salonul 12, internată cu suspiciune de infarct miocardic acut. Troponina a crescut, ecocardiografia arată fracția de ejecție 38 la sută.", "PAT:Maria Lungu"),
  (2, "Я бы предложил сделать МРТ сердца до вмешательства, чтобы оценить жизнеспособность миокарда.", ""),
  (3, "Сколько времени займёт МРТ? У нас очередь.", ""),
  (2, "Dacă o programăm azi, avem rezultatul mâine dimineață.", ""),
  (1, "Bine. Suntem de acord cu RMN cardiac înainte de intervenție? Cine e pentru?", ""),
  (3, "Da, de acord.", ""),
  (4, "De acord.", "D:mri"),
  (2, "Mă ocup eu de programare, o fac până vineri.", "A:mri_book:Speaker 2:2026-09-25"),
  (1, "Intervenția rămâne luni la ora 9.", "OLD:time"),
  (4, "Stop, la 9 dimineața nu avem anestezist liber, e la altă operație.", ""),
  (1, "Atunci o mutăm la ora 10. Toată lumea e ok cu ora 10?", ""),
  (3, "Ok, 10 e bine.", "D:time"),
  (1, "Al doilea subiect, paturile ATI pentru luni.", ""),
  (4, "Avem două paturi libere, но только если переведём двух пациентов в терапию до воскресенья.", ""),
  (1, "Deci condiționat: dacă transferul se face până duminică, păstrăm cele două paturi pentru luni. Da?", ""),
  (3, "Da, aprobăm așa.", "D:beds"),
  (4, "Confirm eu transferul cu secția de terapie mâine.", "A:transfer:Speaker 4:2026-09-25"),
  (2, "Apropo, poate ar trebui să schimbăm furnizorul de reactivi pentru troponină, sunt cam scumpi.", "NOTD"),
  (1, "Discutăm altă dată despre furnizori.", ""),
  (1, "Al treilea subiect, protocolul de sepsis. Where are we with the sepsis bundle?", ""),
  (3, "Am revizuit protocolul. Propun antibioticul în prima oră de la triaj, lactatul la 2 ore.", ""),
  (2, "Согласен, это по рекомендациям Surviving Sepsis.", ""),
  (1, "Aprobăm protocolul revizuit, cu antibiotic în prima oră și lactat la 2 ore.", "D:sepsis"),
  (1, "Cine face instruirea personalului de la UPU?", ""),
  (3, "Instruirea o fac eu, până la sfârșitul lunii.", "A:training:Speaker 3:2026-09-30"),
  (1, "Mulțumesc. Ședința următoare joi, la aceeași oră.", ""),
 ]),
 "med02": ("medical", [
  (1, "Începem. Azi avem cazul pacientului Ion Rusu și consumul de antibiotice pe trimestru.", "PAT:Ion Rusu"),
  (2, "Pacientul are 58 de ani, patul 3 în chirurgie, după colecistectomie, febră 38,9 în a treia zi.", ""),
  (2, "Hemocultura e în lucru. Am început ceftriaxonă 2 grame pe zi.", ""),
  (3, "По-моему, нужно добавить метронидазол, если есть подозрение на абсцесс.", ""),
  (2, "Facem mai întâi CT de abdomen. Dacă apare colecție, adăugăm metronidazol.", ""),
  (1, "De acord: CT de abdomen azi, iar metronidazolul doar dacă CT arată colecție.", "D:ct"),
  (4, "Programez eu CT-ul pentru azi după-amiază.", "A:ct_book:Speaker 4:2026-09-24"),
  (1, "Consumul de antibiotice. Prezentați datele, vă rog.", ""),
  (3, "În trimestrul trei, carbapenemele au crescut cu 22 la sută față de trimestrul doi.", ""),
  (3, "I suggest we introduce a pre-authorisation for meropenem.", ""),
  (2, "Не уверен, это замедлит лечение в реанимации.", ""),
  (1, "Propun să votăm pre-autorizarea pentru meropenem, cu excepție pentru ATI. Pentru?", ""),
  (3, "Pentru.", ""),
  (4, "Pentru.", ""),
  (2, "Против.", ""),
  (1, "Trei pentru, unul împotrivă. Se aprobă pre-autorizarea, cu excepție pentru ATI.", "D:preauth"),
  (3, "Pregătesc formularul de pre-autorizare în termen de 7 zile.", "A:form:Speaker 3:2026-10-01"),
  (4, "Și un audit la sfârșit de trimestru, maybe?", "NOTD"),
  (1, "Vedem. Altceva? Nu. Închidem.", ""),
 ]),
 "exe01": ("executive", [
  (1, "Bună ziua. Comitetul executiv. Pe agendă: bugetul pentru trimestrul patru, angajarea asistentelor și contractul de mentenanță CT.", ""),
  (2, "Bugetul de investiții pentru Q4 e 4,2 milioane lei. Propunerea e 2,5 pentru echipamente, restul pentru renovarea secției de pediatrie.", ""),
  (3, "А сколько осталось от третьего квартала?", ""),
  (2, "Au rămas 300 de mii, le trecem în Q4.", ""),
  (1, "Aprobăm bugetul Q4 de 4,2 milioane, cu repartizarea propusă. Obiecții? Nu. Aprobat.", "D:budget"),
  (1, "Angajarea asistentelor. Ne lipsesc 12 asistente în ATI și chirurgie.", ""),
  (4, "Putem anunța concursul săptămâna viitoare.", ""),
  (1, "Bine, anunțăm concursul pentru 12 posturi. HR, vă ocupați?", "D:hiring"),
  (4, "Da, HR se ocupă, publicăm anunțul săptămâna viitoare.", "A:hiring_ad:Speaker 4:"),
  (3, "Может, повысим зарплаты медсёстрам на 10 процентов, чтобы привлечь людей?", "NOTD"),
  (1, "Asta e o decizie mare, revenim la următoarea ședință cu calculele.", ""),
  (1, "Contractul de mentenanță CT expiră pe 15 octombrie.", ""),
  (2, "Furnizorul oferă prelungire pe un an cu 8 la sută mai scump.", ""),
  (1, "Negociem mai întâi. Serviciul juridic, puteți încerca să obțineți un preț mai bun până pe 5 octombrie?", ""),
  (5, "Da, negociem noi până pe 5 octombrie.", "A:ct_negotiation:Speaker 5:2026-10-05"),
  (1, "Decizia finală pe contract o luăm după negocieri.", "NOTD"),
 ]),
 "exe02": ("executive", [
  (1, "Azi: parteneriatul cu compania de asigurări și data deschiderii secției de reabilitare.", ""),
  (2, "Moldasig propune un contract pentru check-up corporativ, 500 de pacienți pe an.", ""),
  (3, "Tariful e prea mic, sub costul nostru.", ""),
  (2, "Pot renegocia tariful la plus 15 la sută.", ""),
  (1, "Aprobăm parteneriatul doar dacă tariful crește cu cel puțin 15 la sută. Da?", ""),
  (3, "Да, при таком условии согласен.", "D:insurer"),
  (2, "Trimit eu contrapropunerea până luni.", "A:counter:Speaker 2:2026-09-28"),
  (1, "Secția de reabilitare. Deschiderea era planificată pe 1 noiembrie.", "OLD:rehab"),
  (4, "Echipamentele vin abia pe 20 noiembrie, deci 1 noiembrie nu e realist.", ""),
  (1, "Atunci amânăm deschiderea pe 1 decembrie. Toți de acord?", ""),
  (3, "Da.", ""),
  (4, "Da, 1 decembrie.", "D:rehab"),
  (4, "Actualizez eu graficul de lucrări și îl trimit până vineri.", "A:schedule:Speaker 4:2026-09-25"),
  (3, "Ar fi bine și o campanie de marketing, what do you think?", "NOTD"),
  (1, "Mai târziu. Mulțumesc tuturor.", ""),
 ]),
 "adm01": ("administrative", [
  (1, "Se aude? Bine. Ședința administrativă. Cantina, parcarea și actualizarea sistemului informatic.", ""),
  (2, "Contractul cu firma de catering expiră la sfârșitul lunii. Am trei oferte.", ""),
  (2, "Cea mai bună e de la Gustul Casei, 45 de lei porția, cu meniu dietetic.", ""),
  (3, "А по отзывам сотрудников они нормальные?", ""),
  (2, "Da, au lucrat la spitalul de copii, recenzii bune.", ""),
  (1, "Alegem Gustul Casei. De acord?", ""),
  (3, "Согласна.", "D:catering"),
  (2, "Semnez eu contractul până la sfârșitul lunii.", "A:catering_sign:Speaker 2:2026-09-30"),
  (1, "Parcarea. Angajații se plâng că nu sunt locuri.", ""),
  (4, "Propun să rezervăm etajul minus unu doar pentru personal.", ""),
  (3, "Тогда пациентам не хватит мест.", ""),
  (1, "Nu decidem azi, facem mai întâi o numărătoare a mașinilor.", ""),
  (4, "Fac eu numărătoarea săptămâna viitoare.", "A:parking_count:Speaker 4:"),
  (1, "Sistemul informatic. IT-ul vrea să facă update-ul în weekend.", ""),
  (5, "Da, sâmbătă de la 22 la 2 noaptea. Sistemul va fi oprit patru ore.", ""),
  (1, "Aprobăm update-ul sâmbătă, 22 la 2. Anunțați toate secțiile.", "D:it_update"),
  (5, "Serviciul IT trimite anunțul la toate secțiile mâine.", "A:it_notice:Speaker 5:2026-09-25"),
  (3, "Sorry, cineva are un încărcător?", ""),
 ]),
 "adm02": ("administrative", [
  (1, "Începem. Graficul de gărzi, exercițiul de evacuare și instruirea GDPR.", ""),
  (2, "Pentru octombrie lipsesc medici de gardă în weekendurile 10 și 24.", ""),
  (3, "Могу взять 10-е, но не 24-е.", ""),
  (1, "Bine. Dr. din chirurgie ia 24?", ""),
  (4, "Da, iau eu 24.", ""),
  (1, "Aprobăm graficul cu aceste modificări.", "D:rota"),
  (2, "Actualizez graficul și îl public azi.", "A:rota_publish:Speaker 2:2026-09-24"),
  (1, "Exercițiul de evacuare. Pompierii cer unul pe an, anul acesta nu l-am făcut.", ""),
  (5, "Propun 15 octombrie, dimineața.", ""),
  (1, "15 octombrie la ora 9. Aprobat.", "D:drill"),
  (5, "Coordonez eu cu pompierii până pe 1 octombrie.", "A:drill_coord:Speaker 5:2026-10-01"),
  (1, "Instruirea GDPR. Legea nouă e în vigoare din 23 august.", ""),
  (3, "Надо обучить всех, у кого доступ к данным пациентов.", ""),
  (1, "Da. Facem instruire obligatorie pentru tot personalul cu acces la date.", "D:gdpr"),
  (3, "Pregătesc eu materialul cât mai curând.", "A:gdpr_material:Speaker 3:"),
  (2, "Poate facem și un test la final?", "NOTD"),
 ]),
}


def write(out: Path, mid: str, mtype: str, script, stamps) -> dict:
    """Write one meeting's transcript and answer key; stamps[i] is line i's time."""
    lines, gold = [], {"id": mid, "type": mtype, "date": DATE, "decisions": {}, "actions": {}, "old": {}, "not_decisions": [],
                       "patients": [], "proposals": {}}
    for n, ((spk, text, tags), stamp) in enumerate(zip(script, stamps), 1):
        lines.append(f"[{stamp}] Speaker {spk}: {text}")
        lid = f"L{n:04d}"
        for tag in filter(None, tags.split(";")):
            kind, _, rest = tag.partition(":")
            if kind == "D":
                gold["decisions"].setdefault(rest, []).append(lid)
            elif kind == "A":
                key, owner, iso = rest.split(":")
                gold["actions"][key] = {"lines": [lid], "owner": owner, "deadline": iso}
            elif kind == "OLD":
                gold["old"].setdefault(rest, []).append(lid)
            elif kind == "NOTD":
                gold["not_decisions"].append(lid)
            elif kind == "PAT":
                gold["patients"].append(rest)
            elif kind == "P":
                gold["proposals"].setdefault(rest, []).append(lid)
    (out / f"{mid}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / f"{mid}.gold.json").write_text(json.dumps(gold, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"type": mtype, "lines": len(lines), "decisions": len(gold["decisions"]), "actions": len(gold["actions"])}


def build(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    index = {}
    for mid, (mtype, script) in MEETINGS.items():
        stamps = [f"{t // 60:02d}:{t % 60:02d}" for t in (5 + i * 9 for i in range(len(script)))]
        index[mid] = write(out, mid, mtype, script, stamps)
    return index


if __name__ == "__main__":
    idx = build(Path(__file__).resolve().parent / "data")
    for k, v in idx.items():
        print(k, v)
    print("total decisions", sum(v["decisions"] for v in idx.values()), "actions", sum(v["actions"] for v in idx.values()))

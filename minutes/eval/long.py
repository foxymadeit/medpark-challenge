"""A one-hour medical board meeting where nobody says a name, like the
recording the judges will give us. Synthetic: no real people or patients.

Same tags as eval/meetings.py, plus P:key where a decision was first proposed.
Two decisions are proposed early in a topic and settled after a long
discussion, more than one extraction window later (mom/extract.py), so the
model sees the agreement without the proposal. Between the settled lines runs
ordinary board talk, built from the templates below with a fixed seed so the
file is the same on every machine. Filler never contains decision or
agreement words, so every decision in the answer key is one the script put there.

python -m eval.long  writes eval/data/long01.txt and long01.gold.json
"""

import random
import re
from pathlib import Path

from eval.meetings import write
from mom.verify import AGREEMENT_WORDS, DECISION_ACTS, fold

MINUTES = 59.5
SEED = 24

FILLER = {
 "generic": [
  "Se aude și în spatele sălii? {aside}",
  "Коллеги онлайн, {online}",
  "{aside} Continuăm.",
  "Cafeaua de la etajul trei {coffee}",
  "Sorry, my pager went off, {pager}",
  "Кто-нибудь видел пульт от проектора? {aside}",
 ],
 "t1": [
  "La internare avea saturația {sat} la sută, acum e {sat2} cu oxigen pe mască.",
  "Креатинин вырос до {creat}, диурез снижен.",
  "Radiografia arată {xray}.",
  "BNP-ul a fost {bnp}, deci decompensarea e clară.",
  "Pacientul din salonul 8 are și {comorb}.",
  "Tensiunea arterială se menține în jur de {bp}.",
  "Hemoleucograma arată leucocite {wbc} mii, proteina C reactivă {crp}.",
  "The family asked again about {family}.",
  "Мы продолжаем {therapy}, динамика пока слабая.",
  "Pacienta din patul 5 are drenul cu {drain}.",
  "Echipa de gardă a notat noaptea trecută {night}.",
 ],
 "t2": [
  "Ocuparea în ATI a fost de {occ} la sută în ultimele {days} zile.",
  "В выходные к нам поступает до {adm} пациентов из приёмного.",
  "Some post-op patients stay in the ICU an extra {extra} just because the ward can't take them.",
  "Durata medie de ședere în ATI este {los} zile.",
  "Transferurile din raioane au crescut, mai ales {districts}.",
  "Проблема не в койках, а в {bottleneck}.",
  "Pe tura de noapte avem {nurses} asistente la douăsprezece paturi.",
  "Ventilatoarele sunt toate funcționale, doar {vent}.",
  "În chirurgie, salonul de lângă sala de operație {room}.",
  "The step-down patients mostly need {needs}, not full intensive care.",
 ],
 "t3": [
  "Toate cele patru tulpini au avut același profil de rezistență, ceea ce sugerează {spread}.",
  "Изоляторов у нас {iso}, и они почти всегда заняты.",
  "Consumul de soluție antiseptică pe secție a fost {gel} litri luna aceasta.",
  "Swabs from the ICU sinks came back {sinks}.",
  "Personalul de curățenie lucrează {cleaning}.",
  "По наблюдениям, гигиену рук соблюдают {compliance} процентов персонала.",
  "Doi dintre pacienți au venit transferați din {origin}.",
  "Laboratorul are nevoie de {lab} zile pentru confirmare.",
  "In the surgical ward the gel dispensers {dispensers}.",
 ],
 "t4": [
  "Lista de așteptare are acum {queue} pacienți.",
  "The endoscopy suite runs {sessions} sessions a week.",
  "Из-за очереди часть пациентов уходит {elsewhere}.",
  "Asistenta de endoscopie lipsește {absence}.",
  "Colonoscopiile de screening ocupă cam {share} la sută din program.",
  "Dezinfecția endoscoapelor durează {disinfect} minute per aparat.",
  "Pacienții se plâng la telefon că {complaint}.",
  "На субботу нужен {staff}, иначе смену не закрыть.",
  "Only {scopes} scopes are working, the fourth is at the service centre.",
 ],
 "t5": [
  "Stocul actual ajunge pentru {stock} zile la consumul obișnuit.",
  "Самый большой расход в {ward}.",
  "Furnizorul spune că problema e {supplier}.",
  "The alternative product has the same {same}, only the packaging differs.",
  "Farmacia a verificat {checked}.",
  "Consumul pe cardiologie a fost {cons} doze săptămâna aceasta.",
  "Для профилактики тромбозов после операций {prophylaxis}.",
  "Cheltuiala suplimentară ar fi în jur de {extra_cost} lei.",
 ],
 "t6": [
  "Anul acesta avem {residents} rezidenți noi în primul an.",
  "Weekend nights at admissions see around {night_adm} patients.",
  "Резиденты жалуются, что {complaint}.",
  "Medicii seniori acoperă deja {senior} gărzi pe lună.",
  "La ultima gardă, un rezident {incident}.",
  "Programul de rezidențiat cere {requirement}.",
 ],
}

SLOTS = {
 "aside": ["Mulțumesc.", "Închideți ușa, vă rog.", "Microfonul face ecou.", "Mai așteptăm un coleg de la chirurgie.", "Am trimis materialele aseară pe e-mail."],
 "online": ["вас слышно?", "включите, пожалуйста, микрофоны только когда говорите.", "у нас пропадает звук.", "видите слайды?"],
 "coffee": ["iar nu funcționează.", "s-a stricat din nou.", "a fost reparată ieri, dar tot curge."],
 "pager": ["it was the emergency room, nothing urgent.", "I'll call them back after this.", "it was the lab about a result."],
 "sat": ["84", "86", "88", "82"], "sat2": ["93", "94", "95"],
 "creat": ["160", "180", "210"],
 "xray": ["infiltrat bazal drept", "revărsat pleural bilateral mic", "congestie pulmonară moderată"],
 "bnp": ["peste 1500", "în jur de 2200", "aproape 3000"],
 "comorb": ["diabet zaharat de tip 2", "fibrilație atrială permanentă", "boală cronică de rinichi"],
 "bp": ["95 pe 60", "100 pe 65", "90 pe 55"],
 "wbc": ["14", "16", "18"], "crp": ["120", "150", "210"],
 "family": ["visiting hours", "the discharge plan", "whether he can go home soon"],
 "therapy": ["диуретики внутривенно", "антибиотикотерапию", "инотропную поддержку"],
 "drain": ["secreție seroasă", "secreție tulbure", "debit mic"],
 "night": ["un episod de tahicardie", "o febră de 38,6", "desaturare la 88"],
 "occ": ["92", "95", "97"], "days": ["30", "60", "90"],
 "adm": ["шести", "восьми", "десяти"],
 "extra": ["day", "two days", "night"],
 "los": ["4,2", "5,1", "3,8"],
 "districts": ["din nordul țării", "din Ungheni și Orhei", "din sud"],
 "bottleneck": ["персонале", "переводах в отделения", "ночных сменах"],
 "nurses": ["trei", "patru"],
 "vent": ["unul e la verificarea anuală", "senzorul de flux al unuia trebuie schimbat"],
 "room": ["e folosit acum ca depozit", "are deja prize de oxigen", "are nevoie doar de monitoare"],
 "needs": ["monitoring and oxygen", "close nursing observation", "a monitor and frequent checks"],
 "spread": ["o transmitere în interiorul spitalului", "o sursă comună"],
 "iso": ["всего два", "три", "только в реанимации"],
 "gel": ["cu 20 la sută mai puțini", "aproape la fel ca", "mai mulți decât"],
 "sinks": ["positive in two of six", "negative this time", "positive in one"],
 "cleaning": ["pe două ture", "cu un om mai puțin", "după alt grafic de la 1 septembrie"],
 "compliance": ["около шестидесяти", "примерно семьдесят", "меньше семидесяти"],
 "origin": ["alte spitale", "spitalele raionale", "secții de reabilitare"],
 "lab": ["două", "trei"],
 "dispensers": ["are often empty on night shifts", "were moved to the corridor", "are refilled only twice a day"],
 "queue": ["peste 300", "aproape 280", "în jur de 320"],
 "sessions": ["eight", "nine", "ten"],
 "elsewhere": ["в частные клиники", "в другие больницы", "с направлением обратно к семейному врачу"],
 "absence": ["două zile pe săptămână", "în concediu medical", "pentru că e la curs"],
 "share": ["30", "40", "25"],
 "disinfect": ["40", "45", "50"],
 "complaint": ["nu pot obține o dată", "așteaptă prea mult rezultatul", "не успевают отдыхать после ночи"],
 "staff": ["анестезиолог", "второй эндоскопист", "техник по дезинфекции"],
 "scopes": ["three", "only three"],
 "stock": ["zece", "opt", "douăsprezece"],
 "ward": ["хирургии", "кардиологии", "реанимации"],
 "supplier": ["la fabricant", "la vamă", "în transportul din Europa"],
 "same": ["active substance and dose", "strength and route"],
 "checked": ["certificatele produsului", "prețurile din ultimele trei luni", "ce au alte spitale în stoc"],
 "cons": ["120", "140", "160"],
 "prophylaxis": ["расход самый стабильный", "используем больше всего", "нужна основная часть запаса"],
 "extra_cost": ["40 de mii", "55 de mii", "60 de mii"],
 "residents": ["nouă", "unsprezece", "doisprezece"],
 "night_adm": ["fifteen", "twenty", "twenty five"],
 "senior": ["patru", "cinci", "șase"],
 "incident": ["a sunat seniorul abia dimineața", "a avut trei internări simultan", "a rămas singur cu un pacient în stare gravă"],
 "requirement": ["un număr minim de gărzi supravegheate", "un curs de resuscitare în primul semestru"],
}

# (speaker, text, tags) or ("FILL", topic, words)
SCRIPT = [
 (1, "Bună ziua, colegi. Începem ședința Consiliului Medical. Avem șase subiecte pe agendă: cazurile clinice, capacitatea ATI, infecțiile nosocomiale, lista de așteptare la endoscopie, stocurile farmaciei și graficul de gărzi al rezidenților.", ""),
 (1, "Добрый день всем, кто подключился онлайн. Мы начинаем.", ""),
 ("FILL", "generic", 120),
 # T1 clinical cases
 (1, "Primul subiect, cazurile clinice. Vă rog, cardiologia.", ""),
 (2, "Pacientul Vasile Ceban, 72 de ani, salonul 8, internat cu insuficiență cardiacă decompensată și pneumonie.", "PAT:Vasile Ceban"),
 ("FILL", "t1", 400),
 (2, "Propun să-l transferăm în terapia intensivă cardiologică pentru monitorizare continuă.", ""),
 (3, "Avem un pat liber în terapia intensivă cardiologică din seara asta.", ""),
 (1, "Deci transferăm pacientul din salonul 8 în terapia intensivă cardiologică astăzi. De acord?", ""),
 (4, "De acord.", "D:icu_transfer"),
 (3, "Pregătesc eu patul și anunț echipa de gardă mâine dimineață.", "A:bed_prep:Speaker 3:2026-09-25"),
 ("FILL", "t1", 250),
 (4, "Al doilea caz. Pacienta Elena Botnaru, 54 de ani, patul 5 în chirurgie, a treia zi după rezecție de colon, cu febră.", "PAT:Elena Botnaru"),
 (4, "Я предлагаю повторную операцию сегодня вечером.", ""),
 (1, "Atunci reintervenția rămâne programată pentru diseară.", "OLD:reop"),
 ("FILL", "t1", 160),
 (5, "Stați, CT-ul de dimineață nu arată colecție. O reintervenție fără colecție e riscantă.", ""),
 (3, "Лучше сначала сделать пункцию под контролем УЗИ.", ""),
 (1, "Atunci anulăm reintervenția de diseară. Facem puncție ghidată ecografic și reevaluăm după rezultat. Toți de acord?", ""),
 (4, "Da, de acord, anulăm reintervenția.", "D:reop"),
 (4, "Programez eu puncția la radiologie pentru mâine la prima oră.", "A:puncture:Speaker 4:2026-09-25"),
 (6, "Poate ar trebui să trecem toată secția de chirurgie pe alt antibiotic profilactic?", "NOTD"),
 (1, "Asta ține de al treilea subiect, nu acum.", ""),
 ("FILL", "t1", 200),
 # T2 ICU capacity; the proposal is settled after a long discussion
 (1, "Al doilea subiect, capacitatea ATI pentru octombrie.", ""),
 (3, "В реанимации двенадцать коек, в среднем занято одиннадцать. В выходные бывает перегрузка.", ""),
 ("FILL", "t2", 400),
 (3, "Propun să deschidem două paturi de terapie intermediară în secția de chirurgie, ca tampon pentru ATI.", "P:intermediate"),
 ("FILL", "t2", 850),
 (7, "Pentru două paturi intermediare ar trebui încă o asistentă pe tură.", ""),
 ("FILL", "t2", 850),
 (1, "Revenind la propunerea de la începutul subiectului: aprobăm deschiderea a două paturi de terapie intermediară în chirurgie, cu o asistentă în plus pe tură.", "D:intermediate"),
 (7, "Refac eu graficul asistentelor în două săptămâni.", "A:nurse_rota:Speaker 7:2026-10-08"),
 (3, "Și în weekendurile cu ocupare peste 90 la sută, propun să suspendăm internările programate care pot ajunge în ATI.", ""),
 (1, "Aprobăm: în weekendurile cu ocupare a ATI peste 90 la sută, internările programate cu risc de ATI se amână.", "D:elective_hold"),
 (3, "Trimit eu anunțul către secțiile chirurgicale până la sfârșitul săptămânii.", "A:hold_notice:Speaker 3:2026-09-25"),
 (2, "And maybe we should buy a second portable ultrasound for the ICU?", "NOTD"),
 (1, "Asta o discutăm la bugetul pe anul viitor.", ""),
 ("FILL", "t2", 150),
 # T3 hospital infections; the audit frequency is reversed
 (1, "Al treilea subiect, infecțiile nosocomiale. Epidemiologia, vă rog.", ""),
 (5, "În septembrie am avut patru cazuri de Klebsiella producătoare de carbapenemaze în ATI și chirurgie.", ""),
 ("FILL", "t3", 400),
 (5, "Propun screening prin tampon rectal la internare pentru toți pacienții transferați din alte spitale.", ""),
 (3, "Это разумно, у нас половина случаев именно переводы.", ""),
 (1, "Aprobăm screeningul la internare pentru pacienții transferați din alte spitale.", "D:screening"),
 (5, "Pregătesc eu procedura și o trimit secțiilor până vineri.", "A:screening_sop:Speaker 5:2026-09-25"),
 ("FILL", "t3", 220),
 (5, "Auditul igienei mâinilor rămâne o dată pe trimestru, ca până acum.", "OLD:hand_audit"),
 ("FILL", "t3", 110),
 (7, "Cu patru cazuri într-o lună, o dată pe trimestru e prea rar. Propun lunar, cel puțin până la final de an.", ""),
 (1, "Corect. Auditul igienei mâinilor devine lunar până la sfârșitul anului. Obiecții? Nu.", "D:hand_audit"),
 (7, "Первый ежемесячный аудит проведу до конца месяца.", "A:hand_audit_first:Speaker 7:2026-09-30"),
 (6, "Поставим дозаторы с антисептиком у каждой кровати?", "NOTD"),
 (1, "Vedem după primul audit.", ""),
 ("FILL", "t3", 200),
 # T4 endoscopy waiting list; the Saturday pilot is settled much later
 (1, "Al patrulea subiect, lista de așteptare la endoscopie.", ""),
 (2, "The waiting list for elective colonoscopy is now seven weeks.", ""),
 ("FILL", "t4", 350),
 (4, "Propunem să adăugăm o zi de endoscopie sâmbăta, cu o echipă prin rotație.", "P:saturday"),
 ("FILL", "t4", 850),
 (2, "Patients with alarm signs should not wait in the same queue as screening.", ""),
 (1, "Aprobăm: pacienții cu semne de alarmă primesc endoscopie în 72 de ore, în afara listei.", "D:red_flags"),
 (2, "Pregătesc criteriile de alarmă săptămâna viitoare.", "A:red_flag_criteria:Speaker 2:"),
 ("FILL", "t4", 850),
 (1, "Să revenim la propunerea cu endoscopia de sâmbătă. Pilotăm o zi de endoscopie sâmbăta timp de o lună, apoi evaluăm lista de așteptare.", ""),
 (2, "Agreed, a one-month pilot makes sense.", "D:saturday"),
 (4, "I'll draw up the weekend team rota by next Wednesday.", "A:saturday_rota:Speaker 4:2026-09-30"),
 (3, "Может, вообще перейти на двухсменную работу эндоскопии?", "NOTD"),
 (1, "Prea devreme, întâi vedem pilotul.", ""),
 ("FILL", "t4", 200),
 # T5 pharmacy
 (1, "Al cincilea subiect, farmacia.", ""),
 (6, "Heparina cu greutate moleculară mică se termină. Furnizorul întârzie livrarea cu trei săptămâni.", ""),
 ("FILL", "t5", 400),
 (6, "Предлагаю закупить у второго поставщика на месяц, цена выше на двенадцать процентов.", ""),
 (1, "Aprobăm achiziția de urgență de la al doilea furnizor pentru o lună.", "D:heparin"),
 (6, "Оформлю заказ до понедельника.", "A:heparin_order:Speaker 6:2026-09-28"),
 ("FILL", "t5", 220),
 (2, "Și pentru cardiologie, restricționăm heparina la indicațiile stricte până vine livrarea?", ""),
 (1, "Da. Până la livrare, heparina se prescrie doar pentru indicațiile din protocol, cu avizul farmacistului clinician. Aprobat.", "D:heparin_restrict"),
 (6, "Trimit eu lista indicațiilor tuturor secțiilor până marți.", "A:heparin_list:Speaker 6:2026-09-29"),
 ("FILL", "t5", 220),
 # T6 resident rota
 (1, "Ultimul subiect, graficul de gărzi al rezidenților pentru octombrie.", ""),
 (7, "Rezidenții de anul întâi fac acum gărzi singuri în weekend la internare.", ""),
 ("FILL", "t6", 380),
 (2, "Предлагаю, чтобы в первые три месяца резиденты дежурили только в паре со старшим врачом.", ""),
 (4, "Da, de acord, e mai sigur pentru pacienți.", "D:resident_pairs"),
 (1, "Cine reface graficul?", ""),
 (2, "Îl refac eu, de îndată ce primesc lista rezidenților.", "A:resident_rota:Speaker 2:"),
 (5, "Și cursul de resuscitare pentru rezidenți?", ""),
 (1, "Cursul de resuscitare devine obligatoriu pentru toți rezidenții noi. Aprobat.", "D:bls"),
 (3, "Îl organizez eu în zece zile.", "A:bls_course:Speaker 3:2026-10-04"),
 (7, "Poate facem și o întâlnire informală cu rezidenții noi?", "NOTD"),
 (1, "Mai vedem.", ""),
 ("FILL", "generic", 100),
 (1, "Mulțumesc tuturor. Ne vedem la ședința următoare.", ""),
]



def _filler(rng, topic, words):
    out, n = [], 0
    while n < words:
        text = rng.choice(FILLER[topic])
        text = text.format(**{k: rng.choice(v) for k, v in SLOTS.items() if "{" + k + "}" in text})
        folded = fold(text)
        assert not any(a in folded for a in DECISION_ACTS) and not set(re.findall(r"\w+", folded)) & set(AGREEMENT_WORDS), \
            f"filler carries a decision word: {text}"
        speaker = rng.choice((2, 3, 4, 5, 6, 7)) if topic != "generic" else rng.choice((1, 1, 3, 6))
        out.append((speaker, text, ""))
        n += len(text.split())
    return out


def script() -> list:
    rng = random.Random(SEED)
    out = []
    for row in SCRIPT:
        out.extend(_filler(rng, row[1], row[2]) if row[0] == "FILL" else [row])
    return out


def stamps(rows) -> list:
    """Clock times proportional to words spoken, the whole meeting ~MINUTES long."""
    words = [len(r[1].split()) for r in rows]
    per_word, t, out = MINUTES * 60 / sum(words), 3.0, []
    for w in words:
        s = int(t)
        out.append(f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}")
        t += w * per_word
    return out


LONG = {"long01": ("medical", script())}


def build(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    return {mid: write(out, mid, mtype, rows, stamps(rows)) for mid, (mtype, rows) in LONG.items()}


if __name__ == "__main__":
    for k, v in build(Path(__file__).resolve().parent / "data").items():
        print(k, v)

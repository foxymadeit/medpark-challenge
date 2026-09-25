"""What a person reads aloud to enroll their voice: about 25 seconds at a
normal pace, the same short board-meeting announcement in each language.

Each passage has the numbers, weekdays, times and requests people say in
meetings, one question (rising pitch) and a thank-you (falling, softer),
and the sounds each language leans on: th, sh, ch, j and ng in English;
ă, î, ș, ț and the soft ce/gi in Romanian; ы, ж, ш, ч, х, й and soft
consonants in Russian. Bilingual staff read two, and the tracker keeps
both as prototypes of one person.
"""

PASSAGES = {
    "en": (
        "Good morning, everyone. Before we start, please check the schedule on the board: "
        "the cardiac review moves to Thursday at half past three. Did the lab send the blood "
        "results for bed twelve? If not, I will call them myself. We need six fresh gowns, "
        "two oxygen masks and a new thermometer by Monday. Thank you, and let's keep this short."
    ),
    "ro": (
        "Bună dimineața tuturor. Înainte să începem, verificați programul de pe tablă: "
        "ședința de cardiologie se mută joi, la trei și jumătate. A trimis laboratorul "
        "analizele pentru patul doisprezece? Dacă nu, îi sun chiar eu. Avem nevoie de șase "
        "halate curate, două măști de oxigen și un termometru nou până luni. "
        "Mulțumesc și să fim scurți."
    ),
    "ru": (
        "Доброе утро, коллеги. Прежде чем начать, проверьте расписание на доске: "
        "кардиологический разбор переносится на четверг, в половине четвёртого. Лаборатория "
        "уже прислала анализы для двенадцатой палаты? Если нет, я позвоню им лично. Нам нужны "
        "шесть чистых халатов, две кислородные маски и новый термометр к понедельнику. "
        "Спасибо, давайте коротко."
    ),
}

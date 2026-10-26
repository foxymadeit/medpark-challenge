// EXAMPLE DATA — not real people. The whole hospital directory used by the demo, in one place: edit freely.
// Moldovan names (mostly Romanian, some Russian), no first name or surname used twice, "Dr." only for physicians.
// `meetingType` = the meetings this person usually attends; `default: true` puts them in that type's pre-filled list
// on New meeting (keep 4–5 per type). Emails are built from the name (see `emailFor`).
import type { Access, MeetingType } from '../types';

export interface DirectoryEntry {
  id: string;
  name: string;
  role: string;
  meetingType: MeetingType;
  access: Access;
  default?: true;
}

/** The signed-up user always gets this id. */
export const YOU_ID = 'p-you';

export const directory: DirectoryEntry[] = [
  // ── Medical: heads of department, physicians, senior nurses, nurses, pharmacist ──
  { id: YOU_ID, name: 'Dr. Ana Popescu', role: 'Head of Cardiology', meetingType: 'medical', access: 'admin', default: true },
  { id: 'p-igor', name: 'Dr. Igor Rusu', role: 'Anesthesiologist', meetingType: 'medical', access: 'organizer', default: true },
  { id: 'p-elena', name: 'Elena Ciobanu', role: 'Head Nurse, ICU', meetingType: 'medical', access: 'receives', default: true },
  { id: 'p-victor', name: 'Dr. Victor Lungu', role: 'Surgeon', meetingType: 'medical', access: 'receives', default: true },
  { id: 'p-natalia', name: 'Natalia Ceban', role: 'Ward Nurse, Cardiology', meetingType: 'medical', access: 'receives', default: true },
  { id: 'p-bogdan', name: 'Dr. Bogdan Munteanu', role: 'Head of Surgery', meetingType: 'medical', access: 'organizer' },
  { id: 'p-diana', name: 'Dr. Diana Gheorghiu', role: 'Head of Paediatrics', meetingType: 'medical', access: 'organizer' },
  { id: 'p-florin', name: 'Dr. Florin Bostan', role: 'Head of Neurology', meetingType: 'medical', access: 'organizer' },
  { id: 'p-galina', name: 'Dr. Galina Kozlova', role: 'Head of Oncology', meetingType: 'medical', access: 'organizer' },
  { id: 'p-horia', name: 'Dr. Horia Cazacu', role: 'Head of Intensive Care', meetingType: 'medical', access: 'organizer' },
  { id: 'p-jana', name: 'Dr. Jana Plămădeală', role: 'Cardiologist', meetingType: 'medical', access: 'receives' },
  { id: 'p-kirill', name: 'Dr. Kirill Smirnov', role: 'Neurologist', meetingType: 'medical', access: 'receives' },
  { id: 'p-liliana', name: 'Dr. Liliana Turcanu', role: 'Paediatrician', meetingType: 'medical', access: 'receives' },
  { id: 'p-nicolae', name: 'Dr. Nicolae Railean', role: 'Oncologist', meetingType: 'medical', access: 'receives' },
  { id: 'p-octavian', name: 'Dr. Octavian Gaina', role: 'Radiologist', meetingType: 'medical', access: 'receives' },
  { id: 'p-pavel', name: 'Pavel Rusnac', role: 'Senior Nurse, Surgery', meetingType: 'medical', access: 'receives' },
  { id: 'p-rodica', name: 'Rodica Lupașcu', role: 'Senior Nurse, Paediatrics', meetingType: 'medical', access: 'receives' },
  { id: 'p-ecaterina', name: 'Ecaterina Bejan', role: 'Nurse, Neurology', meetingType: 'medical', access: 'receives' },
  { id: 'p-zinaida', name: 'Zinaida Ostapenco', role: 'Nurse, Oncology', meetingType: 'medical', access: 'receives' },
  { id: 'p-lucia', name: 'Lucia Vrabie', role: 'Clinical Pharmacist', meetingType: 'medical', access: 'receives' },

  // ── Executive: directors, deputies, legal ──
  { id: 'p-ion', name: 'Dr. Ion Moraru', role: 'Hospital Director', meetingType: 'executive', access: 'organizer', default: true },
  { id: 'p-svetlana', name: 'Dr. Svetlana Cojocaru', role: 'Medical Director', meetingType: 'executive', access: 'organizer', default: true },
  { id: 'p-andrei', name: 'Andrei Botnaru', role: 'Chief Financial Officer', meetingType: 'executive', access: 'organizer', default: true },
  { id: 'p-veronica', name: 'Veronica Lupu', role: 'Director of Quality', meetingType: 'executive', access: 'organizer', default: true },
  { id: 'p-constantin', name: 'Constantin Dabija', role: 'Chief Operating Officer', meetingType: 'executive', access: 'organizer' },
  { id: 'p-eugen', name: 'Eugen Spătaru', role: 'IT Director', meetingType: 'executive', access: 'organizer' },
  { id: 'p-alina', name: 'Alina Tîcu', role: 'Legal Counsel', meetingType: 'executive', access: 'receives' },
  { id: 'p-gheorghe', name: 'Dr. Gheorghe Ursachi', role: 'Deputy Medical Director', meetingType: 'executive', access: 'organizer' },
  { id: 'p-mariana', name: 'Mariana Sîrbu', role: 'Deputy General Director', meetingType: 'executive', access: 'organizer' },
  { id: 'p-boris', name: 'Boris Fedorov', role: 'Deputy Finance Director', meetingType: 'executive', access: 'receives' },
  { id: 'p-felicia', name: 'Felicia Năstase', role: 'Director of Nursing', meetingType: 'executive', access: 'organizer' },
  { id: 'p-petru', name: 'Petru Zgardan', role: 'Head of Strategy', meetingType: 'executive', access: 'receives' },
  { id: 'p-valentina', name: 'Dr. Valentina Hâncu', role: 'Director of Research', meetingType: 'executive', access: 'receives' },
  { id: 'p-tudor', name: 'Tudor Pînzaru', role: 'Chief Compliance Officer', meetingType: 'executive', access: 'receives' },
  { id: 'p-lilia', name: 'Lilia Codreanu', role: 'Head of Communications', meetingType: 'executive', access: 'receives' },
  { id: 'p-radu', name: 'Radu Furtună', role: 'Head of Partnerships', meetingType: 'executive', access: 'receives' },
  { id: 'p-stela', name: 'Stela Gavriliuc', role: 'Board Secretary', meetingType: 'executive', access: 'receives' },
  { id: 'p-dorin', name: 'Dorin Chiriac', role: 'Director of Patient Safety', meetingType: 'executive', access: 'receives' },
  { id: 'p-inga', name: 'Inga Bălan', role: 'Deputy Operations Director', meetingType: 'executive', access: 'receives' },
  { id: 'p-nadejda', name: 'Nadejda Volkova', role: 'Deputy IT Director', meetingType: 'executive', access: 'receives' },

  // ── Administrative: HR, accounting, procurement, registration, IT support, facilities, office, legal assistant ──
  { id: 'p-maria', name: 'Maria Rotaru', role: 'Hospital Administrator', meetingType: 'administrative', access: 'organizer', default: true },
  { id: 'p-tatiana', name: 'Tatiana Ursu', role: 'HR Manager', meetingType: 'administrative', access: 'organizer', default: true },
  { id: 'p-mihai', name: 'Mihai Cebotari', role: 'Finance Officer', meetingType: 'administrative', access: 'receives', default: true },
  { id: 'p-sergiu', name: 'Sergiu Melnic', role: 'Procurement Specialist', meetingType: 'administrative', access: 'receives', default: true },
  { id: 'p-olga', name: 'Olga Grosu', role: 'Facilities Coordinator', meetingType: 'administrative', access: 'receives', default: true },
  { id: 'p-adrian', name: 'Adrian Sandu', role: 'Accountant', meetingType: 'administrative', access: 'receives' },
  { id: 'p-cornelia', name: 'Cornelia Prisăcaru', role: 'HR Specialist', meetingType: 'administrative', access: 'receives' },
  { id: 'p-daniel', name: 'Daniel Bivol', role: 'IT Support Engineer', meetingType: 'administrative', access: 'receives' },
  { id: 'p-emilia', name: 'Emilia Taran', role: 'Registrar, Front Desk', meetingType: 'administrative', access: 'receives' },
  { id: 'p-grigore', name: 'Grigore Popa', role: 'Procurement Manager', meetingType: 'administrative', access: 'organizer' },
  { id: 'p-iulia', name: 'Iulia Moldovan', role: 'Records Office Clerk', meetingType: 'administrative', access: 'receives' },
  { id: 'p-leonid', name: 'Leonid Petrov', role: 'IT Support Lead', meetingType: 'administrative', access: 'receives' },
  { id: 'p-marin', name: 'Marin Gurău', role: 'Maintenance Supervisor', meetingType: 'administrative', access: 'receives' },
  { id: 'p-nina', name: 'Nina Stratan', role: 'Payroll Accountant', meetingType: 'administrative', access: 'receives' },
  { id: 'p-oleg', name: 'Oleg Kuznetsov', role: 'Warehouse Coordinator', meetingType: 'administrative', access: 'receives' },
  { id: 'p-paula', name: 'Paula Arnăut', role: 'Patient Registration Clerk', meetingType: 'administrative', access: 'receives' },
  { id: 'p-silvia', name: 'Silvia Toma', role: 'Legal Assistant', meetingType: 'administrative', access: 'receives' },
  { id: 'p-ulian', name: 'Ulian Cuciuc', role: 'Housekeeping Supervisor', meetingType: 'administrative', access: 'receives' },
  { id: 'p-viorica', name: 'Viorica Negru', role: 'Secretary, General Office', meetingType: 'administrative', access: 'receives' },
  { id: 'p-zoia', name: 'Zoia Bîrcă', role: 'Billing Specialist', meetingType: 'administrative', access: 'receives' },
];

/** first.last@medpark.md, without diacritics or titles ("Dr. Jana Plămădeală" → jana.plamadeala@medpark.md). */
export function emailFor(name: string): string {
  const parts = name
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .split(/\s+/)
    .filter((w) => !/^(dr|prof)\.?$/.test(w));
  return `${parts[0]}.${parts[parts.length - 1]}@medpark.md`;
}

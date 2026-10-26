// EXAMPLE default participants per meeting type, pre-filled on New meeting.
// Edit freely: switching the meeting type replaces the list with the one below.
// Names that match someone in the directory (Participants page) become that person, with their email;
// any other name is added to the meeting as a guest without an email.
import type { MeetingType } from '../types';

export interface DefaultParticipant {
  name: string;
  role: string;
}

export const defaultParticipants: Record<MeetingType, DefaultParticipant[]> = {
  medical: [
    { name: 'Dr. Ana Popescu', role: 'Head of Cardiology' },
    { name: 'Dr. Igor Rusu', role: 'Anesthesiologist' },
    { name: 'Elena Ciobanu', role: 'Head Nurse, ICU' },
    { name: 'Dr. Victor Lungu', role: 'Surgeon' },
    { name: 'Natalia Ceban', role: 'Ward Nurse, Cardiology' },
  ],
  executive: [
    { name: 'Dr. Ion Moraru', role: 'Hospital Director' },
    { name: 'Dr. Svetlana Cojocaru', role: 'Medical Director' },
    { name: 'Andrei Botnaru', role: 'Chief Financial Officer' },
    { name: 'Veronica Lupu', role: 'Head of Quality' },
  ],
  administrative: [
    { name: 'Maria Rotaru', role: 'Hospital Administrator' },
    { name: 'Tatiana Ursu', role: 'HR Manager' },
    { name: 'Mihai Cebotari', role: 'Finance Officer' },
    { name: 'Sergiu Melnic', role: 'Procurement Specialist' },
    { name: 'Olga Grosu', role: 'Facilities Coordinator' },
  ],
};

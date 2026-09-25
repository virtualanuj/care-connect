# CareConnect — Intent

## Problem

Front-desk staff at the clinic currently manage doctor scheduling, patient
booking, and the daily walk-in/no-show queue manually (phone, paper, or
disconnected tools). There is no consistent way to prevent double-booking,
enforce cancellation and follow-up policies, or reserve emergency capacity.
Doctors have no structured pre-visit context on why a patient is coming in,
and visit documentation is entirely manual.

## Proposed outcome (measurable)

- Zero double-bookings (same doctor or same patient, overlapping times) —
  enforced, not just monitored.
- Front-desk can view and manage the full day's queue (booked, checked-in,
  walk-ins, no-shows) from a single dashboard, replacing manual tracking.
- Every appointment enforces clinic policy automatically: cancellations
  blocked inside the cutoff window, a configurable number of emergency slots
  held back per doctor per day, follow-ups constrained to the policy window.
- AI-assisted symptom triage (urgency + suggested specialty) is available to
  front-desk at booking time, with a visible safety disclaimer, and can
  always be overridden by staff.
- Doctors receive an AI-generated pre-visit summary before each consultation
  and can turn their notes into a draft visit summary.

## Features

**Scheduling & availability**
- Doctor profiles with specialty and weekly recurring availability, plus
  one-off exceptions (holidays, extra hours).
- Bookable slots derived from availability, sized per doctor.
- A configurable number of slots per doctor per day held back for
  emergencies, bookable only through an explicit emergency path.
- Booking supports both a specific doctor and a specialty-wide search
  (e.g. "any available cardiologist"), returning the first matching slot
  across all doctors in that specialty.

**Patients**
- Patient registration with basic demographics and contact info.
- A simple, append-only medical history log per patient (not a full chart).

**Booking & lifecycle**
- Book, reschedule, and cancel appointments, with no double-booking for
  either the doctor or the patient.
- Cancellations blocked inside a configurable cutoff window before the
  appointment; front-desk can force-cancel with an explicit override.
- Appointment lifecycle: Booked → Checked-in → In-consultation →
  Completed / No-show / Cancelled.
- Follow-up booking linked to the original visit, constrained to a
  configurable maximum number of days out.

**Front-desk operations**
- A daily dashboard showing the queue: booked appointments, walk-ins,
  in-progress consultations, completions, and no-shows for the day.
- Walk-in registration and booking against emergency-held capacity when no
  regular slot is available.

**Visit documentation**
- Doctors record visit notes tied to each appointment.
- Follow-up appointments can be booked directly from a completed visit.

**AI-native features**
- Symptom pre-triage: patient-reported symptoms produce a suggested urgency
  (emergency / urgent / routine) and specialty, shown with a safety
  disclaimer; staff can always override the result.
- A pre-visit summary assembled for the doctor from patient history,
  reported symptoms, and the triage result.
- A draft visit summary generated from the doctor's raw notes, which the
  doctor reviews and finalizes.

## Affected users and systems

- **Front-desk admin**: primary user — registers patients, books/reschedules
  /cancels appointments, runs the daily queue, records walk-ins and no-shows.
- **Doctor**: sets weekly availability, views their schedule, reviews AI
  pre-visit summaries, writes visit notes, drafts follow-ups.
- **Patient**: not a direct system user in v1 — represented as a record only;
  all interaction happens through front-desk staff.
- **External system**: Gemini API, used for symptom triage and note/summary
  drafting.

## Constraints

- Single clinic, single physical location (no multi-tenancy).
- Patients do not get their own login/portal in v1 — front-desk mediated
  only.
- Staff auth is email/password for v1; social login is a deferred fast-follow.
- AI outputs (triage, summaries) are advisory only — staff can always
  override, and a safety disclaimer must accompany any triage result.
- Business-rule correctness (no double-booking, cancellation window,
  emergency holdback, follow-up window) is the highest-priority, TDD-covered
  part of the system.
- No HIPAA-equivalent or other regulatory compliance requirement for
  patient data storage in v1.

## Out of scope

- Patient-facing portal or self-service booking.
- Multi-location or multi-tenant support.
- Billing, insurance, or payment processing.
- Full EHR (medical history is a simple record list, not a clinical chart).
- Social login / SSO (deferred).

## Open questions

- Exact default values for cancellation cutoff, emergency-slot count, and
  follow-up window — proposed as configurable defaults, need clinic sign-off.

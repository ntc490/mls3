# Household Appointments - Implementation Plan

## Overview
Let one appointment cover the heads of a household ("David and Lisa Smith")
instead of a single member. This is deliberately not a free-form multi-member
appointment: every group appointment in practice has been a family unit, and a
household gives a group a natural name without any new UI for picking people.

A future, separate idea - an arbitrary group shown as "First Last (group) -
Type" with the other participants in Notes - needs no schema change and is not
part of this plan.

## Data
- `appointments.csv` gains one optional column, `household` (`True`/`False`,
  like the member booleans).
- `member_id` stays the person picked; the household and its heads are looked
  up when needed, so names follow a re-import.
- Older files load unchanged - a missing column means "not a household
  appointment".

## Heads of household
- `MemberDatabase.get_heads(household_id)` - the heads, including whoever was
  picked. Factored out of `get_parents()`, which keeps its behaviour (heads
  other than the member themselves).
- In-ward heads count even when inactive: an inactive spouse is still part of
  the household; only the default (below) looks at `active`.

## Templates: `{name}` covers several people
No new templates. The expander takes a list of people (default `[member]`) and
names them together:

| | 1 person | 2, same last name | 2, different last names |
|---|---|---|---|
| formal | Brother Smith | Brother and Sister Smith | Brother Smith and Sister Jones |
| casual | David | David & Lisa | David & Lisa |
| full | David Smith | David and Lisa Smith | David Smith and Lisa Jones |

- A `?flag` condition is true if anyone in the group has the flag.
- `{parent_greeting}` becomes the same naming applied to the parents, removing
  two copies of that code and fixing "Brother and Sister {first parent's last
  name}" when parents' last names differ.
- Appointment templates only say "you"/"your", so they read correctly for one
  person or two.

## Pronouns
`_parent` templates talk about the child, and used "they/them/their". New
tokens follow the subject's recorded gender:

| Token | M | F | missing |
|---|---|---|---|
| `{he}` | he | she | he/she |
| `{him}` | him | her | him/her |
| `{his}` | his | her | his/her |

## SMS
Household appointments send one group text to the heads' phones (the same
`;`-joined `smsto:` used for parents of minors). Heads without a phone are
skipped; it's an error only if none have one.

## Display and history
- Calendar title, home and events cards use the full group name:
  "David and Lisa Smith - Tithing".
- The appointment appears in every head's history, not just the picked member's.

## Defaults
`appointment_types.yaml` gains `default_household`. The scheduler shows a
"Whole household - David and Lisa Smith" checkbox only when the picked
member is one of two or more heads, and starts it checked when:
- `default_household: true` (Family) - always.
- `default_household: active_heads` (Tithing) - every head is active, so an
  inactive spouse leaves it off.

Only a head books for the household. An appointment picked through a child is
the child's - named for the child, with the `_parent` texts going to every
parent with a phone - and a household appointment whose household is down to
one head becomes that member's own.

## Build order (one commit each)
1. Pronoun tokens and the three template fixes, with tests
2. `get_heads()` and the `household` column, with tests
3. `{name}` covering several people; `parent_greeting` from the same helper
4. SMS for household appointments
5. Feeds, history for every head, calendar titles
6. `default_household` and the scheduler checkbox

---
id: news
title: News
order: 205
section: research
audience: all
summary: Follow what is new in mathematics — papers by field, open problems, Lean and Mathlib, AI for maths — and send it to a project.
---

# News

The **News** screen (logo menu) gathers what is new in mathematics. Madalean fetches it for you, from time to time,
from public addresses; everything is kept on the host computer and can be read without the Internet.

## What you find there

| Section | Sources |
|---|---|
| New papers | arXiv, every mathematics category and logic in computer science |
| Open problems | the Erdős problems (status changes), MathOverflow questions tagged “open-problems”, the Polymath blog |
| Lean and Mathlib | Lean releases, the latest additions to Mathlib, the Lean community blog, the Xena blog |
| AI for mathematics | arXiv papers about automated proving, formalisation and mathematical reasoning |
| Announcements, prizes and outreach | the AMS, Quanta Magazine, Images des mathématiques, Terence Tao's blog |
| Your feeds | the RSS or Atom addresses you add yourself |

Each item shows its source, date, authors, abstract and a link to the original page, which opens in the browser.
Madalean keeps only the title, an excerpt and the link: the full text is read on the original site.

## Sorting and searching

- **Search**: a word, an author; accents do not matter.
- **Field**: algebra, number theory, geometry, topology, analysis, partial differential equations, probability,
  statistics, combinatorics, logic, category theory, numerical analysis, optimisation, mathematical physics, history
  and education. The field comes from the category given by the source, otherwise from the words of the title and
  the abstract.
- **Unread**, **Saved**, **Open problems**.
- **My fields**: only the fields ticked in Settings › News.
- **For my projects**: the items that share rare words with your projects (titles, statements of the dossiers,
  titles of the notes and of the sources). The words in common are shown. This sorting happens on your computer:
  nothing of your projects is sent.

Opening an item marks it as read. “Save” keeps it without a time limit.

## Sending to a project

In an open item, four buttons send it to the project chosen in the top bar:

- **Add to the project's Sources** (arXiv papers): the paper enters the project's library, as if you had given its
  identifier in the Sources screen.
- **Create a conjecture**: the title and the abstract become the statement of a conjecture, with the original link.
- **Create a dossier from this problem**: a dossier is created with this text as its statement. Nothing is started:
  read and correct the statement first.
- **Send to a note**: a note with the quotation, the authors, the link and the date.

## French summary

“Summarise in French” asks a free online model for a summary of two or three sentences. The original text always
stays below it: the summary is a reading aid, not a source. The button only appears for sources whose licence allows
it (arXiv, MathOverflow, Mathlib, your own feeds); for a blog, a magazine or a learned society, Madalean keeps to
the title, the excerpt and the link. The setting “Summarise automatically” does it for a few
new items of your fields at each update.

A text that comes from the Internet may contain sentences written to mislead a program. Madalean treats it as a text
to read, never as an instruction; when it spots such sentences, it says so and does not send that text to a model.

## Updates

Every 6 hours by default, while the host computer is on and connected to the Internet. “Update” does it at once. A
source that does not answer is tried again later, less and less often.

In **Local mode**, Madalean fetches nothing: you read what is already stored.

The number of unread items appears on Home (“What's new”) and in the menu. No message ever pops up by itself.

## Settings › News

- the fields followed;
- each source, to turn on or off, with its licence and terms;
- your own RSS or Atom feeds (an `https` address of a public site);
- the frequency, how long items are kept, automatic summaries, whether the unread number is shown.

## What leaves your computer

Only anonymous reads of the addresses listed in Settings › News: no account, no key, no name, no e-mail address. If
you ask for a summary, the item's title and public abstract are sent to the online model, and nothing else. See also
[Security and privacy](security.md).

## Check it yourself

1. Logo menu › News: the list fills after “Update” (outside Local mode).
2. Tick “Open problems”: only MathOverflow questions and open Erdős problems remain.
3. Switch to Local mode, then “Update”: the button is inactive and the list stays readable.

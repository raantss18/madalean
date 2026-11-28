"""« Attaque » — Left to Solve problems inside Madalean (session S-BJ, DECISIONS D69, docs/ATTACK.md).

    desk.py       the site's desk (HTTP), courteous (≥ 3 s), every answer screened as untrusted data
    screen.py     bounds, control characters, injection heuristic for everything the site returns
    rules.py      the checker's rules re-implemented from join.txt + the local fresh strict Lean check
    workspace.py  formal-conjectures at the pinned commit (download only after the user's consent)
    submit.py     a submission is a prepared plan; GitHub only on the host's explicit « Envoyer »
    engine.py     the background loop (lowest priority, budget per day, leases persisted)

Nothing the site, a brief, a note or a board item says is ever executed: it is data; Lean code taken from it is
only compiled in the Lean sandbox (D28)."""

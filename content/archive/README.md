# Archived scripts

These scripts are **complete and render-tested, but out of niche**.

Commit `333767c` (*"chore(channel): keep published videos finance-only"*) narrowed the
channel to finance / business / markets / economics, and `pipeline/run.py::_validate_finance_niche`
now hard-refuses anything else:

```
Refusing out-of-niche job 0001: niche='history'. This channel publishes finance,
business, markets, or economics only.
```

They sat in `content/queue/` anyway, which was actively harmful: `dry-run.yml` picked
`content/queue/*.md | head -n1`, so the very first CI render always crashed on the niche
gate. The rationale for the finance-only lane — and the RPM math behind it — is in
[`docs/FINANCE.md`](../../docs/FINANCE.md).

| File | Niche | Status | Why it still exists |
|---|---|---|---|
| `0001-the-canal-that-broke-a-city.md` | history | draft | The authored **Johnstown** deep dive (`tools/deep_dive.py johnstown`) and the **Shorts** cut (`tools/shorts.py short-johnstown`) both still render from it. Keep it, or those engines lose their source script. |
| `0002-shorts-johnstown-hook.md` | history | draft | Same — Shorts source script. |

Nothing in this directory is ever picked up by `pipeline/run.py::select_jobs`, which only
globs `content/queue/`. Moving a file back into `content/queue/` re-arms it — but it will be
rejected by the niche gate unless the niche is changed first.

# CP knowledge maintenance

This is CP's adaptation of Andrej Karpathy's LLM Wiki. Codex integrates new evidence into linked Markdown pages so later chats can use the previous investigation. The [knowledge index](README.md) is the entry point, and the [update log](second-brain/log.md) records material revisions. [Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

## Sources and page conventions

| Question | Evidence to use |
| --- | --- |
| What did Dante approve? | The exact decision in its contract or approved handoff. Link to the relevant heading and record the decision date when known. |
| What does this checkout do? | The owning file and named symbol, traced through its callers. Record the branch, commit, and whether relevant files have local changes when checking the Atlas. |
| What passed in isolation? | A dated report or test result with its fixture, scope, and limitations. A test definition is a pointer to a check. |
| What runs live? | A dated observation that connects the running process, configuration and data owner, and served bundle to the visible behavior. Mark missing evidence **live status unverified**. |

Keep source material in its existing location. A Second Brain page has a decision summary, source links, evidence boundaries, open questions, and a link to the matching Atlas page. An Atlas page has a checkout stamp, the UI/API entry points, owners and shared callers, stores, failure paths, and tests by scenario. Use relative Markdown links and stable symbol names. An index entry needs a one-line scope and a link to the topic page.

## Add or update evidence

1. Start with a named source, such as an approved contract entry, changed source files, or a verification report. Find the existing topic via the index.
2. Read the source and compare it with the current page. Keep proposals, approved rules, source observations, isolated evidence, and live evidence distinct. Use **superseded** for an old rule when a later explicit decision replaced it. If code or evidence disagrees with the agreed rule, record both sides with links and the user impact. Follow the CP contract-change process if resolving it would change the rule.
3. Within the approved scope, update the existing Second Brain or Atlas page wherever the evidence changes its answer. Update both when the decision and code path both change. Add index entries only when a new topic is needed. Record the date, affected pages, source, change, and any unresolved difference in one entry in the shared log.

## Answer a question

Start from the index and open the smallest relevant set of pages. Follow the cited contract, code, or report before giving a consequential answer. Say which evidence supports the answer and identify any gap. Questions are read-only by default. If an answer reveals a durable finding, propose adding it or fold it into a documentation update Dante already approved.

## Check for drift

After a material update or when asked to review the wiki, follow the index to each affected topic. Resolve its file and heading links, search for named functions, endpoints, and test cases with `rg`, and compare the stated decision with the most recent approval. Check that each topic is indexed and linked to its companion where one exists. Check that every verification claim names its source and scope. Report stale or conflicting entries and correct them within the approved documentation scope. A source edit, live action, or new product decision follows the [CP work rules](../AGENTS.md).

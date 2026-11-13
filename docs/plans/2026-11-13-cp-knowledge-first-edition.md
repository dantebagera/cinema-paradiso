# CP Second Brain and Atlas first edition

**Status** · Dante approved completing the remaining sections on 2026-11-13. All nine roadmap areas are indexed in both guides.

## Problem and decision

The pilot and four follow-on topics established how to trace Movie and TV files, downloads, identity review, and TV Follow. The existing indexes need entries for the rest of the roadmap so a reader can start from a CP action and reach its decisions, source owners, and relevant checks.

Each area gets a paired Atlas and Second Brain page. Use existing decisions and verification records as evidence and trace the current checkout for implementation claims. The scope is documentation.

## Contracts affected and contract-change decision

The pages describe existing product behavior and preserve the decision and evidence boundaries in [CP work rules](../../AGENTS.md). The deliverables change documentation coverage. Where historical proposals, checked-out code, or dated evidence differ, record the status in the guide.

## Current design and ownership

The [knowledge index](../README.md) leads to both sets of guides and the [maintenance workflow](../knowledge-workflow.md). Existing topic pages and the shared update log carry prior evidence. The source pass uses the local Cinema Paradiso checkout on `master` at `be511f9` with existing tracked and untracked changes. The initial homepage check found listener PID `31920` on port 5000 and entry script `index-9d_Ds88k.js`. The runtime data root and live feature behavior remain unverified for this documentation pass.

## Exact behavior contract

Atlas pages name the UI and API entry points, the code and data that own the behavior, shared callers, and representative failure cases with existing tests. Second Brain pages link the applicable decisions and dated evidence and identify open or unverified claims. The paired pages link to one another and to related workflows. The index lists all fourteen topic pairs.

## Implementation sequence

1. Trace the nine remaining areas through their current source owners and compare relevant historical plans and verification records.
2. Add the nine pairs of pages, extend the indexes, and link existing guides where a workflow crosses owners.
3. Check links, anchors, code and test references, and perform independent read-only navigation checks. Record the result in the shared update log.

## Acceptance matrix

| Topic | Question a reader can trace from the index |
| --- | --- |
| Movie Follow | A release is visible on an indexer. Why is the followed movie pending, and which action triggers another scan? |
| Search and Discover | Why does a title appear in Discover but disappear under a Library search or filter? |
| Playback and Streaming | Why did a TV episode launch with a different file or fail to resume, and where does playback progress reach Home? |
| Home, Lists, and Notifications | Where does a changed watched or ownership state appear, and how does the browser learn about it? |
| Movie Maintenance | Why did a duplicate, upgrade, rename, move, or deletion action affect a particular file and its catalog records? |
| AI Features | Which provider handled a request, and at what point can an AI proposal affect CP state? |
| IPTV | Which provider and catalog own a result, and what does preview versus Apply do to its metadata? |
| Movie and TV Detail Features | Where do a title's credits, related titles, collection membership, awards, or artwork come from? |
| Settings and Shared Infrastructure | Which settings, database, frontend bundle, and background owners does an installed or portable runtime use? |

## Verification and rollout

Check the Markdown files, relative links, headings, topic pairs and indexes in the current checkout. Check named tests against test definitions. Use fresh reviewers for cross-guide discovery and compare the walkthrough to the sources. Check the final workspace against the initial Git state for unrelated edits. The evidence for this pass is documentation and read-only source discovery. Application execution, compiled UI checks, and live feature qualification are outside this documentation pass.

The first-edition audit verified navigation from `AGENTS.md` through the index to all 14 topic pairs, reciprocal links, local targets and headings, and named test pointers. Independent read-only reviewers followed a completed Movie transfer through Library publication and Following removal, and a TV version through playback progress to Home Continue Watching. See the [shared update log](../second-brain/log.md#2026-11-13--first-edition) for the source paths and evidence limits.

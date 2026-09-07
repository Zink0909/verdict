# Graduate-application release checklist

This is a finite release checklist, not a feature backlog. The scope and change
gate live in [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md).

## Automated evidence

- [x] API-free canonical demo executes the fixed protocol and reaches a bounded verdict.
- [x] Local regression suite passes: 67/67 on 2026-09-07.
- [x] Repository integrity audit passes: 41/41 on 2026-09-07.
- [x] Static public site is deployed from `docs/`.
- [x] GitHub Actions passes from a clean hosted runner: [run 34119641279](https://github.com/Zink0909/verdict/actions/runs/34119641279) on 2026-09-07.
- [x] A fresh GitHub-hosted checkout installs the application and research dependencies, passes all gates, and executes the API-free canonical demo in that run.

## Human publication decisions

- [x] Complete a source-and-license evidence review; see [`DATA_PUBLICATION_REVIEW.md`](DATA_PUBLICATION_REVIEW.md).
- [ ] Resolve every group reported by `python scripts/audit_publication.py --strict`.
- [ ] Confirm that the three internship-derived case groups are authorized for public release.
- [ ] Record redistribution permission or replace redistributed vendor/public files with lawful download instructions.
- [ ] Remove the QuantConnect panel and reconstructable derivatives from the public tree and public Git history, or record written permission for the exact artifacts.
- [ ] Decide whether to retain or externalize the 100.2 MB Complexity anchor.
- [ ] Have one reader unfamiliar with the project complete the comprehension test below.

## Thirty-second / five-minute comprehension test

Give the reader only the public homepage and do not explain the project first.

1. After 30 seconds, ask: “What is Verdict?”
2. Ask them to identify what was learned from the four source projects.
3. Ask them to start the canonical demo and explain why its conclusion is not
   simply “the model works” or “the paper is wrong.”
4. Record where they hesitated, what they thought the product was, and how long
   the demo took.

Pass criteria:

- their one-sentence answer describes evidence/validation rather than trading;
- they understand that the four projects supplied reusable lessons;
- they distinguish reproduced performance from an unsupported mechanism claim;
- they finish without needing an API key or code modification in about five minutes.

Only wording, navigation and instructions should be changed in response to this
test. A comprehension problem is not permission to add another feature.

## Freeze

- [ ] Choose whether the interactive Streamlit surface must be hosted publicly or whether the public static evidence site plus reproducible local demo is sufficient.
- [ ] Update this checklist with final evidence links and decisions.
- [ ] Create the `v1.0.0` release tag.
- [ ] Mark the graduate-application version frozen.

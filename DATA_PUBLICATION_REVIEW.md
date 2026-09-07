# Data publication review

Reviewed: 2026-09-07. This is a conservative release review, not legal advice.
It records what the repository can prove and refuses to infer permission from
technical reproducibility or public download access.

The machine-readable inventory is [`publication_data.json`](publication_data.json).
Run `python scripts/audit_publication.py --strict` before any public release tag.

## Decisions

| Group | Evidence found | Current disposition |
|---|---|---|
| Buy the Dip internship study | On 2026-09-07 the project owner confirmed that the internship-derived project material may be made public. | Approved for the owner's publication decision. Separately sourced vendor data remains subject to its own license. |
| Vol Harvest internship study | On 2026-09-07 the project owner confirmed that the internship-derived project material may be made public. | Approved for the owner's publication decision. Separately sourced vendor data remains subject to its own license. |
| Distribution Shift internship study | On 2026-09-07 the project owner confirmed that the internship-derived project material, including the de-identified saved series committed here, may be made public. | Approved for the owner's publication and de-identification decision. Separately sourced vendor data remains subject to its own license. |
| Complexity reproduction | `zivmi/voc_reproduction` declares MIT for its repository, but its input data originate elsewhere. The `nkonts` repository exposes no license in its root, and no upstream redistribution permission is recorded here for Goyal data or the authors' anchor. | Do not infer data rights from the code license. Replace redistributed upstream files with lawful download instructions or obtain permission. Retain `processed.parquet` only after its derived-data status is reviewed. Externalize the 100.2 MB `nkonts_metrics_anchor.parquet`; it is not needed by the canonical demo. |
| QuantConnect TSMOM export | QuantConnect says most hosted datasets cannot be freely redistributed and that downloaded data cannot be redistributed or converted in any format. | **Public removal required** for `panel.csv` and reconstructable derived series unless written permission covers the exact files. |
| Kenneth French factor archive | The official library makes the archive downloadable and labels the site copyright, but this review found no explicit redistribution license. | Replace the committed ZIP with a hash-pinned download step unless written permission is obtained. |

## Primary evidence links

- [QuantConnect dataset licensing](https://www.quantconnect.com/docs/v2/cloud-platform/datasets/licensing)
- [Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
- [`zivmi/voc_reproduction`](https://github.com/zivmi/voc_reproduction)
- [`nkonts/replication-the-virtue-of-complexity-in-return-prediction`](https://github.com/nkonts/replication-the-virtue-of-complexity-in-return-prediction)

## Safe release sequence

1. Make a private backup before changing history.
2. Get the three internship-owner decisions in writing.
3. Build a sanitized public tree that excludes unresolved upstream and
   internship artifacts; preserve source URLs, hashes, schemas, code and
   non-reconstructable figures where their terms permit it.
4. Because removing files from the current branch does not remove earlier Git
   objects, publish from a cleaned history or a new sanitized repository.
5. Clone that exact public repository into a clean environment, run all gates,
   then run the strict publication audit.

Do not create `v1.0.0` while any manifest group is unresolved.

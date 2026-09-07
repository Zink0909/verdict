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
| Complexity reproduction | Public pages alone did not establish redistribution rights for every upstream artifact. On 2026-09-07 the project owner confirmed that the applicable license explicitly covers storing, downloading and redistributing these exact source and transformed files through public GitHub. | Approved on the owner's specific-license attestation. Retain the 100.2 MB anchor in v1 as appendix reproducibility evidence; it is not a canonical-demo dependency. |
| QuantConnect TSMOM export | QuantConnect's general page says most hosted datasets cannot be freely redistributed. On 2026-09-07 the project owner confirmed holding a specific license that explicitly covers public GitHub storage, download and redistribution of these exact source and transformed files. | Approved on the owner's specific-license attestation, which is narrower and more specific than the conservative default from the general page. |
| Kenneth French factor archive | Public download access alone did not establish redistribution rights. On 2026-09-07 the project owner confirmed that the applicable license explicitly covers public GitHub storage, download and redistribution of this exact archive. | Approved on the owner's specific-license attestation. |

## Primary evidence links

- [QuantConnect dataset licensing](https://www.quantconnect.com/docs/v2/cloud-platform/datasets/licensing)
- [Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
- [`zivmi/voc_reproduction`](https://github.com/zivmi/voc_reproduction)
- [`nkonts/replication-the-virtue-of-complexity-in-return-prediction`](https://github.com/nkonts/replication-the-virtue-of-complexity-in-return-prediction)

## Approval record and release sequence

1. The three internship publication decisions and the three external-data
   redistribution decisions were confirmed by the project owner on 2026-09-07.
2. The applicable license documents are held by the owner and are not committed;
   this repository records the owner's explicit attestation, not the documents.
3. Run the strict publication audit in every clean CI checkout so newly added or
   unresolved data cannot silently enter the release.
4. Re-open this review if a file, upstream source, license or public host changes.

Do not create `v1.0.0` if any manifest group becomes unresolved.

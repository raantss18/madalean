Recorded answers of public scholarly APIs (arXiv API, doi.org/Crossref, OpenAlex, OpenLibrary, zbMATH Open, Semantic
Scholar), replayed by the offline tests through `madalean.research.fetch.ReplayTransport`. Recorded on 2026-11-21 by
`MADALEAN_ONLINE_TESTS=1 MADALEAN_RECORD=1 pytest tests/test_sources_online.py`. Metadata only (Crossref, OpenAlex
and arXiv metadata are CC0; zbMATH Open data CC BY-SA 4.0). No paper full text is stored here: the e-print and PDF
answers are replaced in the tests by Madalean's own CC0 demo note (`madalean/research/demo_data/`).

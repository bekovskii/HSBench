# Search source modules

`hs_classifier/` is copied from the MIT-licensed upstream `harvard-growth-lab/hscode-mapping` repository. It includes Lingua language detection/translation, Sentence Transformers embedding setup, FAISS retrieval, and search-term/reranking modules.

The package expects Python 3.12+, the dependencies listed in the upstream `pyproject.toml`, model access, an initialized index, and upstream Atlas-backed source data. Those runtime assets are not included. It is kept as the Day 1–2 integration source; the Day 3 page currently uses the small local tariff sample for a clearly labeled text-match preview.


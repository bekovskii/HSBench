# Search source modules

`hs_classifier/` is copied from the MIT-licensed upstream `harvard-growth-lab/hscode-mapping` repository. It includes Lingua language detection/translation, Sentence Transformers embedding setup, FAISS retrieval, and search-term/reranking modules.

`build_hsbench_index.py` builds a separate multilingual index from the local HSBench HS6 nodes, so this project does not need Harvard's Atlas credentials. Search uses Lingua for detection, local Ollama to translate English phrases to Chinese, and FAISS over 5,615 S-BERT vectors. The Harvard Atlas loader remains available for its original dataset. Search falls back to the labeled tariff sample if the optional dependencies or local model weights are unavailable.

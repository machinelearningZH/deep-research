import pandas as pd
import spacy
from transformers import AutoTokenizer
import yaml
from pathlib import Path


def load_config():
    config_path = Path(__file__).parent / "config_data.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


config = load_config()


nlp = spacy.load(
    "de_core_news_lg",
    disable=["ner", "tagger", "morphologizer", "attribute_ruler", "lemmatizer"],
)
nlp.max_length = 1_500_000

model_path = "intfloat/multilingual-e5-small"
tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True)


def chunk_text(data, max_token_count=500, overlap_tokens=100):
    """Chunk text into parts of max_token_count tokens with overlap_sents sentences overlap.

    Parameters
    ----------
    data : pd.DataFrame
        DataFrame containing the data.
    max_token_count : int, optional
        The maximum number of tokens per chunk, by default 512.
    overlap_sents : int, optional
        The number of sentences to overlap between chunks, by default 5.

    Returns
    -------
    list
        List of tuples containing the identifier and the chunked text.
    """
    try:
        # Sentencize text.
        doc = nlp(data.text)
        sents = [sent.text for sent in doc.sents]

        # Count tokens in each sentence.
        # TODO: Sentences can potentially be longer than max_token_count. Find a way to handle this.
        tokens = [len(tokenizer.tokenize(sent)) for sent in sents]

        # Create chunks by adding full sentences until max_token_count is reached.
        chunks = []
        current_chunk_start = 0
        current_sent = 0
        current_chunk = []
        current_tokens = 0

        while True:
            if current_sent >= len(sents):
                chunks.append(" ".join(current_chunk))
                break

            current_tokens += tokens[current_sent]
            if current_tokens < max_token_count:
                current_chunk.append(sents[current_sent])
                current_sent += 1
            else:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_tokens = 0

                # Go back n sents until we create an overlap of overlap_tokens or more.
                count_back_tokens = 0
                count_back_sents = 0
                while True:
                    count_back_tokens += tokens[current_sent]
                    count_back_sents += 1
                    if count_back_tokens > overlap_tokens:
                        break
                    current_sent -= 1
                current_sent -= count_back_sents

                # Avoid endless loop if overlap_sents is too high.
                if current_sent <= current_chunk_start:
                    current_sent = current_chunk_start + 1
                current_chunk_start = current_sent

        return [(data.identifier, chunk) for chunk in chunks]

    except Exception as e:
        print(f"Error chunking text: {data.identifier} - {e}")
        return [(data.identifier, None)]

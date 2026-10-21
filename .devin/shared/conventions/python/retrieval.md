# Retrieval conventions

What to do when a model needs knowledge it was not trained on. [llm](llm.md) owns the model call
itself; [backend](backend.md) owns the database this runs in.

## Choose per corpus, not once

Retrieval architecture is a per-corpus decision. Defaulting every case to a pipeline is how a
team ends up maintaining an index for forty documents it wrote itself.

| The corpus | Use | Why |
|---|---|---|
| We own and curate the content | A curated knowledge base | The content is already structured and small enough to hand over directly. An index adds a staleness problem and buys nothing. |
| Small, one-off, or confidential | Agentic search over the source | Nothing is copied or embedded, so there is no second place for confidential material to live and no index to keep current. |
| Large, high-volume, or citations required | A RAG pipeline | Only at this point does the cost of building and maintaining an index earn itself. |

Write down which one a corpus got, and why. The next person will otherwise assume RAG.

## When it is RAG

- Recursive chunking at about 512 tokens. Chunk boundaries that ignore document structure split
  a sentence from the thing that gives it meaning.
- Hybrid search, then rerank. Vector similarity alone misses exact identifiers, names and codes,
  which is often precisely what a user searched for.
- In the PostgreSQL the service already runs. A separate vector database is a new dependency,
  a new backup, and a new failure mode — take it only for a measured reason.
- **Answers carry source spans.** An answer that cannot show where it came from cannot be
  checked, and an unverifiable answer from a model is a liability rather than an asset.
- **Who may see what is enforced in the database, before anything reaches the model.** This is the
  rule that does not bend. Where confidentiality is contractual — acquisition material is the case
  we have — that means a separate index per deal rather than one shared index with a filter over
  it. A filter is a line of code someone can forget, and forgetting it puts one party's documents
  in front of a question asked about another.
- **Deleting a document deletes its chunks, its vectors and any cached answers built from it.** A
  document removed from the source while its embeddings survive is still answering questions.
- **Measure retrieval separately from the final answer.** A good answer built on the wrong
  documents and a bad answer built on the right ones need different fixes, and one end-to-end score
  hides which you have.
- A corpus may be **embedded locally and held in a local index** instead of going to a hosted
  embedding service. This is an available choice, not a requirement — take it when a specific
  customer agreement requires it, and write down which agreement.
- **Record the embedding model and its version with every index.** An index built by a model
  nobody wrote down cannot be safely rebuilt or extended: new vectors from a different model do
  not share a space with the old ones, and nothing about the failure looks like an error.

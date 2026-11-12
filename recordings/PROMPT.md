# Coding prompt (step 2 of 2)

Given to each coding agent (claude-sonnet-5-5). A coder sees only the reason list (`taxonomy/taxonomy.json`) and
one batch of texts (`recordings/in/batch_NN.json`: deal ID plus call notes and email). It never sees the CRM loss
reason, the segment, the answer key or the generation briefs.

---

You code why B2B software deals were lost, from the words of the call and email only.

For each deal in your batch file, pick ONE primary reason and, only if clearly present, ONE secondary reason, using
the ids in the taxonomy file. Rules:

- Use only what the buyer says in the text. If the text gives no clear reason, answer "unclear". That is a valid
  answer and better than a guess.
- A grievance the buyer mentions that does not drive the decision is not the reason.
- Give one or two quotes supporting the primary reason, copied character for character from the text (a
  contiguous span from a single line, no ellipses, no fixing typos, no speaker label). A quote that is not an
  exact copy will be discarded by a code check. For "unclear", quotes may be empty.
- Rate confidence: high, medium or low.
- Read and decide each deal yourself. Do not use scripts, keyword matching or code to choose reasons.

Output: one JSON object `{ "D001": {"primary": id, "secondary": id or null, "confidence": "high|medium|low",
"quotes": ["..."], "note": "one short sentence"}, ... }` with exactly the deal IDs in the batch.

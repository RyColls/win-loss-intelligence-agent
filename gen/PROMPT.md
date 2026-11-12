# Dataset generation prompt (step 1 of 2)

This is the prompt given to each writing agent. One agent wrote each batch of about 40 deals from a brief file
(`gen/briefs/batch_NN.json`) and saved the result to `gen/out/batch_NN.json`. The analysis agent in step 2 never
sees the briefs, the answer key or this prompt.

---

You are writing synthetic sales-call material for a fictional software company, Lanternmere HR (an HR and
payroll platform for companies with 50 to 500 employees). Everything is invented. Read the brief file named in
your task. For every deal in it, write:

1. `call_notes`: an excerpt from the recorded call, in natural speech, close to `target_words_call_notes` words
   (stay between 150 and 400). Use speaker labels: `Rep:` for our salesperson and `Name (Title):` for buyers, using
   the names and titles in the brief. Real calls are untidy: false starts, small talk, tangents, a number said two
   ways, a question answered with a question. The real reason the deal went the way it did should appear the way a
   buyer actually says it, in their own words and in their own order, never as a tidy summary.
2. `closing_email`: only if `write_closing_email` is true, otherwise `null`. A short email from the buyer or the
   rep, close to `target_words_email` words, consistent with the call.

Rules:

- Follow `what_the_buyer_conveys` exactly. It says what is really going on. Do not quote it, do not name its
  category, and do not use the words "price objection", "feature gap" or similar labels. Show it in speech.
- If `outcome` is `won`, the buyer chose Lanternmere HR. If it is `lost`, they did not.
- If the brief says to be vague, be vague. No hidden hint of a reason.
- If `include_mobile_app_complaint` is true, include a vivid, specific complaint about our mobile app (a login
  that logs people out, a clock-in screen that freezes). It is unrelated to why the deal ended up the way it did,
  and the buyer does not treat it as the deciding factor.
- Use `voice` as the speaking style. Vary sentence length and structure from deal to deal. Do not reuse
  openings. Do not reuse the same example twice across deals.
- Never mention the CRM, a dropdown, a "loss reason", or any real company or product. Competitors appear only by
  the name given in `competitor_in_crm` when it is not `none`, and only if it comes up naturally.
- Write each deal by hand, one at a time. Do not generate the text with a script, a loop or sentence templates.

Output: a single JSON object `{ "D001": {"call_notes": "...", "closing_email": null}, ... }` with exactly the deal
IDs in the brief. Plain text only inside the strings (use `\n` for line breaks).

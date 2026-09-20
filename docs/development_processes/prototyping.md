# Prototyping process

How to run a design prototype for this project, written to be handed to an agent
as a prompt. It is the process that produced `prototypes/devin-prototype/`,
including the parts that went wrong.

Read `prototypes/README.md` first for the repository conventions. This document
is about **how to work**, not where files go.

---

## 1. What a prototype is for

A prototype exists to answer questions that cannot be answered on paper. It is
not a first draft of the product and it does not propose an architecture. It is a
throwaway surface where alternatives are put side by side and looked at.

If you find yourself writing migrations, services, or tests for domain logic,
you have left prototyping.

**Non-negotiable conventions**

- Static files, no build step. HTML, CSS and plain JavaScript. Loading a library
  from a CDN as an ES module is acceptable; adding a bundler is not.
- Hardcoded data. No database, no persistence, no API.
- One folder per prototype, with its own README describing approach and visual
  identity in enough detail to reproduce it.
- The prototype does not touch `src/`, `alembic/` or configuration.

---

## 2. Before writing any code

Ask **three to five questions, no more**. Enough to remove the ambiguity that
would make you rebuild everything; not so many that you are asking the user to
design it.

Questions that paid off:

- **Form.** Standalone static pages, a single page with a hash router, or
  something inside the real application? The answer changes every file you write.
- **Language.** Which language for the interface copy and the fake content?
- **Fidelity.** Keep the principles of a reference design and improve the
  execution, or propose something independent?
- **Scope.** Which content types are in this round?

Do not ask about taste. Taste is what the prototype is for.

---

## 3. The loop

Work in this order. Do not skip a step because the next one is more
interesting.

### 3.1 Establish the system on one page

Build **tokens, typography and one page** before any other page. The first page
becomes the reference implementation; every later page is a variation of it. If
the system is wrong, you find out after one page instead of twelve.

### 3.2 Build the shell and the content types

The shell (navigation, layout, responsive behaviour) is shared by every page and
is therefore the highest-leverage thing to get right. Build it once, inject it,
and keep the pages as pure content.

### 3.3 For every open question, build BOTH options behind a toggle

This was the single most effective technique in the whole process. Repeatedly,
the question was "should this be A or B", and the answer was to build both, from
the same markup, switched by a preference:

- symbol style: icons or shapes;
- navigation: one list or two, for characters and NPCs;
- editor layout: labelled fields or a document;
- writing engine: three of them, on the same document.

Two rules make it work:

- **The same state, two presentations.** Never build two disconnected demos:
  switching must not lose anything, so the user compares the *presentation* and
  not the content.
- **A toggle that is visibly a comparison.** Label it, explain in the page what
  the two options mean, and put a shortcut in the page so the comparison does not
  require going back to a settings panel.

The payoff is that the decision is made on real content. Almost every decision in
this project was made that way, and the ones that were made in prose had to be
revisited.

### 3.4 Verify with a browser after every change

- Load the page in a real browser and assert **no console errors** and no failed
  requests.
- Take screenshots: full page at desktop, and at phone width.
- Check the states you just built, not only the default one.
- Interact: click, type, open the menu, submit.

A change is not done because the file looks right.

### 3.5 Record the decision, with the alternatives

Keep a living document next to the prototype. For every question, record:

- what was decided;
- **why**, in terms that can be checked;
- **what was rejected and why** — this is the part that pays off later, when
  someone asks "why not X" six months after everyone has forgotten;
- what the decision costs, and what the escape hatch is if it turns out wrong.

---

## 4. What went wrong, and the rule that comes out of it

Every item below is a real mistake from the prototype this document is based on.
They are the reason the rules exist.

| Mistake | Rule |
|---|---|
| Hand-built a caret, an active-line highlight and an equal-height hack inside a `<textarea>`, to imitate an editor. All of it was deleted the moment real editors were compared. | **When the surface is a textarea and the requirements read like an editor's, stop and evaluate editors first.** Do not build the hacks. |
| The first demo of one candidate rendered only references, so it looked worse than it was. The user nearly chose on a false comparison. | **Every candidate demo must cover the same feature set**, or say loudly in the page what is missing. An unfair comparison is worse than no comparison. |
| A full-page screenshot made a sticky sidebar look like it stopped halfway down. The user reported it as a bug twice. | **Know your verification tool's artifacts**, and say "this is my screenshot, not your browser" when it is. Otherwise you spend two rounds on a non-bug. |
| Repeatedly wrote `!doctype html>` without the `<`, and wrote CSS selectors scoped to one container while the page used another. | **Add a check that would have caught it.** A browser assertion on a specific expected state catches both; reading the file again does not. |
| Renamed a root attribute (`data-character-editor` to `data-doc`) and silently disabled a whole page. | **When renaming a selector or attribute, grep for every producer**, not only for the consumer you are editing. |
| Recorded an exploration toggle as if it were a product decision, then had to correct the document when the user pointed out the alternative was never real. | **Separate "we are exploring" from "we decided"** in the document. Different sections, different words. |
| Wrote a claim in the document ("the decision is whether the document stays Markdown") that was imprecise, and was corrected by the user. | **Only write claims you can verify.** If you cannot point at a measurement, a file or a demonstration, do not write it as fact. |
| Proposed a preference for something that is a build-time choice (which editor to use). | **Ask: who would set this, and what breaks if two people disagree?** If two people disagreeing would change the *content*, it is not a preference. |
| Added a fourth switch to a fixed-height panel and broke the phone layout. | **Re-check the smallest viewport after every addition** to a fixed-size container. |
| Invented plausible campaign content (a "next act" the user had not planned). | **Never invent facts about the user's data.** Ask, or leave it out. Plausible-looking fiction in a prototype reads as a requirement. |

---

## 5. When the user reports something

1. **Reproduce it** before changing anything.
2. **Check whether it is real or an artifact** of how you captured it.
3. If it is real, **write the check that fails**, then fix, then confirm the check
   passes. Several bugs in this project were found only because a comparison page
   measured things instead of showing them.
4. If you cannot reproduce it, say so and ask for the exact state. Do not "fix"
   something you cannot see.

---

## 6. Comparing two implementations mechanically

The most valuable single artifact of this process was a page that renders the
**same input twice** through two different implementations and compares them
instead of showing them side by side:

- text, word by word;
- block structure, element by element;
- **geometry**, element by element: height, margins.

It caught two real defects that no amount of looking would have found: a hidden
element leaking into the measured text, and a wrapper element that made list
spacing differ between the two renderings.

Rules for building one:

- Use the **real** implementation on both sides. Generate the server-side output
  with the application's actual renderer and configuration, not a mock. Commit
  the generator script so the artifact can be regenerated.
- Report the comparison as a **pass or fail with the first difference**, not as a
  wall of output.
- Normalise only differences you can name and justify, and say so in the code.
  A silent normalisation turns a real defect into a green light.

---

## 7. Closing a prototype round

- The prototype README says what it is, how to run it, and what it does not do.
- Every open question is either decided in the document or explicitly listed as
  open.
- Decisions taken during prototyping are promoted into the feature documents
  (`docs/features-request/`), because that is what the implementation reads.
- Anything discovered that is worth doing but not now goes to
  `docs/features-request/desired_features.md`, with the constraint that would shape it.
- Commit the prototype. It is the record of *why*, and it is cheap to keep.

---

## 8. Prompt template

```
Prototype the following for this project: <what, and which content types>.

Constraints: static files under prototypes/<name>/, no build step, hardcoded
data, does not touch src/. Read prototypes/README.md and
docs/development_processes/prototyping.md first.

Start by asking me at most five questions about form, language and scope.

Then work in increments: establish the system on one page, build the shell, then
the content types. Where a question has two plausible answers, build both from
the same state behind a visible toggle so I can compare them on real content.

Verify every increment in a browser: no console errors, desktop and phone
screenshots, and check the states you just built.

Keep a document next to the prototype recording each decision, why, what was
rejected, and what the decision costs.

Do not invent facts about my campaign content. Ask, or leave it out.
```

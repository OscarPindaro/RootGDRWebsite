/* Obsidian-style live preview for the Markdown editor.
 *
 * The document stays Markdown: every rendered construct is a decoration. The
 * line the selection is on keeps its Markdown, so the author can edit it; every
 * other line hides the markers and styles the text, so the page reads as the
 * rendered result while it is being written.
 */
import { Decoration, ViewPlugin } from "@codemirror/view";
import { syntaxTree } from "@codemirror/language";

const hide = Decoration.replace({});

const MARKS = new Set([
  "HeaderMark",
  "EmphasisMark",
  "CodeMark",
  "LinkMark",
]);

const heading = (level) =>
  Decoration.mark({ class: `cm-lp-h${level}` });
const HEADINGS = {
  ATXHeading1: heading(1),
  ATXHeading2: heading(2),
  ATXHeading3: heading(3),
  ATXHeading4: heading(4),
  ATXHeading5: heading(5),
  ATXHeading6: heading(6),
};
const STRONG = Decoration.mark({ class: "cm-lp-strong" });
const EMPHASIS = Decoration.mark({ class: "cm-lp-emphasis" });
const CODE = Decoration.mark({ class: "cm-lp-code" });
const LINK = Decoration.mark({ class: "cm-lp-link" });
const MENTION = Decoration.mark({ class: "cm-lp-mention" });

const MENTION_RE = /@\[[^\]]+\]/g;

function children(node) {
  const list = [];
  for (let child = node.firstChild; child; child = child.nextSibling) {
    list.push(child);
  }
  return list;
}

function activeLines(state) {
  const lines = new Set();
  for (const range of state.selection.ranges) {
    const first = state.doc.lineAt(range.from).number;
    const last = state.doc.lineAt(range.to).number;
    for (let number = first; number <= last; number += 1) lines.add(number);
  }
  return lines;
}

function decorateNode(node, state, decorations) {
  const line = state.doc.lineAt(node.from);
  if (line.number !== state.doc.lineAt(node.to).number) return;
  const kids = children(node);
  const marks = kids.filter((child) => MARKS.has(child.name));
  if (marks.length === 0) return;

  const level = HEADINGS[node.name];
  if (level) {
    const marker = marks[0];
    // Hide the marker and the space after it, then style the rest of the line.
    decorations.push(hide.range(marker.from, marker.to));
    let start = marker.to;
    if (state.doc.sliceString(start, start + 1) === " ") start += 1;
    if (start < line.to) decorations.push(level.range(start, line.to));
    return;
  }

  if (node.name === "StrongEmphasis" || node.name === "Emphasis") {
    const first = marks[0];
    const last = marks[marks.length - 1];
    for (const mark of marks) decorations.push(hide.range(mark.from, mark.to));
    if (first.to < last.from) {
      decorations.push(
        (node.name === "StrongEmphasis" ? STRONG : EMPHASIS).range(
          first.to,
          last.from,
        ),
      );
    }
    return;
  }

  if (node.name === "InlineCode") {
    const first = marks[0];
    const last = marks[marks.length - 1];
    for (const mark of marks) decorations.push(hide.range(mark.from, mark.to));
    if (first.to < last.from) decorations.push(CODE.range(first.to, last.from));
    return;
  }

  if (node.name === "Link") {
    // `[text](url)` -> `text`: hide everything from the closing bracket on.
    const closing = marks.find(
      (mark) => state.doc.sliceString(mark.from, mark.to) === "]",
    );
    const opening = marks[0];
    if (!closing) return;
    decorations.push(hide.range(closing.from, node.to));
    if (opening.to < closing.from) {
      decorations.push(LINK.range(opening.to, closing.from));
    }
  }
}

function buildDecorations(view) {
  const { state } = view;
  const active = activeLines(state);
  const decorations = [];

  for (const { from, to } of view.visibleRanges) {
    syntaxTree(state).iterate({
      from,
      to,
      enter: (node) => {
        if (active.has(state.doc.lineAt(node.from).number)) return;
        decorateNode(node.node, state, decorations);
      },
    });

    // Mentions are not Markdown, so they are found in the text of the range.
    const text = state.doc.sliceString(from, to);
    MENTION_RE.lastIndex = 0;
    let match = MENTION_RE.exec(text);
    while (match) {
      const start = from + match.index;
      const line = state.doc.lineAt(start);
      if (!active.has(line.number)) {
        // Hide the brackets, keep the name.
        decorations.push(hide.range(start, start + 2));
        decorations.push(hide.range(start + match[0].length - 1, start + match[0].length));
        decorations.push(MENTION.range(start + 2, start + match[0].length - 1));
      }
      match = MENTION_RE.exec(text);
    }
  }

  return Decoration.set(decorations, true);
}

export const livePreview = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.decorations = buildDecorations(view);
    }

    update(update) {
      if (update.docChanged || update.viewportChanged || update.selectionSet) {
        this.decorations = buildDecorations(update.view);
      }
    }
  },
  { decorations: (view) => view.decorations },
);

/**
 * Converts common Markdown syntax to Telegram-compatible HTML.
 *
 * Telegram's HTML mode supports a limited subset of tags:
 * <b>, <i>, <code>, <pre>, <a>, <u>, <s>, <blockquote>
 *
 * The LLM often returns Markdown, so we convert before sending.
 */

/**
 * Escape HTML special characters so they don't break Telegram's HTML parser.
 * Must run BEFORE any markdown→HTML tag conversion.
 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/**
 * Parse a contiguous markdown table block into headers + rows.
 * Returns null if the lines are not a valid table.
 */
function parseTable(tableLines: string[]): { headers: string[]; rows: string[][] } | null {
  if (tableLines.length < 2) return null;

  const parseCells = (line: string): string[] =>
    line.trim().slice(1, -1).split('|').map((c) => c.trim()).filter(Boolean);

  const headers = parseCells(tableLines[0]);
  if (headers.length === 0) return null;

  const rows: string[][] = [];
  for (let i = 1; i < tableLines.length; i++) {
    const trimmed = tableLines[i].trim();
    // Skip separator lines (|---|---|)
    if (/^\|[\s\-:|]+\|$/.test(trimmed)) continue;
    rows.push(parseCells(trimmed));
  }

  return { headers, rows };
}

/**
 * Convert a parsed table to a mobile-friendly vertical card layout (HTML).
 *
 * 2-column table:
 *   <b>col1</b>: col2
 *
 * 3+ column table:
 *   <b>col1_value</b>
 *   header2: col2_value
 *   header3: col3_value
 */
function tableToHtmlCards(headers: string[], rows: string[][]): string {
  if (rows.length === 0) {
    return `<b>${headers.join(' — ')}</b>`;
  }

  const cards: string[] = [];

  for (const cells of rows) {
    if (headers.length <= 2) {
      // 2-column: "<b>cell0</b>: cell1"  or just "<b>cell0</b>"
      const label = cells[0] ?? '';
      const value = cells[1];
      cards.push(value ? `<b>${label}</b>: ${value}` : `<b>${label}</b>`);
    } else {
      // 3+ columns: first cell is bold title, rest are "header: value"
      const lines: string[] = [`<b>${cells[0] ?? ''}</b>`];
      for (let c = 1; c < headers.length; c++) {
        if (cells[c]) {
          lines.push(`${headers[c]}: ${cells[c]}`);
        }
      }
      cards.push(lines.join('\n'));
    }
  }

  // Separate cards with blank line for 3+ col, single newline for 2 col
  return cards.join(headers.length <= 2 ? '\n' : '\n\n');
}

/**
 * Convert a parsed table to a mobile-friendly vertical card layout (plain text).
 * Same structure as HTML version but without tags.
 */
function tableToPlainCards(headers: string[], rows: string[][]): string {
  if (rows.length === 0) {
    return headers.join(' — ');
  }

  const cards: string[] = [];

  for (const cells of rows) {
    if (headers.length <= 2) {
      const label = cells[0] ?? '';
      const value = cells[1];
      cards.push(value ? `${label}: ${value}` : label);
    } else {
      const lines: string[] = [cells[0] ?? ''];
      for (let c = 1; c < headers.length; c++) {
        if (cells[c]) {
          lines.push(`${headers[c]}: ${cells[c]}`);
        }
      }
      cards.push(lines.join('\n'));
    }
  }

  return cards.join(headers.length <= 2 ? '\n' : '\n\n');
}

/** Check if a trimmed line is a table row (starts and ends with |). */
function isTableRow(line: string): boolean {
  const t = line.trim();
  return /^\|.*\|$/.test(t);
}

/** Check if a trimmed line is a table separator (|---|---|). */
function isSeparator(line: string): boolean {
  return /^\|[\s\-:|]+\|$/.test(line.trim());
}

/**
 * Find all contiguous table blocks in the text and replace them with
 * mobile-friendly cards.  `formatter` is called per table.
 */
function replaceMarkdownTables(
  text: string,
  formatter: (headers: string[], rows: string[][]) => string,
): string {
  const lines = text.split('\n');
  const result: string[] = [];
  let i = 0;

  while (i < lines.length) {
    if (isTableRow(lines[i]) || isSeparator(lines[i])) {
      // Collect contiguous table lines
      const tableLines: string[] = [];
      while (i < lines.length && (isTableRow(lines[i]) || isSeparator(lines[i]))) {
        tableLines.push(lines[i]);
        i++;
      }

      const parsed = parseTable(tableLines);
      if (parsed) {
        result.push(formatter(parsed.headers, parsed.rows));
      } else {
        // Not a valid table — keep original lines
        result.push(...tableLines);
      }
    } else {
      result.push(lines[i]);
      i++;
    }
  }

  return result.join('\n');
}

/**
 * Convert Markdown-formatted text to Telegram-compatible HTML.
 *
 * Handles (in order):
 * 0. Markdown tables       (| ... |) → mobile-friendly vertical cards
 * 1. HTML entity escaping  (& < >)
 * 2. Fenced code blocks    (```...```)
 * 3. Inline code           (`...`)
 * 4. Bold                  (**...**)
 * 5. Italic                (*...*)
 * 6. Markdown headers      (# ...)
 * 7. Blockquotes           (> ...)
 */
export function markdownToHtml(text: string): string {
  if (!text) return text;

  // Step 0 — convert markdown tables to mobile-friendly HTML cards
  // Must run before escapeHtml because we generate <b> tags here.
  // We escape cell content individually within tableToHtmlCards is not needed
  // because escapeHtml runs on the full text AFTER table conversion,
  // and our <b> tags get preserved by step 1's entity replacement
  // (they don't contain & < >).
  // Actually, we need to be careful: escapeHtml would break our <b> tags.
  // So we do table conversion AFTER escapeHtml and insert raw HTML.
  // BUT table pipes | need to be detected before escaping.
  //
  // Strategy: extract tables first, replace with placeholders, escape, then
  // re-insert. Simpler: convert tables to plain "label: value" first,
  // then let bold conversion handle **label**: value.
  //
  // Simplest correct approach: convert tables to markdown-formatted text
  // (using ** for bold), then let the rest of the pipeline handle it.
  let result = replaceMarkdownTables(text, (headers, rows) => {
    // Produce markdown text that the rest of the pipeline will convert
    if (rows.length === 0) return `**${headers.join(' — ')}**`;

    const cards: string[] = [];
    for (const cells of rows) {
      if (headers.length <= 2) {
        const label = cells[0] ?? '';
        const value = cells[1];
        cards.push(value ? `**${label}**: ${value}` : `**${label}**`);
      } else {
        const lines: string[] = [`**${cells[0] ?? ''}**`];
        for (let c = 1; c < headers.length; c++) {
          if (cells[c]) lines.push(`${headers[c]}: ${cells[c]}`);
        }
        cards.push(lines.join('\n'));
      }
    }
    return cards.join(headers.length <= 2 ? '\n' : '\n\n');
  });

  // Step 1 — escape HTML entities
  result = escapeHtml(result);

  // Step 2 — fenced code blocks (``` ... ```)
  result = result.replace(/```(?:\w*)\n?([\s\S]*?)```/g, (_match, code: string) => {
    return `<pre>${code.replace(/\n$/, '')}</pre>`;
  });

  // Step 3 — inline code (`...`)
  result = result.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Step 4 — bold (**...**)
  result = result.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');

  // Step 5 — italic (*...*)  — must come after bold
  result = result.replace(/\*(.+?)\*/g, '<i>$1</i>');

  // Step 6 — headers (# ... at line start) → bold text
  result = result.replace(/^#{1,6}\s+(.+)$/gm, '<b>$1</b>');

  // Step 7 — blockquotes (> ... at line start) → remove the > prefix
  result = result.replace(/^&gt;\s?/gm, '');

  return result;
}

/**
 * Strip markdown syntax to produce clean plain text (no HTML tags).
 * Used as a last-resort fallback when Telegram rejects our HTML.
 */
export function stripMarkdown(text: string): string {
  if (!text) return text;

  let result = replaceMarkdownTables(text, tableToPlainCards);

  // Fenced code blocks → just the code
  result = result.replace(/```(?:\w*)\n?([\s\S]*?)```/g, '$1');

  // Inline code → just the text
  result = result.replace(/`([^`]+)`/g, '$1');

  // Bold → just the text
  result = result.replace(/\*\*(.+?)\*\*/g, '$1');

  // Italic → just the text
  result = result.replace(/\*(.+?)\*/g, '$1');

  // Headers → just the text
  result = result.replace(/^#{1,6}\s+(.+)$/gm, '$1');

  // Blockquotes → remove > prefix
  result = result.replace(/^>\s?/gm, '');

  return result;
}

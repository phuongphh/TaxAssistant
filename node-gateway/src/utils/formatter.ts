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
 * Convert Markdown-formatted text to Telegram-compatible HTML.
 *
 * Handles (in order):
 * 1. HTML entity escaping  (& < >)
 * 2. Fenced code blocks    (```...```)
 * 3. Inline code           (`...`)
 * 4. Bold                  (**...**)
 * 5. Italic                (*...*)
 * 6. Markdown headers      (# ...)
 */
export function markdownToHtml(text: string): string {
  if (!text) return text;

  // Step 1 — escape HTML entities
  let result = escapeHtml(text);

  // Step 2 — fenced code blocks (``` ... ```)
  // Optionally capture a language hint after the opening fence.
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

  return result;
}

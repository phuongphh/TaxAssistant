import { describe, it, expect } from 'vitest';
import { markdownToHtml } from './formatter';

describe('markdownToHtml', () => {
  // --- HTML escaping ---
  it('escapes & < > to HTML entities', () => {
    expect(markdownToHtml('A & B < C > D')).toBe('A &amp; B &lt; C &gt; D');
  });

  // --- Bold ---
  it('converts **text** to <b>text</b>', () => {
    expect(markdownToHtml('Hello **world**')).toBe('Hello <b>world</b>');
  });

  it('converts multiple bold segments', () => {
    expect(markdownToHtml('**a** and **b**')).toBe('<b>a</b> and <b>b</b>');
  });

  // --- Italic ---
  it('converts *text* to <i>text</i>', () => {
    expect(markdownToHtml('Hello *world*')).toBe('Hello <i>world</i>');
  });

  // --- Bold before italic (order matters) ---
  it('handles bold and italic in same string', () => {
    expect(markdownToHtml('**bold** and *italic*')).toBe('<b>bold</b> and <i>italic</i>');
  });

  // --- Inline code ---
  it('converts `code` to <code>code</code>', () => {
    expect(markdownToHtml('Use `npm install`')).toBe('Use <code>npm install</code>');
  });

  // --- Fenced code blocks ---
  it('converts fenced code blocks to <pre>', () => {
    const input = '```\nconst x = 1;\n```';
    expect(markdownToHtml(input)).toBe('<pre>const x = 1;</pre>');
  });

  it('handles fenced code blocks with language hint', () => {
    const input = '```javascript\nconst x = 1;\n```';
    expect(markdownToHtml(input)).toBe('<pre>const x = 1;</pre>');
  });

  // --- Headers ---
  it('converts # header to bold', () => {
    expect(markdownToHtml('# Tiêu đề')).toBe('<b>Tiêu đề</b>');
  });

  it('converts ## header to bold', () => {
    expect(markdownToHtml('## Sub header')).toBe('<b>Sub header</b>');
  });

  it('only converts headers at line start', () => {
    expect(markdownToHtml('text # not a header')).toBe('text # not a header');
  });

  // --- Mixed formatting ---
  it('handles mixed markdown in a realistic LLM response', () => {
    const input = [
      '# Thuế GTGT',
      '',
      'Thuế **GTGT** (VAT) là *10%* cho hàng hóa.',
      'Dùng lệnh `tính thuế` để bắt đầu.',
    ].join('\n');

    const expected = [
      '<b>Thuế GTGT</b>',
      '',
      'Thuế <b>GTGT</b> (VAT) là <i>10%</i> cho hàng hóa.',
      'Dùng lệnh <code>tính thuế</code> để bắt đầu.',
    ].join('\n');

    expect(markdownToHtml(input)).toBe(expected);
  });

  // --- Edge cases ---
  it('returns empty string for empty input', () => {
    expect(markdownToHtml('')).toBe('');
  });

  it('returns plain text unchanged when no markdown', () => {
    const plain = 'Xin chào! Tôi là trợ lý thuế.';
    expect(markdownToHtml(plain)).toBe(plain);
  });

  it('escapes HTML inside markdown formatting', () => {
    expect(markdownToHtml('**<script>**')).toBe('<b>&lt;script&gt;</b>');
  });

  it('handles code block with HTML characters inside', () => {
    const input = '`a < b && c > d`';
    expect(markdownToHtml(input)).toBe('<code>a &lt; b &amp;&amp; c &gt; d</code>');
  });

  // --- Markdown tables ---
  it('converts markdown table rows to dash-separated text', () => {
    const input = [
      '| Lĩnh vực | Nội dung |',
      '|----------|----------|',
      '| Thuế TNCN | Tính thuế |',
      '| Thuế GTGT | Kê khai |',
    ].join('\n');

    const expected = [
      'Lĩnh vực — Nội dung',
      'Thuế TNCN — Tính thuế',
      'Thuế GTGT — Kê khai',
    ].join('\n');

    expect(markdownToHtml(input)).toBe(expected);
  });

  it('strips table separator lines', () => {
    const input = '| A | B |\n|---|---|\n| 1 | 2 |';
    expect(markdownToHtml(input)).toBe('A — B\n1 — 2');
  });

  // --- Blockquotes ---
  it('removes > blockquote prefix', () => {
    expect(markdownToHtml('> Trích dẫn')).toBe('Trích dẫn');
  });

  it('removes > from multiple blockquote lines', () => {
    const input = '> Dòng 1\n> Dòng 2';
    expect(markdownToHtml(input)).toBe('Dòng 1\nDòng 2');
  });

  it('handles > with no space after it', () => {
    expect(markdownToHtml('>Trích dẫn')).toBe('Trích dẫn');
  });
});

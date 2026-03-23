import { describe, it, expect } from 'vitest';
import { markdownToHtml, stripMarkdown } from './formatter';

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

  // --- Markdown tables (mobile-friendly card layout) ---
  it('converts 2-column table to bold label: value cards', () => {
    const input = [
      '| Lĩnh vực | Nội dung |',
      '|----------|----------|',
      '| Thuế TNCN | Tính thuế |',
      '| Thuế GTGT | Kê khai |',
    ].join('\n');

    const expected = [
      '<b>Thuế TNCN</b>: Tính thuế',
      '<b>Thuế GTGT</b>: Kê khai',
    ].join('\n');

    expect(markdownToHtml(input)).toBe(expected);
  });

  it('converts 3-column table to vertical cards with header labels', () => {
    const input = [
      '| Loại | Thuế suất | Áp dụng |',
      '|------|-----------|---------|',
      '| GTGT | 10% | Hàng hóa |',
      '| TNDN | 20% | Lợi nhuận |',
    ].join('\n');

    const expected = [
      '<b>GTGT</b>',
      'Thuế suất: 10%',
      'Áp dụng: Hàng hóa',
      '',
      '<b>TNDN</b>',
      'Thuế suất: 20%',
      'Áp dụng: Lợi nhuận',
    ].join('\n');

    expect(markdownToHtml(input)).toBe(expected);
  });

  it('strips table separator lines', () => {
    const input = '| A | B |\n|---|---|\n| 1 | 2 |';
    expect(markdownToHtml(input)).toBe('<b>1</b>: 2');
  });

  it('handles table with bold markdown in cells', () => {
    const input = [
      '| Loại | Mô tả |',
      '|------|-------|',
      '| **Thuế TNCN** | Tính thuế cá nhân |',
    ].join('\n');

    // ** in cell gets converted by the bold step
    const result = markdownToHtml(input);
    expect(result).toContain('Thuế TNCN');
    expect(result).toContain('Tính thuế cá nhân');
    expect(result).not.toContain('|');
  });

  it('handles header-only table (no data rows)', () => {
    const input = '| A | B |\n|---|---|';
    expect(markdownToHtml(input)).toBe('<b>A — B</b>');
  });

  it('preserves text around tables', () => {
    const input = 'Trước bảng\n| A | B |\n|---|---|\n| 1 | 2 |\nSau bảng';
    const result = markdownToHtml(input);
    expect(result).toContain('Trước bảng');
    expect(result).toContain('Sau bảng');
    expect(result).not.toContain('|');
  });

  it('renders the screenshot table as mobile-friendly cards', () => {
    const input = [
      '| Lĩnh vực | Nội dung |',
      '|----------|----------|',
      '| 💰 **Thuế TNCN** | Tính thuế, giảm trừ gia cảnh |',
      '| 📊 **Thuế GTGT** | Kê khai, khấu trừ, hoàn thuế |',
      '| 🏢 **Thuế TNDN** | Chi phí được trừ, lợi nhuận |',
    ].join('\n');

    const result = markdownToHtml(input);
    // Should have bold labels and values, no pipe characters
    expect(result).toContain('Thuế TNCN');
    expect(result).toContain('Tính thuế, giảm trừ gia cảnh');
    expect(result).toContain('Thuế GTGT');
    expect(result).not.toContain('|');
    expect(result).not.toContain('---');
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

describe('stripMarkdown', () => {
  it('strips **bold** markers', () => {
    expect(stripMarkdown('Hello **world**')).toBe('Hello world');
  });

  it('strips *italic* markers', () => {
    expect(stripMarkdown('Hello *world*')).toBe('Hello world');
  });

  it('strips `inline code` markers', () => {
    expect(stripMarkdown('Use `npm install`')).toBe('Use npm install');
  });

  it('strips # headers to plain text', () => {
    expect(stripMarkdown('## Tiêu đề')).toBe('Tiêu đề');
  });

  it('strips > blockquote prefix', () => {
    expect(stripMarkdown('> Trích dẫn')).toBe('Trích dẫn');
  });

  it('converts 2-column table to label: value', () => {
    const input = '| A | B |\n|---|---|\n| X | Y |';
    expect(stripMarkdown(input)).toBe('X: Y');
  });

  it('converts 3-column table to vertical card', () => {
    const input = '| Name | Rate | Note |\n|---|---|---|\n| VAT | 10% | goods |';
    expect(stripMarkdown(input)).toBe('VAT\nRate: 10%\nNote: goods');
  });

  it('does not produce HTML tags', () => {
    const input = '**bold** and *italic* and `code`';
    const result = stripMarkdown(input);
    expect(result).not.toContain('<');
    expect(result).not.toContain('>');
    expect(result).toBe('bold and italic and code');
  });

  it('strips fenced code blocks', () => {
    const input = '```js\nconst x = 1;\n```';
    expect(stripMarkdown(input)).toBe('const x = 1;\n');
  });
});

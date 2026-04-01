// Simple test to verify suggestion system logic
const { detectContext, generateSuggestions, formatSuggestions, isSuggestionChoice } = require('./node-gateway/dist/services/suggestionGenerator');

console.log('Testing Suggestion System\n');

// Test 1: Context Detection
console.log('=== Test 1: Context Detection ===');
const testCases = [
  { input: 'Tính thuế TNCN lương 20 triệu', expected: 'tax-calculation' },
  { input: 'Hạn nộp thuế môn bài 2025', expected: 'deadline-info' },
  { input: 'Tra cứu thông tư 78/2014/TT-BTC', expected: 'legal-doc' },
  { input: 'Đăng ký mã số thuế cá nhân', expected: 'tax-registration' },
  { input: 'Cách kê khai thuế GTGT', expected: 'declaration-guide' },
  { input: 'Xin chào', expected: 'general' },
];

testCases.forEach(({ input, expected }) => {
  const result = detectContext(input);
  const passed = result === expected;
  console.log(`${passed ? '✅' : '❌'} "${input}" -> ${result} (expected: ${expected})`);
});

// Test 2: Suggestion Generation
console.log('\n=== Test 2: Suggestion Generation ===');
const contexts = ['tax-calculation', 'deadline-info', 'legal-doc', 'tax-registration', 'declaration-guide', 'general'];
contexts.forEach(context => {
  const suggestions = generateSuggestions(context);
  console.log(`\n${context}:`);
  suggestions.forEach(s => {
    console.log(`  ${s.id}. ${s.text} (${s.action})`);
  });
});

// Test 3: Suggestion Formatting
console.log('\n=== Test 3: Suggestion Formatting ===');
const taxSuggestions = generateSuggestions('tax-calculation');
const formatted = formatSuggestions(taxSuggestions);
console.log('Formatted suggestions:');
console.log(formatted);

// Test 4: Suggestion Choice Detection
console.log('\n=== Test 4: Suggestion Choice Detection ===');
const choiceTests = [
  { input: '1', expected: true },
  { input: '2', expected: true },
  { input: '3', expected: true },
  { input: '4', expected: false },
  { input: '0', expected: false },
  { input: 'hello', expected: false },
  { input: ' 1 ', expected: true },
  { input: '', expected: false },
];

choiceTests.forEach(({ input, expected }) => {
  const result = isSuggestionChoice(input);
  const passed = result === expected;
  console.log(`${passed ? '✅' : '❌'} "${input}" -> ${result} (expected: ${expected})`);
});

console.log('\n=== All Tests Complete ===');
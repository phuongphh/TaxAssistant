// Simple test to verify suggestion generator logic
const suggestionGenerator = require('./node-gateway/dist/services/suggestionGenerator.js');

console.log('Testing suggestion generator...\n');

// Test 1: Generate suggestions for tax calculation
console.log('1. Tax calculation suggestions:');
const taxSuggestions = suggestionGenerator.generateSuggestions('tax-calculation');
taxSuggestions.forEach(s => {
  console.log(`   ${s.id}. ${s.text} (${s.action})`);
});

// Test 2: Detect context
console.log('\n2. Context detection:');
const testMessages = [
  'Tính thuế TNCN lương 20 triệu',
  'Hạn nộp thuế môn bài 2025',
  'Tra cứu thông tư 78/2014',
  'Đăng ký mã số thuế cá nhân',
  'Cách kê khai thuế GTGT'
];

testMessages.forEach(msg => {
  const context = suggestionGenerator.detectContext(msg);
  console.log(`   "${msg}" -> ${context}`);
});

// Test 3: Format suggestions
console.log('\n3. Format suggestions:');
const formatted = suggestionGenerator.formatSuggestions(taxSuggestions);
console.log(formatted);

// Test 4: Check suggestion choice
console.log('\n4. Suggestion choice detection:');
['1', '2', '3', '4', 'hello'].forEach(input => {
  console.log(`   "${input}" -> ${suggestionGenerator.isSuggestionChoice(input)}`);
});

console.log('\n✅ All tests completed!');
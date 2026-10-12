const assert=require('node:assert/strict'),ms=require('./index');
assert.equal(ms('-10.5h'),-37800000);assert.equal(ms('-.5h'),-1800000);assert.equal(ms('10.5h'),37800000);

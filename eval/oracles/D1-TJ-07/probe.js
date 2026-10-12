const assert=require('node:assert/strict'),ms=require('./index');assert.equal(ms('10-.5'),undefined);assert.equal(ms('-10.5'),-10.5);

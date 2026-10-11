const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
function fixture() {
  const controls = {};
  for (const id of ['#cancel-media','#retry-media']) controls[id] = {
    hidden:false, disabled:false, classList:{toggle(_,value) {controls[id].hidden=value;}}
  };
  const context = {document:{querySelector:id=>controls[id]}};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync('app/web/media-profiles.js','utf8'),context);
  return {context,controls};
}
test('owner active cancellation and disabled retry, terminal explicit retry',()=>{
  const {context,controls}=fixture();
  for (const state of ['queued','running','cancelling']) {
    context.updateProcessingControls({state},true);
    assert.equal(controls['#cancel-media'].hidden,false);
    assert.equal(controls['#cancel-media'].disabled,state==='cancelling');
    assert.equal(controls['#retry-media'].disabled,true);
  }
  for (const state of ['cancelled','failed','completed']) {
    context.updateProcessingControls({state},true);
    assert.equal(controls['#cancel-media'].hidden,true);
    assert.equal(controls['#retry-media'].disabled,false);
  }
});
test('nonowner controls hidden and absent DOM safe',()=>{
  const {context,controls}=fixture();
  context.updateProcessingControls({state:'running'},false);
  assert.equal(controls['#cancel-media'].hidden,true);
  assert.equal(controls['#retry-media'].hidden,true);
  context.document.querySelector=()=>null;
  assert.doesNotThrow(()=>context.updateProcessingControls({state:'running'},true));
});
test('late response after video switch, return, or same-video reentry discarded',()=>{
  const {context}=fixture();
  assert.equal(context.processingResponseIsCurrent('a',1,{id:'a'},1),true);
  assert.equal(context.processingResponseIsCurrent('a',1,{id:'b'},1),false);
  assert.equal(context.processingResponseIsCurrent('a',1,null,2),false);
  assert.equal(context.processingResponseIsCurrent('a',1,{id:'a'},2),false);
});

function cancelFixture(post) {
  const {context,controls}=fixture();
  context.$=id=>controls[id];context.guard=fn=>fn;
  context.currentVideo={id:'a'};context.mediaWatchGeneration=1;
  context.post=post;context.toast=()=>{};context.watches=[];
  context.watch=async id=>{context.watches.push(id);context.mediaWatchGeneration++;
    context.updateProcessingControls({state:'cancelling'},true);};
  const source=fs.readFileSync('app/web/community.js','utf8');
  const handler=source.split('\n').find(line=>line.startsWith("$('#cancel-media').onclick="));
  assert.ok(handler);vm.runInContext(handler,context);
  return {context,controls};
}
test('actual cancel handler keeps cancelling disabled and recovers only failed request',async()=>{
  const success=cancelFixture(async()=>({state:'cancelling'}));
  await success.controls['#cancel-media'].onclick();
  assert.deepEqual(success.context.watches,['a']);
  assert.equal(success.controls['#cancel-media'].disabled,true);
  const failure=cancelFixture(async()=>{throw Error('synthetic error');});
  await assert.rejects(failure.controls['#cancel-media'].onclick(),/synthetic error/);
  assert.equal(failure.controls['#cancel-media'].disabled,false);
});
test('actual cancel handler does not reopen same video after intervening navigation',async()=>{
  let finish;const request=new Promise(resolve=>{finish=resolve;});
  const {context,controls}=cancelFixture(()=>request);
  const pending=controls['#cancel-media'].onclick();
  context.mediaWatchGeneration=3;finish({state:'cancelled'});await pending;
  assert.deepEqual(context.watches,[]);
});

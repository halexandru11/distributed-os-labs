'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'interactive.html'), 'utf8');
const engine = html.match(/<script id="matrix-engine">([\s\S]*?)<\/script>/)[1];
const ui = html.match(/<script id="matrix-ui">([\s\S]*?)<\/script>/)[1];
vm.runInThisContext(engine, {filename: 'matrix-engine'});
new vm.Script(ui, {filename: 'matrix-ui'});
const M = globalThis.MatrixLab;
const config = (extra = {}) => ({n:3, m:5, r:4, strategy:'parallel_i', budget:4,
  ...M.generate(3, 5, 4, 'small', 1001), ...extra});
const reference = c => Array.from({length:c.n}, (_,i) => Array.from({length:c.r}, (_,j) => {
  let sum = 0n;
  for (let k=0;k<c.m;k++) sum += BigInt(c.a[i][k]) * BigInt(c.b[k][j]);
  return c.arithmetic === 'exact' ? sum : BigInt.asUintN(64, sum);
}));

test('every strategy covers every product once, with correct arithmetic and no overlapping work on a thread', () => {
  for (const spec of M.STRATEGIES) for (const [n,m,r] of [[1,1,1],[3,5,4],[2,12,2],[12,2,12]])
    for (const policy of ['static','dynamic','guided']) for (const chunk of [0,2]) {
      const c = config({n,m,r,strategy:spec.id,budget:8,schedules:Array(3).fill(policy),
        chunks:Array(3).fill(chunk),...M.generate(n,m,r,'random_full',1001)});
      const plan = M.buildPlan(c);
      assert.equal(plan.events.length,n*m*r);
      assert.equal(new Set(plan.events.map(e=>`${e.i},${e.j},${e.k}`)).size,n*m*r);
      assert.deepEqual(M.replay(plan,plan.duration).values,reference(c));
      assert.deepEqual(M.replay(plan,0).values,Array.from({length:n},()=>Array(r).fill(0n)));
      for (const worker of plan.workers) {
        const events=plan.events.filter(e=>e.worker===worker);
        for(let q=1;q<events.length;q++)assert.ok(events[q].start>=events[q-1].end);
      }
      for(const team of plan.teams) {
        const iterations=team.chunks.flatMap(c=>Array.from({length:c.end-c.begin},(_,q)=>c.begin+q));
        assert.equal(new Set(iterations).size,iterations.length);
      }
    }
});

test('row, column, flattened-cell and contribution ownership are distinct', () => {
  const values=M.generate(2,4,6,'small',1),base=config({n:2,m:4,r:6,budget:8,...values});
  const rows=M.buildPlan({...base,strategy:'parallel_i'});
  const cells=M.buildPlan({...base,strategy:'collapse_ij'});
  assert.equal(rows.workers.length,2);
  assert.equal(cells.workers.length,8);
  for(const row of rows.cells)assert.equal(new Set(row.flat().map(e=>e.worker)).size,1);
  const cols=M.buildPlan({...base,strategy:'parallel_j'});
  assert.ok(Math.max(...cols.events.filter(e=>e.i===0).map(e=>e.end)) <= Math.min(...cols.events.filter(e=>e.i===1).map(e=>e.start)));
  for(const cell of cells.cells.flat())assert.equal(new Set(cell.map(e=>e.worker)).size,1);
  const sums=M.buildPlan({...base,strategy:'parallel_k'});
  assert.equal(new Set(sums.cells[0][0].map(e=>e.worker)).size,4);
});

test('nested allocation preserves exact total budgets and active-level limits', () => {
  for(const spec of M.STRATEGIES)for(const budget of [1,4,7,8,12,32,256]) {
    const threads=M.balancedThreads(spec.id,budget);
    const product=spec.groups.filter(g=>g.parallel).reduce((p,g)=>p*threads[M.LOOPS.indexOf(g.loops[0])],1);
    assert.equal(product,spec.id==='seq'?1:budget);
  }
  assert.deepEqual(M.balancedThreads('nested_ijk',8),[2,2,2]);
  assert.deepEqual(M.balancedThreads('nested_jk',8),[1,4,2]);
  let plan=M.buildPlan(config({strategy:'nested_ijk',threadMode:'explicit',threads:[2,2,2],maxLevels:1}));
  assert.ok(plan.teams.filter(t=>t.level>1).every(t=>t.size===1));
  plan=M.buildPlan(config({strategy:'nested_ijk',threadMode:'explicit',threads:[1,2,4],maxLevels:1}));
  assert.ok(plan.teams.filter(t=>t.level===2).every(t=>t.size===2));
  assert.ok(plan.teams.filter(t=>t.level===3).every(t=>t.size===1));
});

test('race demonstration loses concurrent writes while protected sums stay correct', () => {
  const c=config({n:1,m:4,r:1,strategy:'parallel_k',budget:4,a:[['1','2','3','4']],b:[['1'],['1'],['1'],['1']]});
  const plan=M.buildPlan(c);
  assert.equal(M.replay(plan,plan.duration,false).values[0][0],10n);
  assert.notEqual(M.replay(plan,plan.duration,true).values[0][0],10n);
  const seq=M.buildPlan({...c,strategy:'seq'});
  assert.equal(M.replay(seq,seq.duration,true).values[0][0],10n);
});

test('input parsing, exact signed integers, overflow, and imported configurations', () => {
  assert.deepEqual(M.parseMatrix('1, 2\n3; 4'),[['1','2'],['3','4']]);
  assert.throws(()=>M.parseMatrix('1 2\n3'));
  assert.throws(()=>M.integer('1.5'));
  assert.throws(()=>M.integer(Number.MAX_SAFE_INTEGER+1));
  assert.equal(M.integer('18446744073709551615'),M.MASK);
  assert.throws(()=>M.validate(config({n:0})));
  assert.throws(()=>M.validate(config({strategy:'made-up'})));
  const exact=config({arithmetic:'exact',...M.generate(3,5,4,'signed',42)});
  const plan=M.buildPlan(exact);
  assert.deepEqual(M.replay(plan,plan.duration).values,reference(exact));
  const max=M.buildPlan(config({...M.generate(3,5,4,'max',1)}));
  assert.ok(max.truth.flat().every(value=>value===5n));
  const roundTrip=M.validate(JSON.parse(JSON.stringify(config())));
  assert.deepEqual(M.buildPlan(roundTrip).truth,M.buildPlan(config()).truth);
});

test('layouts preserve the mathematical result and dispatch is reproducible', () => {
  const c=config({strategy:'nested_ijk',budget:8,schedules:['dynamic','guided','static'],chunks:[1,2,1]});
  const a=M.buildPlan(c),b=M.buildPlan(c),transposed=M.buildPlan({...c,layout:'transposed'});
  assert.deepEqual(a.events,b.events);
  assert.deepEqual(a.truth,transposed.truth);
  assert.deepEqual(a.events,transposed.events);
});

test('homework generators and arithmetic agree with the actual C implementation', {skip:!fs.existsSync(path.join(root,'matmul'))}, () => {
  for(const spec of M.STRATEGIES)for(const dataset of ['random','random_full','zeros','ones','max']) {
    const c=config({strategy:spec.id,seed:1001,...M.generate(3,5,4,dataset,1001)});
    const plan=M.buildPlan(c);
    let hash=14695981039346656037n;
    for(const value of plan.truth.flat())hash=BigInt.asUintN(64,(hash^value)*1099511628211n);
    const result=spawnSync(path.join(root,'matmul'),['--n','3','--m','5','--r','4','--variant',spec.id,
      '--budget','4','--dataset',dataset,'--seed','1001','--repeats','1','--warmups','0'],
      {encoding:'utf8',env:{...process.env,OMP_WAIT_POLICY:'PASSIVE'},timeout:10000});
    assert.equal(result.status,0,result.stderr);
    assert.equal(JSON.parse(result.stdout).checksum,hash.toString(16).padStart(16,'0'));
  }
});

test('embedded source excerpts are exact copies of the current C functions', () => {
  const embedded=JSON.parse(html.match(/<script id="matrix-source" type="application\/json">([\s\S]*?)<\/script>/)[1]);
  const source=fs.readFileSync(path.join(root,'matmul.c'),'utf8');
  assert.equal(embedded.sha256,require('node:crypto').createHash('sha256').update(source).digest('hex'));
  assert.deepEqual(Object.keys(embedded.kernels),M.STRATEGIES.map(s=>s.id));
  const lines=source.split('\n');
  for(const record of [...Object.values(embedded.kernels),...Object.values(embedded.helpers)])
    assert.equal(lines.slice(record.startLine-1,record.startLine-1+record.text.split('\n').length).join('\n'),record.text);
});

test('tracing follows k through a sum and j after the sum; simultaneous k values remain distinct', () => {
  const plan=M.buildPlan(config({strategy:'parallel_i'}));
  let previousWorker=null;
  for(let wave=0;wave<12;wave++){
    const trace=M.traceContext(plan,wave,{mode:'execution',previousWorker,selected:{i:0,j:0,k:0}});
    assert.equal(trace.phase,'active');
    assert.equal(trace.event.start,wave);
    assert.equal(trace.event.k,wave%5);
    assert.equal(trace.event.j,Math.floor(wave/5));
    previousWorker=trace.event.worker;
  }
  const sums=M.buildPlan(config({strategy:'parallel_k',budget:4}));
  const first=M.traceContext(sums,0);
  assert.equal(new Set(first.active.map(e=>e.k)).size,4);
  for(const worker of sums.workers){
    const trace=M.traceContext(sums,0,{worker});
    assert.equal(trace.event.worker,worker);
    assert.equal(trace.phase,'active');
  }
});

test('cell inspection preserves a requested future product and distinguishes waiting or finished work', () => {
  const plan=M.buildPlan(config({strategy:'seq'}));
  const selected={i:2,j:3,k:4};
  const inspect=M.traceContext(plan,0,{mode:'cell',selected,pinned:true});
  assert.equal(inspect.phase,'upcoming');
  assert.deepEqual([inspect.event.i,inspect.event.j,inspect.event.k],[2,3,4]);
  assert.equal(inspect.event.end,plan.duration);
  const complete=M.traceContext(plan,plan.duration,{mode:'cell',selected:{i:0,j:0,k:0}});
  assert.equal(complete.phase,'finished');
  assert.equal(complete.active.length,0);
  assert.equal(complete.event.k,4);
});

test('loop scopes correctly distinguish collapsed teams, serial loops and serialized nested teams', () => {
  for(const spec of M.STRATEGIES){
    const plan=M.buildPlan(config({strategy:spec.id,budget:8}));
    const scopes=M.loopScopes(plan,plan.events[0]);
    assert.deepEqual(scopes.map(s=>s.loop),['i','j','k']);
    assert.equal(new Set(scopes.filter(s=>s.parallel).map(s=>s.team)).size,spec.groups.filter(g=>g.parallel).length);
  }
  let plan=M.buildPlan(config({strategy:'collapse_ij'}));
  let scopes=M.loopScopes(plan,plan.events[0]);
  assert.equal(scopes[0].team,scopes[1].team);
  assert.equal(scopes[2].parallel,false);
  plan=M.buildPlan(config({strategy:'nested_ijk',budget:8,maxLevels:1}));
  scopes=M.loopScopes(plan,plan.events[0]);
  assert.deepEqual(scopes.map(s=>s.serialized),[false,true,true]);
});

import mitt from './src/index';
const e = mitt<{foo:string;bar?:number}>();
e.on('foo', value => {const typed:string=value;void typed;});
e.emit('foo','yes');e.emit('bar');e.emit('bar',1);
// @ts-expect-error wrong payload must be rejected
e.emit('foo',1);
// @ts-expect-error required payload cannot be omitted
e.emit('foo');
// @ts-expect-error wrong handler parameter must be rejected
e.on('foo',(n:number)=>{void n;});
e.on('*',(key,value)=>{const k:'foo'|'bar'=key;const v:string|number|undefined=value;void k;void v;});

// Evaluator-only behavioral oracle. Never materialize in an agent workspace.
'use strict';
let React, ReactNoop, Scheduler, act;
beforeEach(() => {
  jest.resetModules();
  React = require('react');
  ReactNoop = require('react-noop-renderer');
  Scheduler = require('scheduler');
  const internalAct = require('jest-react').act;
  act = cb => internalAct(() => ReactNoop.batchedUpdates(cb));
});
function store(initial) {
  let value = initial;
  const listeners = new Set();
  return {
    getSnapshot: () => value,
    subscribe: listener => { listeners.add(listener); return () => listeners.delete(listener); },
    publish: next => { value = next; ReactNoop.batchedUpdates(() => listeners.forEach(fn => fn())); },
    count: () => listeners.size,
  };
}
function App({source}) {
  const value = React.useSyncExternalStore(source.subscribe, source.getSnapshot);
  Scheduler.unstable_yieldValue(value);
  return value;
}
test('contract snapshot notifications and equality bailout', () => {
  const source = store('ready');
  const root = ReactNoop.createRoot();
  act(() => root.render(<App source={source} />));
  expect(Scheduler).toHaveYielded(['ready']);
  expect(root).toMatchRenderedOutput('ready');
  expect(source.count()).toBe(1);
  // Deliberately outside act: notifications must schedule synchronous work even
  // for a concurrent root; draining all scheduler work would mask that contract.
  React.startTransition(() => source.publish('next'));
  expect(Scheduler).toHaveYielded(['next']);
  expect(root).toMatchRenderedOutput('next');
  act(() => source.publish('next'));
  expect(Scheduler).toHaveYielded([]);
  expect(root).toMatchRenderedOutput('next');
  act(() => root.render(null));
  expect(source.count()).toBe(0);
});
test('contract store replacement unsubscribes previous source', () => {
  const first = store('old');
  const second = store('new');
  const root = ReactNoop.createRoot();
  act(() => root.render(<App source={first} />));
  expect(Scheduler).toHaveYielded(['old']);
  act(() => root.render(<App source={second} />));
  expect(Scheduler).toHaveYielded(['new']);
  expect(first.count()).toBe(0);
  expect(second.count()).toBe(1);
  act(() => first.publish('ignored'));
  expect(Scheduler).toHaveYielded([]);
  expect(root).toMatchRenderedOutput('new');
  act(() => second.publish('current'));
  expect(Scheduler).toHaveYielded(['current']);
  expect(root).toMatchRenderedOutput('current');
  act(() => root.render(null));
  expect(second.count()).toBe(0);
});
test('contract independently selected snapshot ignores unrelated field', () => {
  const source = store({a:'A0', b:'B0'});
  function Selected() {
    const value = React.useSyncExternalStore(source.subscribe, () => source.getSnapshot().a);
    Scheduler.unstable_yieldValue(value);
    return value;
  }
  const root = ReactNoop.createRoot();
  act(() => root.render(<Selected />));
  expect(Scheduler).toHaveYielded(['A0']);
  act(() => source.publish({a:'A0', b:'B1'}));
  expect(Scheduler).toHaveYielded([]);
  act(() => source.publish({a:'A1', b:'B1'}));
  expect(Scheduler).toHaveYielded(['A1']);
  expect(root).toMatchRenderedOutput('A1');
  act(() => root.render(null));
});
test('regression ordinary state update remains supported', () => {
  let update;
  function Stateful() {
    const [value, setValue] = React.useState('start');
    update = setValue;
    Scheduler.unstable_yieldValue(value);
    return value;
  }
  const root = ReactNoop.createRoot();
  act(() => root.render(<Stateful />));
  expect(Scheduler).toHaveYielded(['start']);
  act(() => update('finish'));
  expect(Scheduler).toHaveYielded(['finish']);
  expect(root).toMatchRenderedOutput('finish');
  act(() => root.render(null));
});
test('regression layout and passive effects release resources', () => {
  const calls = [];
  function Effectful() {
    React.useLayoutEffect(() => { calls.push('layout'); return () => calls.push('layout-cleanup'); }, []);
    React.useEffect(() => { calls.push('passive'); return () => calls.push('passive-cleanup'); }, []);
    return 'effects';
  }
  const root = ReactNoop.createRoot();
  act(() => root.render(<Effectful />));
  expect(calls).toEqual(['layout', 'passive']);
  act(() => root.render(null));
  expect(calls).toEqual(['layout', 'passive', 'layout-cleanup', 'passive-cleanup']);
});

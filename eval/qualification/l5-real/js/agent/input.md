The React package already exposes `useSyncExternalStore(subscribe, getSnapshot)`, but calling the built-in hook in a component currently throws “Not yet implemented”. Please complete its native behavior.

A component should render the current external snapshot, subscribe to changes, and update synchronously when that snapshot changes, including components mounted in a concurrent root and notifications wrapped in `startTransition`. Notifications that leave the selected snapshot unchanged should not force another render. If the component switches to another store, it should stop observing the previous store and read the new one; unmounting should release its subscription. Preserve ordinary state updates and effect cleanup behavior.

Use the existing public two-argument API and the captured development configuration. Server rendering and later pre-commit concurrency improvements are outside this request.
